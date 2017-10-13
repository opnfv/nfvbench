#!/usr/bin/env python
# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import compute
from glanceclient.v2 import client as glanceclient
from log import LOG
from neutronclient.neutron import client as neutronclient
from novaclient.client import Client
import os
import re
import time


class StageClientException(Exception):
    pass


class BasicStageClient(object):
    """Client for spawning and accessing the VM setup"""

    nfvbenchvm_config_name = 'nfvbenchvm.conf'

    def __init__(self, config, cred):
        self.comp = None
        self.image_instance = None
        self.image_name = None
        self.config = config
        self.cred = cred
        self.nets = []
        self.vms = []
        self.created_ports = []
        self.ports = {}
        self.compute_nodes = set([])
        self.comp = None
        self.neutron = None
        self.flavor_type = {'is_reuse': True, 'flavor': None}
        self.host_ips = None

    def _ensure_vms_active(self):
        retry_count = (self.config.check_traffic_time_sec +
                       self.config.generic_poll_sec - 1) / self.config.generic_poll_sec
        for _ in range(retry_count):
            for i, instance in enumerate(self.vms):
                if instance.status == 'ACTIVE':
                    continue
                is_reuse = getattr(instance, 'is_reuse', True)
                instance = self.comp.poll_server(instance)
                if instance.status == 'ERROR':
                    raise StageClientException('Instance creation error: %s' %
                                               instance.fault['message'])
                if instance.status == 'ACTIVE':
                    LOG.info('Created instance: %s', instance.name)
                self.vms[i] = instance
                setattr(self.vms[i], 'is_reuse', is_reuse)
            if all(map(lambda instance: instance.status == 'ACTIVE', self.vms)):
                return
            time.sleep(self.config.generic_poll_sec)
        raise StageClientException('Timed out waiting for VMs to spawn')

    def _setup_openstack_clients(self):
        self.session = self.cred.get_session()
        nova_client = Client(2, session=self.session)
        self.neutron = neutronclient.Client('2.0', session=self.session)
        self.glance_client = glanceclient.Client('2',
                                                 session=self.session)
        self.comp = compute.Compute(nova_client, self.glance_client, self.neutron, self.config)

    def _lookup_network(self, network_name):
        networks = self.neutron.list_networks(name=network_name)
        return networks['networks'][0] if networks['networks'] else None

    def _create_net(self, name, subnet, cidr, network_type=None,
                    segmentation_id=None, physical_network=None):
        network = self._lookup_network(name)
        if network:
            # a network of same name already exists, we need to verify it has the same
            # characteristics
            if segmentation_id:
                if network['provider:segmentation_id'] != segmentation_id:
                    raise StageClientException("Mismatch of 'segmentation_id' for reused "
                                               "network '{net}'. Network has id '{seg_id1}', "
                                               "configuration requires '{seg_id2}'."
                                               .format(net=name,
                                                       seg_id1=network['provider:segmentation_id'],
                                                       seg_id2=segmentation_id))

            if physical_network:
                if network['provider:physical_network'] != physical_network:
                    raise StageClientException("Mismatch of 'physical_network' for reused "
                                               "network '{net}'. Network has '{phys1}', "
                                               "configuration requires '{phys2}'."
                                               .format(net=name,
                                                       phys1=network['provider:physical_network'],
                                                       phys2=physical_network))

            LOG.info('Reusing existing network: ' + name)
            network['is_reuse'] = True
            return network

        body = {
            'network': {
                'name': name,
                'admin_state_up': True
            }
        }

        if network_type:
            body['network']['provider:network_type'] = network_type
            if segmentation_id:
                body['network']['provider:segmentation_id'] = segmentation_id
            if physical_network:
                body['network']['provider:physical_network'] = physical_network

        network = self.neutron.create_network(body)['network']
        body = {
            'subnet': {
                'name': subnet,
                'cidr': cidr,
                'network_id': network['id'],
                'enable_dhcp': False,
                'ip_version': 4,
                'dns_nameservers': []
            }
        }
        subnet = self.neutron.create_subnet(body)['subnet']
        # add subnet id to the network dict since it has just been added
        network['subnets'] = [subnet['id']]
        network['is_reuse'] = False
        LOG.info('Created network: %s.' % name)
        return network

    def _create_port(self, net):
        body = {
            "port": {
                'network_id': net['id'],
                'binding:vnic_type': 'direct' if self.config.sriov else 'normal'
            }
        }
        port = self.neutron.create_port(body)
        return port['port']

    def __delete_port(self, port):
        retry = 0
        while retry < self.config.generic_retry_count:
            try:
                self.neutron.delete_port(port['id'])
                return
            except Exception:
                retry += 1
                time.sleep(self.config.generic_poll_sec)
        LOG.error('Unable to delete port: %s' % (port['id']))

    def __delete_net(self, network):
        retry = 0
        while retry < self.config.generic_retry_count:
            try:
                self.neutron.delete_network(network['id'])
                return
            except Exception:
                retry += 1
                time.sleep(self.config.generic_poll_sec)
        LOG.error('Unable to delete network: %s' % (network['name']))

    def __get_server_az(self, server):
        availability_zone = getattr(server, 'OS-EXT-AZ:availability_zone', None)
        host = getattr(server, 'OS-EXT-SRV-ATTR:host', None)
        if availability_zone is None:
            return None
        if host is None:
            return None
        return availability_zone + ':' + host

    def _lookup_servers(self, name=None, nets=None, az=None, flavor_id=None):
        error_msg = 'VM with the same name, but non-matching {} found. Aborting.'
        networks = set(map(lambda net: net['name'], nets)) if nets else None
        server_list = self.comp.get_server_list()
        matching_servers = []

        for server in server_list:
            if name and server.name != name:
                continue

            if flavor_id and server.flavor['id'] != flavor_id:
                raise StageClientException(error_msg.format('flavors'))

            if networks and not set(server.networks.keys()).issuperset(networks):
                raise StageClientException(error_msg.format('networks'))

            if server.status != "ACTIVE":
                raise StageClientException(error_msg.format('state'))

            # everything matches
            matching_servers.append(server)

        return matching_servers

    def _create_server(self, name, ports, az, nfvbenchvm_config):
        port_ids = map(lambda port: {'port-id': port['id']}, ports)
        nfvbenchvm_config_location = os.path.join('/etc/', self.nfvbenchvm_config_name)
        server = self.comp.create_server(name,
                                         self.image_instance,
                                         self.flavor_type['flavor'],
                                         None,
                                         port_ids,
                                         None,
                                         avail_zone=az,
                                         user_data=None,
                                         config_drive=True,
                                         files={nfvbenchvm_config_location: nfvbenchvm_config})
        if server:
            setattr(server, 'is_reuse', False)
            LOG.info('Creating instance: %s on %s' % (name, az))
        else:
            raise StageClientException('Unable to create instance: %s.' % (name))
        return server

    def _setup_resources(self):
        # To avoid reuploading image in server mode, check whether image_name is set or not
        if self.image_name:
            self.image_instance = self.comp.find_image(self.image_name)
        if self.image_instance:
            LOG.info("Reusing image %s" % self.image_name)
        else:
            image_name_search_pattern = '(nfvbenchvm-\d+(\.\d+)*).qcow2'
            if self.config.vm_image_file:
                match = re.search(image_name_search_pattern, self.config.vm_image_file)
                if match:
                    self.image_name = match.group(1)
                    LOG.info('Using provided VM image file %s' % self.config.vm_image_file)
                else:
                    raise StageClientException('Provided VM image file name %s must start with '
                                               '"nfvbenchvm-<version>"' % self.config.vm_image_file)
            else:
                pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                for f in os.listdir(pkg_root):
                    if re.search(image_name_search_pattern, f):
                        self.config.vm_image_file = pkg_root + '/' + f
                        self.image_name = f.replace('.qcow2', '')
                        LOG.info('Found built-in VM image file %s' % f)
                        break
                else:
                    raise StageClientException('Cannot find any built-in VM image file.')
            if self.image_name:
                self.image_instance = self.comp.find_image(self.image_name)
            if not self.image_instance:
                LOG.info('Uploading %s'
                         % self.image_name)
                res = self.comp.upload_image_via_url(self.image_name,
                                                     self.config.vm_image_file)

                if not res:
                    raise StageClientException('Error uploading image %s from %s. ABORTING.'
                                               % (self.image_name,
                                                  self.config.vm_image_file))
                LOG.info('Image %s successfully uploaded.' % self.image_name)
                self.image_instance = self.comp.find_image(self.image_name)

        self.__setup_flavor()

    def __setup_flavor(self):
        if self.flavor_type.get('flavor', False):
            return

        self.flavor_type['flavor'] = self.comp.find_flavor(self.config.flavor_type)
        if self.flavor_type['flavor']:
            self.flavor_type['is_reuse'] = True
        else:
            flavor_dict = self.config.flavor
            extra_specs = flavor_dict.pop('extra_specs', None)

            self.flavor_type['flavor'] = self.comp.create_flavor(self.config.flavor_type,
                                                                 override=True,
                                                                 **flavor_dict)

            LOG.info("Flavor '%s' was created." % self.config.flavor_type)

            if extra_specs:
                self.flavor_type['flavor'].set_keys(extra_specs)

            self.flavor_type['is_reuse'] = False

        if self.flavor_type['flavor'] is None:
            raise StageClientException('%s: flavor to launch VM not found. ABORTING.'
                                       % self.config.flavor_type)

    def __delete_flavor(self, flavor):
        if self.comp.delete_flavor(flavor=flavor):
            LOG.info("Flavor '%s' deleted" % self.config.flavor_type)
            self.flavor_type = {'is_reuse': False, 'flavor': None}
        else:
            LOG.error('Unable to delete flavor: %s' % self.config.flavor_type)

    def get_config_file(self, chain_index, src_mac, dst_mac):
        boot_script_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        'nfvbenchvm/', self.nfvbenchvm_config_name)

        with open(boot_script_file, 'r') as boot_script:
            content = boot_script.read()

        g1cidr = self.config.generator_config.src_device.get_gw_ip(chain_index) + '/8'
        g2cidr = self.config.generator_config.dst_device.get_gw_ip(chain_index) + '/8'

        vm_config = {
            'forwarder': self.config.vm_forwarder,
            'tg_gateway1_ip': self.config.traffic_generator.tg_gateway_ip_addrs[0],
            'tg_gateway2_ip': self.config.traffic_generator.tg_gateway_ip_addrs[1],
            'tg_net1': self.config.traffic_generator.ip_addrs[0],
            'tg_net2': self.config.traffic_generator.ip_addrs[1],
            'vnf_gateway1_cidr': g1cidr,
            'vnf_gateway2_cidr': g2cidr,
            'tg_mac1': src_mac,
            'tg_mac2': dst_mac
        }

        return content.format(**vm_config)

    def set_ports(self):
        """Stores all ports of NFVbench networks."""
        nets = self.get_networks_uuids()
        for port in self.neutron.list_ports()['ports']:
            if port['network_id'] in nets:
                ports = self.ports.setdefault(port['network_id'], [])
                ports.append(port)

    def disable_port_security(self):
        """
        Disable security at port level.
        """
        vm_ids = map(lambda vm: vm.id, self.vms)
        for net in self.nets:
            for port in self.ports[net['id']]:
                if port['device_id'] in vm_ids:
                    self.neutron.update_port(port['id'], {
                        'port': {
                            'security_groups': [],
                            'port_security_enabled': False,
                        }
                    })
                    LOG.info('Security disabled on port {}'.format(port['id']))

    def get_loop_vm_hostnames(self):
        return [getattr(vm, 'OS-EXT-SRV-ATTR:hypervisor_hostname') for vm in self.vms]

    def get_host_ips(self):
        '''Return the IP adresss(es) of the host compute nodes for this VMclient instance.
        Returns a list of 1 IP adress or 2 IP addresses (PVVP inter-node)
        '''
        if not self.host_ips:
            #  get the hypervisor object from the host name
            self.host_ips = [self.comp.get_hypervisor(
                             getattr(vm, 'OS-EXT-SRV-ATTR:hypervisor_hostname')).host_ip
                             for vm in self.vms]
        return self.host_ips

    def get_loop_vm_compute_nodes(self):
        compute_nodes = []
        for vm in self.vms:
            az = getattr(vm, 'OS-EXT-AZ:availability_zone')
            hostname = getattr(vm, 'OS-EXT-SRV-ATTR:hypervisor_hostname')
            compute_nodes.append(az + ':' + hostname)
        return compute_nodes

    def get_reusable_vm(self, name, nets, az):
        servers = self._lookup_servers(name=name, nets=nets, az=az,
                                       flavor_id=self.flavor_type['flavor'].id)
        if servers:
            server = servers[0]
            LOG.info('Reusing existing server: ' + name)
            setattr(server, 'is_reuse', True)
            return server
        else:
            return None

    def get_networks_uuids(self):
        """
        Extract UUID of used networks. Order is important.

        :return: list of UUIDs of created networks
        """
        return [net['id'] for net in self.nets]

    def get_vlans(self):
        """
        Extract vlans of used networks. Order is important.

        :return: list of UUIDs of created networks
        """
        vlans = []
        for net in self.nets:
            assert (net['provider:network_type'] == 'vlan')
            vlans.append(net['provider:segmentation_id'])

        return vlans

    def setup(self):
        """
        Creates two networks and spawn a VM which act as a loop VM connected
        with the two networks.
        """
        self._setup_openstack_clients()

    def dispose(self, only_vm=False):
        """
        Deletes the created two networks and the VM.
        """
        for vm in self.vms:
            if vm:
                if not getattr(vm, 'is_reuse', True):
                    self.comp.delete_server(vm)
                else:
                    LOG.info('Server %s not removed since it is reused' % vm.name)

        for port in self.created_ports:
            self.__delete_port(port)

        if not only_vm:
            for net in self.nets:
                if 'is_reuse' in net and not net['is_reuse']:
                    self.__delete_net(net)
                else:
                    LOG.info('Network %s not removed since it is reused' % (net['name']))

            if not self.flavor_type['is_reuse']:
                self.__delete_flavor(self.flavor_type['flavor'])


class EXTStageClient(BasicStageClient):
    def __init__(self, config, cred):
        super(EXTStageClient, self).__init__(config, cred)

    def setup(self):
        super(EXTStageClient, self).setup()

        # Lookup two existing networks
        for net_name in [self.config.external_networks.left, self.config.external_networks.right]:
            net = self._lookup_network(net_name)
            if net:
                self.nets.append(net)
            else:
                raise StageClientException('Existing network {} cannot be found.'.format(net_name))


class PVPStageClient(BasicStageClient):
    def __init__(self, config, cred):
        super(PVPStageClient, self).__init__(config, cred)

    def get_end_port_macs(self):
        vm_ids = map(lambda vm: vm.id, self.vms)
        port_macs = []
        for index, net in enumerate(self.nets):
            vm_mac_map = {port['device_id']: port['mac_address'] for port in self.ports[net['id']]}
            port_macs.append([vm_mac_map[vm_id] for vm_id in vm_ids])
        return port_macs

    def setup(self):
        super(PVPStageClient, self).setup()
        self._setup_resources()

        # Create two networks
        nets = self.config.internal_networks
        self.nets.extend([self._create_net(**n) for n in [nets.left, nets.right]])

        az_list = self.comp.get_enabled_az_host_list(required_count=1)
        if not az_list:
            raise Exception('Not enough hosts found.')

        az = az_list[0]
        self.compute_nodes.add(az)
        for chain_index in xrange(self.config.service_chain_count):
            name = self.config.loop_vm_name + str(chain_index)
            reusable_vm = self.get_reusable_vm(name, self.nets, az)
            if reusable_vm:
                self.vms.append(reusable_vm)
            else:
                config_file = self.get_config_file(chain_index,
                                                   self.config.generator_config.src_device.mac,
                                                   self.config.generator_config.dst_device.mac)

                ports = [self._create_port(net) for net in self.nets]
                self.created_ports.extend(ports)
                self.vms.append(self._create_server(name, ports, az, config_file))
        self._ensure_vms_active()
        self.set_ports()


class PVVPStageClient(BasicStageClient):
    def __init__(self, config, cred):
        super(PVVPStageClient, self).__init__(config, cred)

    def get_end_port_macs(self):
        port_macs = []
        for index, net in enumerate(self.nets[:2]):
            vm_ids = map(lambda vm: vm.id, self.vms[index::2])
            vm_mac_map = {port['device_id']: port['mac_address'] for port in self.ports[net['id']]}
            port_macs.append([vm_mac_map[vm_id] for vm_id in vm_ids])
        return port_macs

    def setup(self):
        super(PVVPStageClient, self).setup()
        self._setup_resources()

        # Create two networks
        nets = self.config.internal_networks
        self.nets.extend([self._create_net(**n) for n in [nets.left, nets.right, nets.middle]])

        required_count = 2 if self.config.inter_node else 1
        az_list = self.comp.get_enabled_az_host_list(required_count=required_count)

        if not az_list:
            raise Exception('Not enough hosts found.')

        az1 = az2 = az_list[0]
        if self.config.inter_node:
            if len(az_list) > 1:
                az1 = az_list[0]
                az2 = az_list[1]
            else:
                # fallback to intra-node
                az1 = az2 = az_list[0]
                self.config.inter_node = False
                LOG.info('Using intra-node instead of inter-node.')

        self.compute_nodes.add(az1)
        self.compute_nodes.add(az2)

        # Create loop VMs
        for chain_index in xrange(self.config.service_chain_count):
            name0 = self.config.loop_vm_name + str(chain_index) + 'a'
            # Attach first VM to net0 and net2
            vm0_nets = self.nets[0::2]
            reusable_vm0 = self.get_reusable_vm(name0, vm0_nets, az1)

            name1 = self.config.loop_vm_name + str(chain_index) + 'b'
            # Attach second VM to net1 and net2
            vm1_nets = self.nets[1:]
            reusable_vm1 = self.get_reusable_vm(name1, vm1_nets, az2)

            if reusable_vm0 and reusable_vm1:
                self.vms.extend([reusable_vm0, reusable_vm1])
            else:
                vm0_port_net0 = self._create_port(vm0_nets[0])
                vm0_port_net2 = self._create_port(vm0_nets[1])

                vm1_port_net2 = self._create_port(vm1_nets[1])
                vm1_port_net1 = self._create_port(vm1_nets[0])

                self.created_ports.extend([vm0_port_net0,
                                           vm0_port_net2,
                                           vm1_port_net2,
                                           vm1_port_net1])

                # order of ports is important for sections below
                # order of MAC addresses needs to follow order of interfaces
                # TG0 (net0) -> VM0 (net2) -> VM1 (net2) -> TG1 (net1)
                config_file0 = self.get_config_file(chain_index,
                                                    self.config.generator_config.src_device.mac,
                                                    vm1_port_net2['mac_address'])
                config_file1 = self.get_config_file(chain_index,
                                                    vm0_port_net2['mac_address'],
                                                    self.config.generator_config.dst_device.mac)

                self.vms.append(self._create_server(name0,
                                                    [vm0_port_net0, vm0_port_net2],
                                                    az1,
                                                    config_file0))
                self.vms.append(self._create_server(name1,
                                                    [vm1_port_net2, vm1_port_net1],
                                                    az2,
                                                    config_file1))

        self._ensure_vms_active()
        self.set_ports()
