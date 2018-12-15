#!/usr/bin/env python
# Copyright 2018 Cisco Systems, Inc.  All rights reserved.
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

# This module takes care of chaining networks, ports and vms
#
"""NFVBENCH CHAIN DISCOVERY/STAGING.

This module takes care of staging/discovering all resources that are participating in a
benchmarking session: flavors, networks, ports, VNF instances.
If a resource is discovered with the same name, it will be reused.
Otherwise it will be created.

ChainManager: manages VM image, flavor, the staging discovery of all chains
              has 1 or more chains
Chain: manages one chain, has 2 or more networks and 1 or more instances
ChainNetwork: manages 1 network in a chain
ChainVnf: manages 1 VNF instance in a chain, has 2 ports
ChainVnfPort: manages 1 instance port

ChainManager-->Chain(*)
Chain-->ChainNetwork(*),ChainVnf(*)
ChainVnf-->ChainVnfPort(2)

Once created/discovered, instances are checked to be in the active state (ready to pass traffic)
Configuration parameters that will influence how these resources are staged/related:
- openstack or no openstack
- chain type
- number of chains
- number of VNF in each chain (PVP, PVVP)
- SRIOV and middle port SRIOV for port types
- whether networks are shared across chains or not

There is not traffic generation involved in this module.
"""
import os
import re
import time

from glanceclient.v2 import client as glanceclient
from neutronclient.neutron import client as neutronclient
from novaclient.client import Client

from attrdict import AttrDict
import compute
from log import LOG
from specs import ChainType

# Left and right index for network and port lists
LEFT = 0
RIGHT = 1
# Name of the VM config file
NFVBENCH_CFG_FILENAME = 'nfvbenchvm.conf'
# full pathame of the VM config in the VM
NFVBENCH_CFG_VM_PATHNAME = os.path.join('/etc/', NFVBENCH_CFG_FILENAME)
# full path of the boot shell script template file on the server where nfvbench runs
BOOT_SCRIPT_PATHNAME = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'nfvbenchvm',
                                    NFVBENCH_CFG_FILENAME)


class ChainException(Exception):
    """Exception while operating the chains."""

    pass

class NetworkEncaps(object):
    """Network encapsulation."""


class ChainFlavor(object):
    """Class to manage the chain flavor."""

    def __init__(self, flavor_name, flavor_dict, comp):
        """Create a flavor."""
        self.name = flavor_name
        self.comp = comp
        self.flavor = self.comp.find_flavor(flavor_name)
        self.reuse = False
        if self.flavor:
            self.reuse = True
            LOG.info("Reused flavor '%s'", flavor_name)
        else:
            extra_specs = flavor_dict.pop('extra_specs', None)

            self.flavor = comp.create_flavor(flavor_name,
                                             **flavor_dict)

            LOG.info("Created flavor '%s'", flavor_name)
            if extra_specs:
                self.flavor.set_keys(extra_specs)

    def delete(self):
        """Delete this flavor."""
        if not self.reuse and self.flavor:
            self.flavor.delete()
            LOG.info("Flavor '%s' deleted", self.name)


class ChainVnfPort(object):
    """A port associated to one VNF in the chain."""

    def __init__(self, name, vnf, chain_network, vnic_type):
        """Create or reuse a port on a given network.

        if vnf.instance is None the VNF instance is not reused and this ChainVnfPort instance must
        create a new port.
        Otherwise vnf.instance is a reused VNF instance and this ChainVnfPort instance must
        find an existing port to reuse that matches the port requirements: same attached network,
        instance, name, vnic type

        name: name for this port
        vnf: ChainVNf instance that owns this port
        chain_network: ChainNetwork instance where this port should attach
        vnic_type: required vnic type for this port
        """
        self.name = name
        self.vnf = vnf
        self.manager = vnf.manager
        self.reuse = False
        self.port = None
        if vnf.instance:
            # VNF instance is reused, we need to find an existing port that matches this instance
            # and network
            # discover ports attached to this instance
            port_list = self.manager.get_ports_from_network(chain_network)
            for port in port_list:
                if port['name'] != name:
                    continue
                if port['binding:vnic_type'] != vnic_type:
                    continue
                if port['device_id'] == vnf.get_uuid():
                    self.port = port
                    LOG.info('Reusing existing port %s mac=%s', name, port['mac_address'])
                    break
            else:
                raise ChainException('Cannot find matching port')
        else:
            # VNF instance is not created yet, we need to create a new port
            body = {
                "port": {
                    'name': name,
                    'network_id': chain_network.get_uuid(),
                    'binding:vnic_type': vnic_type
                }
            }
            port = self.manager.neutron_client.create_port(body)
            self.port = port['port']
            LOG.info('Created port %s', name)
            try:
                self.manager.neutron_client.update_port(self.port['id'], {
                    'port': {
                        'security_groups': [],
                        'port_security_enabled': False,
                    }
                })
                LOG.info('Security disabled on port %s', name)
            except Exception:
                LOG.info('Failed to disable security on port %s (ignored)', name)

    def get_mac(self):
        """Get the MAC address for this port."""
        return self.port['mac_address']

    def delete(self):
        """Delete this port instance."""
        if self.reuse or not self.port:
            return
        retry = 0
        while retry < self.manager.config.generic_retry_count:
            try:
                self.manager.neutron_client.delete_port(self.port['id'])
                LOG.info("Deleted port %s", self.name)
                return
            except Exception:
                retry += 1
                time.sleep(self.manager.config.generic_poll_sec)
        LOG.error('Unable to delete port: %s', self.name)


class ChainNetwork(object):
    """Could be a shared network across all chains or a chain private network."""

    def __init__(self, manager, network_config, chain_id=None, lookup_only=False):
        """Create a network for given chain.

        network_config: a dict containing the network properties
                        (segmentation_id and physical_network)
        chain_id: to which chain the networks belong.
                  a None value will mean that these networks are shared by all chains
        """
        self.manager = manager
        self.name = network_config.name
        self.segmentation_id = self._get_item(network_config.segmentation_id,
                                              chain_id, auto_index=True)
        self.physical_network = self._get_item(network_config.physical_network, chain_id)
        if chain_id is not None:
            self.name += str(chain_id)
        self.reuse = False
        self.network = None
        self.vlan = None
        try:
            self._setup(network_config, lookup_only)
        except Exception:
            if lookup_only:
                LOG.error("Cannot find network %s", self.name)
            else:
                LOG.error("Error creating network %s", self.name)
            self.delete()
            raise

    def _get_item(self, item_field, index, auto_index=False):
        """Retrieve an item from a list or a single value.

        item_field: can be None, a tuple of a single value
        index: if None is same as 0, else is the index for a chain
        auto_index: if true will automatically get the final value by adding the
                    index to the base value (if full list not provided)

        If the item_field is not a tuple, it is considered same as a tuple with same value at any
        index.
        If a list is provided, its length must be > index
        """
        if not item_field:
            return None
        if index is None:
            index = 0
        if isinstance(item_field, tuple):
            try:
                return item_field[index]
            except IndexError:
                raise ChainException("List %s is too short for chain index %d" %
                                     (str(item_field), index))
        # single value is configured
        if auto_index:
            return item_field + index
        return item_field

    def _setup(self, network_config, lookup_only):
        # Lookup if there is a matching network with same name
        networks = self.manager.neutron_client.list_networks(name=self.name)
        if networks['networks']:
            network = networks['networks'][0]
            # a network of same name already exists, we need to verify it has the same
            # characteristics
            if self.segmentation_id:
                if network['provider:segmentation_id'] != self.segmentation_id:
                    raise ChainException("Mismatch of 'segmentation_id' for reused "
                                         "network '{net}'. Network has id '{seg_id1}', "
                                         "configuration requires '{seg_id2}'."
                                         .format(net=self.name,
                                                 seg_id1=network['provider:segmentation_id'],
                                                 seg_id2=self.segmentation_id))

            if self.physical_network:
                if network['provider:physical_network'] != self.physical_network:
                    raise ChainException("Mismatch of 'physical_network' for reused "
                                         "network '{net}'. Network has '{phys1}', "
                                         "configuration requires '{phys2}'."
                                         .format(net=self.name,
                                                 phys1=network['provider:physical_network'],
                                                 phys2=self.physical_network))

            LOG.info('Reusing existing network %s', self.name)
            self.reuse = True
            self.network = network
        else:
            if lookup_only:
                raise ChainException('Network %s not found' % self.name)
            body = {
                'network': {
                    'name': self.name,
                    'admin_state_up': True
                    }
            }
            if network_config.network_type:
                body['network']['provider:network_type'] = network_config.network_type
            if self.segmentation_id:
                body['network']['provider:segmentation_id'] = self.segmentation_id
            if self.physical_network:
                body['network']['provider:physical_network'] = self.physical_network
            self.network = self.manager.neutron_client.create_network(body)['network']
            body = {
                'subnet': {'name': network_config.subnet,
                           'cidr': network_config.cidr,
                           'network_id': self.network['id'],
                           'enable_dhcp': False,
                           'ip_version': 4,
                           'dns_nameservers': []}
            }
            subnet = self.manager.neutron_client.create_subnet(body)['subnet']
            # add subnet id to the network dict since it has just been added
            self.network['subnets'] = [subnet['id']]
            LOG.info('Created network: %s', self.name)

    def get_uuid(self):
        """
        Extract UUID of this network.

        :return: UUID of this network
        """
        return self.network['id']

    def get_vlan(self):
        """
        Extract vlan for this network.

        :return: vlan ID for this network
        """
        if self.network['provider:network_type'] != 'vlan':
            raise ChainException('Trying to retrieve VLAN id for non VLAN network')
        return self.network['provider:segmentation_id']

    def get_vxlan(self):
        """
        Extract VNI for this network.

        :return: VNI ID for this network
        """
        if 'vxlan' not in self.network['provider:network_type']:
            raise ChainException('Trying to retrieve VNI for non VXLAN network')
        return self.network['provider:segmentation_id']

    def delete(self):
        """Delete this network."""
        if not self.reuse and self.network:
            retry = 0
            while retry < self.manager.config.generic_retry_count:
                try:
                    self.manager.neutron_client.delete_network(self.network['id'])
                    LOG.info("Deleted network: %s", self.name)
                    return
                except Exception:
                    retry += 1
                    LOG.info('Error deleting network %s (retry %d/%d)...',
                             self.name,
                             retry,
                             self.manager.config.generic_retry_count)
                    time.sleep(self.manager.config.generic_poll_sec)
            LOG.error('Unable to delete network: %s', self.name)


class ChainVnf(object):
    """A class to represent a VNF in a chain."""

    def __init__(self, chain, vnf_id, networks):
        """Reuse a VNF instance with same characteristics or create a new VNF instance.

        chain: the chain where this vnf belongs
        vnf_id: indicates the index of this vnf in its chain (first vnf=0)
        networks: the list of all networks (ChainNetwork) of the current chain
        """
        self.manager = chain.manager
        self.chain = chain
        self.vnf_id = vnf_id
        self.name = self.manager.config.loop_vm_name + str(chain.chain_id)
        if len(networks) > 2:
            # we will have more than 1 VM in each chain
            self.name += '-' + str(vnf_id)
        self.ports = []
        self.status = None
        self.instance = None
        self.reuse = False
        self.host_ip = None
        try:
            # the vnf_id is conveniently also the starting index in networks
            # for the left and right networks associated to this VNF
            self._setup(networks[vnf_id:vnf_id + 2])
        except Exception:
            LOG.error("Error creating VNF %s", self.name)
            self.delete()
            raise

    def _get_vm_config(self, remote_mac_pair):
        config = self.manager.config
        devices = self.manager.generator_config.devices
        with open(BOOT_SCRIPT_PATHNAME, 'r') as boot_script:
            content = boot_script.read()
        g1cidr = devices[LEFT].get_gw_ip(self.chain.chain_id) + '/8'
        g2cidr = devices[RIGHT].get_gw_ip(self.chain.chain_id) + '/8'
        vm_config = {
            'forwarder': config.vm_forwarder,
            'intf_mac1': self.ports[LEFT].get_mac(),
            'intf_mac2': self.ports[RIGHT].get_mac(),
            'tg_gateway1_ip': devices[LEFT].tg_gateway_ip_addrs,
            'tg_gateway2_ip': devices[RIGHT].tg_gateway_ip_addrs,
            'tg_net1': devices[LEFT].ip_addrs,
            'tg_net2': devices[RIGHT].ip_addrs,
            'vnf_gateway1_cidr': g1cidr,
            'vnf_gateway2_cidr': g2cidr,
            'tg_mac1': remote_mac_pair[0],
            'tg_mac2': remote_mac_pair[1]
        }
        return content.format(**vm_config)

    def _get_vnic_type(self, port_index):
        """Get the right vnic type for given port indexself.

        If SR-IOV is speficied, middle ports in multi-VNF chains
        can use vswitch or SR-IOV based on config.use_sriov_middle_net
        """
        if self.manager.config.sriov:
            chain_length = self.chain.get_length()
            if self.manager.config.use_sriov_middle_net or chain_length == 1:
                return 'direct'
            if self.vnf_id == 0 and port_index == 0:
                # first VNF in chain must use sriov for left port
                return 'direct'
            if (self.vnf_id == chain_length - 1) and (port_index == 1):
                # last VNF in chain must use sriov for right port
                return 'direct'
        return 'normal'

    def _setup(self, networks):
        flavor_id = self.manager.flavor.flavor.id
        # Check if we can reuse an instance with same name
        for instance in self.manager.existing_instances:
            if instance.name == self.name:
                # Verify that other instance characteristics match
                if instance.flavor['id'] != flavor_id:
                    self._reuse_exception('Flavor mismatch')
                if instance.status != "ACTIVE":
                    self._reuse_exception('Matching instance is not in ACTIVE state')
                # The 2 networks for this instance must also be reused
                if not networks[LEFT].reuse:
                    self._reuse_exception('network %s is new' % networks[LEFT].name)
                if not networks[RIGHT].reuse:
                    self._reuse_exception('network %s is new' % networks[RIGHT].name)
                # instance.networks have the network names as keys:
                # {'nfvbench-rnet0': ['192.168.2.10'], 'nfvbench-lnet0': ['192.168.1.8']}
                if networks[LEFT].name not in instance.networks:
                    self._reuse_exception('Left network mismatch')
                if networks[RIGHT].name not in instance.networks:
                    self._reuse_exception('Right network mismatch')

                self.reuse = True
                self.instance = instance
                LOG.info('Reusing existing instance %s on %s',
                         self.name, self.get_hypervisor_name())
        # create or reuse/discover 2 ports per instance
        self.ports = [ChainVnfPort(self.name + '-' + str(index),
                                   self,
                                   networks[index],
                                   self._get_vnic_type(index)) for index in [0, 1]]
        # if no reuse, actual vm creation is deferred after all ports in the chain are created
        # since we need to know the next mac in a multi-vnf chain

    def create_vnf(self, remote_mac_pair):
        """Create the VNF instance if it does not already exist."""
        if self.instance is None:
            port_ids = [{'port-id': vnf_port.port['id']}
                        for vnf_port in self.ports]
            vm_config = self._get_vm_config(remote_mac_pair)
            az = self.manager.placer.get_required_az()
            server = self.manager.comp.create_server(self.name,
                                                     self.manager.image_instance,
                                                     self.manager.flavor.flavor,
                                                     None,
                                                     port_ids,
                                                     None,
                                                     avail_zone=az,
                                                     user_data=None,
                                                     config_drive=True,
                                                     files={NFVBENCH_CFG_VM_PATHNAME: vm_config})
            if server:
                self.instance = server
                if self.manager.placer.is_resolved():
                    LOG.info('Created instance %s on %s', self.name, az)
                else:
                    # the location is undetermined at this point
                    # self.get_hypervisor_name() will return None
                    LOG.info('Created instance %s - waiting for placement resolution...', self.name)
                    # here we MUST wait until this instance is resolved otherwise subsequent
                    # VNF creation can be placed in other hypervisors!
                    config = self.manager.config
                    max_retries = (config.check_traffic_time_sec +
                                   config.generic_poll_sec - 1) / config.generic_poll_sec
                    retry = 0
                    for retry in range(max_retries):
                        status = self.get_status()
                        if status == 'ACTIVE':
                            hyp_name = self.get_hypervisor_name()
                            LOG.info('Instance %s is active and has been placed on %s',
                                     self.name, hyp_name)
                            self.manager.placer.register_full_name(hyp_name)
                            break
                        if status == 'ERROR':
                            raise ChainException('Instance %s creation error: %s' %
                                                 (self.name,
                                                  self.instance.fault['message']))
                        LOG.info('Waiting for instance %s to become active (retry %d/%d)...',
                                 self.name, retry + 1, max_retries + 1)
                        time.sleep(config.generic_poll_sec)
                    else:
                        # timing out
                        LOG.error('Instance %s creation timed out', self.name)
                        raise ChainException('Instance %s creation timed out' % self.name)
                self.reuse = False
            else:
                raise ChainException('Unable to create instance: %s' % (self.name))

    def _reuse_exception(self, reason):
        raise ChainException('Instance %s cannot be reused (%s)' % (self.name, reason))

    def get_status(self):
        """Get the statis of this instance."""
        if self.instance.status != 'ACTIVE':
            self.instance = self.manager.comp.poll_server(self.instance)
        return self.instance.status

    def get_hostname(self):
        """Get the hypervisor host name running this VNF instance."""
        return getattr(self.instance, 'OS-EXT-SRV-ATTR:hypervisor_hostname')

    def get_host_ip(self):
        """Get the IP address of the host where this instance runs.

        return: the IP address
        """
        if not self.host_ip:
            self.host_ip = self.manager.comp.get_hypervisor(self.get_hostname()).host_ip
        return self.host_ip

    def get_hypervisor_name(self):
        """Get hypervisor name (az:hostname) for this VNF instance."""
        if self.instance:
            az = getattr(self.instance, 'OS-EXT-AZ:availability_zone')
            hostname = self.get_hostname()
            if az:
                return az + ':' + hostname
            return hostname
        return None

    def get_uuid(self):
        """Get the uuid for this instance."""
        return self.instance.id

    def delete(self, forced=False):
        """Delete this VNF instance."""
        if self.reuse:
            LOG.info("Instance %s not deleted (reused)", self.name)
        else:
            if self.instance:
                self.manager.comp.delete_server(self.instance)
                LOG.info("Deleted instance %s", self.name)
            for port in self.ports:
                port.delete()

class Chain(object):
    """A class to manage a single chain.

    Can handle any type of chain (EXT, PVP, PVVP)
    """

    def __init__(self, chain_id, manager):
        """Create a new chain.

        chain_id: chain index (first chain is 0)
        manager: the chain manager that owns all chains
        """
        self.chain_id = chain_id
        self.manager = manager
        self.encaps = manager.encaps
        self.networks = []
        self.instances = []
        try:
            self.networks = manager.get_networks(chain_id)
            # For external chain VNFs can only be discovered from their MAC addresses
            # either from config or from ARP
            if manager.config.service_chain != ChainType.EXT:
                for chain_instance_index in range(self.get_length()):
                    self.instances.append(ChainVnf(self,
                                                   chain_instance_index,
                                                   self.networks))
                # at this point new VNFs are not created yet but
                # verify that all discovered VNFs are on the same hypervisor
                self._check_hypervisors()
                # now that all VNF ports are created we need to calculate the
                # left/right remote MAC for each VNF in the chain
                # before actually creating the VNF itself
                rem_mac_pairs = self._get_remote_mac_pairs()
                for instance in self.instances:
                    rem_mac_pair = rem_mac_pairs.pop(0)
                    instance.create_vnf(rem_mac_pair)
        except Exception:
            self.delete()
            raise

    def _check_hypervisors(self):
        common_hypervisor = None
        for instance in self.instances:
            # get the full hypervizor name (az:compute)
            hname = instance.get_hypervisor_name()
            if hname:
                if common_hypervisor:
                    if hname != common_hypervisor:
                        raise ChainException('Discovered instances on different hypervisors:'
                                             ' %s and %s' % (hname, common_hypervisor))
                else:
                    common_hypervisor = hname
        if common_hypervisor:
            # check that the common hypervisor name matchs the requested hypervisor name
            # and set the name to be used by all future instances (if any)
            if not self.manager.placer.register_full_name(common_hypervisor):
                raise ChainException('Discovered hypervisor placement %s is incompatible' %
                                     common_hypervisor)

    def get_length(self):
        """Get the number of VNF in the chain."""
        return len(self.networks) - 1

    def _get_remote_mac_pairs(self):
        """Get the list of remote mac pairs for every VNF in the chain.

        Traverse the chain from left to right and establish the
        left/right remote MAC for each VNF in the chainself.

        PVP case is simpler:
        mac sequence: tg_src_mac, vm0-mac0, vm0-mac1, tg_dst_mac
        must produce [[tg_src_mac, tg_dst_mac]] or looking at index in mac sequence: [[0, 3]]
        the mac pair is what the VNF at that position (index 0) sees as next hop mac left and right

        PVVP:
        tg_src_mac, vm0-mac0, vm0-mac1, vm1-mac0, vm1-mac1, tg_dst_mac
        Must produce the following list:
        [[tg_src_mac, vm1-mac0], [vm0-mac1, tg_dst_mac]] or index: [[0, 3], [2, 5]]

        General case with 3 VMs in chain, the list of consecutive macs (left to right):
        tg_src_mac, vm0-mac0, vm0-mac1, vm1-mac0, vm1-mac1, vm2-mac0, vm2-mac1, tg_dst_mac
        Must produce the following list:
        [[tg_src_mac, vm1-mac0], [vm0-mac1, vm2-mac0], [vm1-mac1, tg_dst_mac]]
        or index: [[0, 3], [2, 5], [4, 7]]

        The series pattern is pretty clear: [[n, n+3],... ] where n is multiple of 2
        """
        # line up all mac from left to right
        mac_seq = [self.manager.generator_config.devices[LEFT].mac]
        for instance in self.instances:
            mac_seq.append(instance.ports[0].get_mac())
            mac_seq.append(instance.ports[1].get_mac())
        mac_seq.append(self.manager.generator_config.devices[RIGHT].mac)
        base = 0
        rem_mac_pairs = []
        for _ in self.instances:
            rem_mac_pairs.append([mac_seq[base], mac_seq[base + 3]])
            base += 2
        return rem_mac_pairs

    def get_instances(self):
        """Return all instances for this chain."""
        return self.instances

    def get_vlan(self, port_index):
        """Get the VLAN id on a given port.

        port_index: left port is 0, right port is 1
        return: the vlan_id or None if there is no vlan tagging
        """
        # for port 1 we need to return the VLAN of the last network in the chain
        # The networks array contains 2 networks for PVP [left, right]
        # and 3 networks in the case of PVVP [left.middle,right]
        if port_index:
            # this will pick the last item in array
            port_index = -1
        return self.networks[port_index].get_vlan()

    def get_vxlan(self, port_index):
        """Get the VXLAN id on a given port.

        port_index: left port is 0, right port is 1
        return: the vxlan_id or None if there is no vxlan
        """
        # for port 1 we need to return the VLAN of the last network in the chain
        # The networks array contains 2 networks for PVP [left, right]
        # and 3 networks in the case of PVVP [left.middle,right]
        if port_index:
            # this will pick the last item in array
            port_index = -1
        return self.networks[port_index].get_vxlan()

    def get_dest_mac(self, port_index):
        """Get the dest MAC on a given port.

        port_index: left port is 0, right port is 1
        return: the dest MAC
        """
        if port_index:
            # for right port, use the right port MAC of the last (right most) VNF In chain
            return self.instances[-1].ports[1].get_mac()
        # for left port use the left port MAC of the first (left most) VNF in chain
        return self.instances[0].ports[0].get_mac()

    def get_network_uuids(self):
        """Get UUID of networks in this chain from left to right (order is important).

        :return: list of UUIDs of networks (2 or 3 elements)
        """
        return [net['id'] for net in self.networks]

    def get_host_ips(self):
        """Return the IP adresss(es) of the host compute nodes used for this chain.

        :return: a list of 1 or 2 IP addresses
        """
        return [vnf.get_host_ip() for vnf in self.instances]

    def get_compute_nodes(self):
        """Return the name of the host compute nodes used for this chain.

        :return: a list of 1 host name in the az:host format
        """
        # Since all chains go through the same compute node(s) we can just retrieve the
        # compute node name(s) for the first chain
        return [vnf.get_hypervisor_name() for vnf in self.instances]

    def delete(self):
        """Delete this chain."""
        for instance in self.instances:
            instance.delete()
        # only delete if these are chain private networks (not shared)
        if not self.manager.config.service_chain_shared_net:
            for network in self.networks:
                network.delete()


class InstancePlacer(object):
    """A class to manage instance placement for all VNFs in all chains.

    A full az string is made of 2 parts AZ and hypervisor.
    The placement is resolved when both parts az and hypervisor names are known.
    """

    def __init__(self, req_az, req_hyp):
        """Create a new instance placer.

        req_az: requested AZ (can be None or empty if no preference)
        req_hyp: requested hypervisor name (can be None of empty if no preference)
                 can be any of 'nova:', 'comp1', 'nova:comp1'
                 if it is a list, only the first item is used (backward compatibility in config)

        req_az is ignored if req_hyp has an az part
        all other parts beyond the first 2 are ignored in req_hyp
        """
        # if passed a list just pick the first item
        if req_hyp and isinstance(req_hyp, list):
            req_hyp = req_hyp[0]
        # only pick first part of az
        if req_az and ':' in req_az:
            req_az = req_az.split(':')[0]
        if req_hyp:
            # check if requested hypervisor string has an AZ part
            split_hyp = req_hyp.split(':')
            if len(split_hyp) > 1:
                # override the AZ part and hypervisor part
                req_az = split_hyp[0]
                req_hyp = split_hyp[1]
        self.requested_az = req_az if req_az else ''
        self.requested_hyp = req_hyp if req_hyp else ''
        # Nova can accept AZ only (e.g. 'nova:', use any hypervisor in that AZ)
        # or hypervisor only (e.g. ':comp1')
        # or both (e.g. 'nova:comp1')
        if req_az:
            self.required_az = req_az + ':' + self.requested_hyp
        else:
            # need to insert a ':' so nova knows this is the hypervisor name
            self.required_az = ':' + self.requested_hyp if req_hyp else ''
        # placement is resolved when both AZ and hypervisor names are known and set
        self.resolved = self.requested_az != '' and self.requested_hyp != ''

    def get_required_az(self):
        """Return the required az (can be resolved or not)."""
        return self.required_az

    def register_full_name(self, discovered_az):
        """Verify compatibility and register a discovered hypervisor full name.

        discovered_az: a discovered AZ in az:hypervisor format
        return: True if discovered_az is compatible and set
                False if discovered_az is not compatible
        """
        if self.resolved:
            return discovered_az == self.required_az

        # must be in full az format
        split_daz = discovered_az.split(':')
        if len(split_daz) != 2:
            return False
        if self.requested_az and self.requested_az != split_daz[0]:
            return False
        if self.requested_hyp and self.requested_hyp != split_daz[1]:
            return False
        self.required_az = discovered_az
        self.resolved = True
        return True

    def is_resolved(self):
        """Check if the full AZ is resolved.

        return: True if resolved
        """
        return self.resolved


class ChainManager(object):
    """A class for managing all chains for a given run.

    Supports openstack or no openstack.
    Supports EXT, PVP and PVVP chains.
    """

    def __init__(self, chain_runner):
        """Create a chain manager to take care of discovering or bringing up the requested chains.

        A new instance must be created every time a new config is used.
        config: the nfvbench config to use
        cred: openstack credentials to use of None if there is no openstack
        """
        self.chain_runner = chain_runner
        self.config = chain_runner.config
        self.generator_config = chain_runner.traffic_client.generator_config
        self.chains = []
        self.image_instance = None
        self.image_name = None
        # Left and right networks shared across all chains (only if shared)
        self.networks = []
        self.encaps = None
        self.flavor = None
        self.comp = None
        self.nova_client = None
        self.neutron_client = None
        self.glance_client = None
        self.existing_instances = []
        # existing ports keyed by the network uuid they belong to
        self._existing_ports = {}
        config = self.config
        self.openstack = (chain_runner.cred is not None) and not config.l2_loopback
        self.chain_count = config.service_chain_count
        self.az = None
        if self.openstack:
            # openstack only
            session = chain_runner.cred.get_session()
            self.nova_client = Client(2, session=session)
            self.neutron_client = neutronclient.Client('2.0', session=session)
            self.glance_client = glanceclient.Client('2', session=session)
            self.comp = compute.Compute(self.nova_client,
                                        self.glance_client,
                                        config)
            try:
                if config.service_chain != ChainType.EXT:
                    self.placer = InstancePlacer(config.availability_zone, config.compute_nodes)
                    self._setup_image()
                    self.flavor = ChainFlavor(config.flavor_type, config.flavor, self.comp)
                    # Get list of all existing instances to check if some instances can be reused
                    self.existing_instances = self.comp.get_server_list()
                # If networks are shared across chains, get the list of networks
                if config.service_chain_shared_net:
                    self.networks = self.get_networks()
                # Reuse/create chains
                for chain_id in range(self.chain_count):
                    self.chains.append(Chain(chain_id, self))
                if config.service_chain == ChainType.EXT:
                    # if EXT and no ARP we need to read dest MACs from config
                    if config.no_arp:
                        self._get_dest_macs_from_config()
                else:
                    # Make sure all instances are active before proceeding
                    self._ensure_instances_active()
            except Exception:
                self.delete()
                raise
        else:
            # no openstack, no need to create chains

            if not config.l2_loopback and config.no_arp:
                self._get_dest_macs_from_config()
            if config.vlan_tagging:
                # make sure there at least as many entries as chains in each left/right list
                if len(config.vlans) != 2:
                    raise ChainException('The config vlans property must be a list '
                                         'with 2 lists of VLAN IDs')
                re_vlan = "[0-9]*$"
                self.vlans = [self._check_list('vlans[0]', config.vlans[0], re_vlan),
                              self._check_list('vlans[1]', config.vlans[1], re_vlan)]
            if config.vxlan:
                raise ChainException('VxLAN is only supported with OpenStack')

    def _get_dest_macs_from_config(self):
        re_mac = "[0-9a-fA-F]{2}([-:])[0-9a-fA-F]{2}(\\1[0-9a-fA-F]{2}){4}$"
        tg_config = self.config.traffic_generator
        self.dest_macs = [self._check_list("mac_addrs_left",
                                           tg_config.mac_addrs_left, re_mac),
                          self._check_list("mac_addrs_right",
                                           tg_config.mac_addrs_right, re_mac)]

    def _check_list(self, list_name, ll, pattern):
        # if it is a single int or mac, make it a list of 1 int
        if isinstance(ll, (int, str)):
            ll = [ll]
        for item in ll:
            if not re.match(pattern, str(item)):
                raise ChainException("Invalid format '{item}' specified in {fname}"
                                     .format(item=item, fname=list_name))
        # must have at least 1 element
        if not ll:
            raise ChainException('%s cannot be empty' % (list_name))
        # for shared network, if 1 element is passed, replicate it as many times
        # as chains
        if self.config.service_chain_shared_net and len(ll) == 1:
            ll = [ll[0]] * self.chain_count

        # number of elements musty be the number of chains
        elif len(ll) < self.chain_count:
            raise ChainException('%s=%s must be a list with %d elements per chain' %
                                 (list_name, ll, self.chain_count))
        return ll

    def _setup_image(self):
        # To avoid reuploading image in server mode, check whether image_name is set or not
        if self.image_name:
            self.image_instance = self.comp.find_image(self.image_name)
        if self.image_instance:
            LOG.info("Reusing image %s", self.image_name)
        else:
            image_name_search_pattern = r'(nfvbenchvm-\d+(\.\d+)*).qcow2'
            if self.config.vm_image_file:
                match = re.search(image_name_search_pattern, self.config.vm_image_file)
                if match:
                    self.image_name = match.group(1)
                    LOG.info('Using provided VM image file %s', self.config.vm_image_file)
                else:
                    raise ChainException('Provided VM image file name %s must start with '
                                         '"nfvbenchvm-<version>"' % self.config.vm_image_file)
            else:
                pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                for f in os.listdir(pkg_root):
                    if re.search(image_name_search_pattern, f):
                        self.config.vm_image_file = pkg_root + '/' + f
                        self.image_name = f.replace('.qcow2', '')
                        LOG.info('Found built-in VM image file %s', f)
                        break
                else:
                    raise ChainException('Cannot find any built-in VM image file.')
            if self.image_name:
                self.image_instance = self.comp.find_image(self.image_name)
            if not self.image_instance:
                LOG.info('Uploading %s', self.image_name)
                res = self.comp.upload_image_via_url(self.image_name,
                                                     self.config.vm_image_file)

                if not res:
                    raise ChainException('Error uploading image %s from %s. ABORTING.' %
                                         (self.image_name, self.config.vm_image_file))
                LOG.info('Image %s successfully uploaded.', self.image_name)
                self.image_instance = self.comp.find_image(self.image_name)

    def _ensure_instances_active(self):
        instances = []
        for chain in self.chains:
            instances.extend(chain.get_instances())
        initial_instance_count = len(instances)
        max_retries = (self.config.check_traffic_time_sec +
                       self.config.generic_poll_sec - 1) / self.config.generic_poll_sec
        retry = 0
        while instances:
            remaining_instances = []
            for instance in instances:
                status = instance.get_status()
                if status == 'ACTIVE':
                    LOG.info('Instance %s is ACTIVE on %s',
                             instance.name, instance.get_hypervisor_name())
                    continue
                if status == 'ERROR':
                    raise ChainException('Instance %s creation error: %s' %
                                         (instance.name,
                                          instance.instance.fault['message']))
                remaining_instances.append(instance)
            if not remaining_instances:
                break
            retry += 1
            if retry >= max_retries:
                raise ChainException('Time-out: %d/%d instances still not active' %
                                     (len(remaining_instances), initial_instance_count))
            LOG.info('Waiting for %d/%d instance to become active (retry %d/%d)...',
                     len(remaining_instances), initial_instance_count,
                     retry, max_retries)
            instances = remaining_instances
            time.sleep(self.config.generic_poll_sec)
        if initial_instance_count:
            LOG.info('All instances are active')

    def get_networks(self, chain_id=None):
        """Get the networks for given EXT, PVP or PVVP chain.

        For EXT packet path, these networks must pre-exist.
        For PVP, PVVP these networks will be created if they do not exist.
        chain_id: to which chain the networks belong.
                  a None value will mean that these networks are shared by all chains
        """
        if self.networks:
            # the only case where self.networks exists is when the networks are shared
            # across all chains
            return self.networks
        if self.config.service_chain == ChainType.EXT:
            lookup_only = True
            ext_net = self.config.external_networks
            net_cfg = [AttrDict({'name': name,
                                 'segmentation_id': None,
                                 'physical_network': None})
                       for name in [ext_net.left, ext_net.right]]
            # segmentation id and subnet should be discovered from neutron
        else:
            lookup_only = False
            int_nets = self.config.internal_networks
            # VLAN and VxLAN
            if self.config.service_chain == ChainType.PVP:
                net_cfg = [int_nets.left, int_nets.right]
            else:
                net_cfg = [int_nets.left, int_nets.middle, int_nets.right]
        networks = []
        try:
            for cfg in net_cfg:
                networks.append(ChainNetwork(self, cfg, chain_id, lookup_only=lookup_only))
        except Exception:
            # need to cleanup all successful networks prior to bailing out
            for net in networks:
                net.delete()
            raise
        return networks

    def get_existing_ports(self):
        """Get the list of existing ports.

        Lazy retrieval of ports as this can be costly if there are lots of ports and
        is only needed when VM and network are being reused.

        return: a dict of list of neutron ports indexed by the network uuid they are attached to

        Each port is a dict with fields such as below:
        {'allowed_address_pairs': [], 'extra_dhcp_opts': [],
         'updated_at': '2018-10-06T07:15:35Z', 'device_owner': 'compute:nova',
         'revision_number': 10, 'port_security_enabled': False, 'binding:profile': {},
         'fixed_ips': [{'subnet_id': '6903a3b3-49a1-4ba4-8259-4a90e7a44b21',
         'ip_address': '192.168.1.4'}], 'id': '3dcb9cfa-d82a-4dd1-85a1-fd8284b52d72',
         'security_groups': [],
         'binding:vif_details': {'vhostuser_socket': '/tmp/3dcb9cfa-d82a-4dd1-85a1-fd8284b52d72',
                                 'vhostuser_mode': 'server'},
         'binding:vif_type': 'vhostuser',
         'mac_address': 'fa:16:3e:3c:63:04',
         'project_id': '977ac76a63d7492f927fa80e86baff4c',
         'status': 'ACTIVE',
         'binding:host_id': 'a20-champagne-compute-1',
         'description': '',
         'device_id': 'a98e2ad2-5371-4aa5-a356-8264a970ce4b',
         'name': 'nfvbench-loop-vm0-0', 'admin_state_up': True,
         'network_id': '3ea5fd88-278f-4d9d-b24d-1e443791a055',
         'tenant_id': '977ac76a63d7492f927fa80e86baff4c',
         'created_at': '2018-10-06T07:15:10Z',
         'binding:vnic_type': 'normal'}
        """
        if not self._existing_ports:
            LOG.info('Loading list of all ports...')
            existing_ports = self.neutron_client.list_ports()['ports']
            # place all ports in the dict keyed by the port network uuid
            for port in existing_ports:
                port_list = self._existing_ports.setdefault(port['network_id'], [])
                port_list.append(port)
            LOG.info("Loaded %d ports attached to %d networks",
                     len(existing_ports), len(self._existing_ports))
        return self._existing_ports

    def get_ports_from_network(self, chain_network):
        """Get the list of existing ports that belong to a network.

        Lazy retrieval of ports as this can be costly if there are lots of ports and
        is only needed when VM and network are being reused.

        chain_network: a ChainNetwork instance for which attached ports neeed to be retrieved
        return: list of neutron ports attached to requested network
        """
        return self.get_existing_ports().get(chain_network.get_uuid(), None)

    def get_host_ip_from_mac(self, mac):
        """Get the host IP address matching a MAC.

        mac: MAC address to look for
        return: the IP address of the host where the matching port runs or None if not found
        """
        # _existing_ports is a dict of list of ports indexed by network id
        for port_list in self.get_existing_ports().values():
            for port in port_list:
                try:
                    if port['mac_address'] == mac:
                        host_id = port['binding:host_id']
                        return self.comp.get_hypervisor(host_id).host_ip
                except KeyError:
                    pass
        return None

    def get_chain_vlans(self, port_index):
        """Get the list of per chain VLAN id on a given port.

        port_index: left port is 0, right port is 1
        return: a VLAN ID list indexed by the chain index or None if no vlan tagging
        """
        if self.chains:
            return [self.chains[chain_index].get_vlan(port_index)
                    for chain_index in range(self.chain_count)]
        # no openstack
        return self.vlans[port_index]

    def get_chain_vxlans(self, port_index):
        """Get the list of per chain VNIs id on a given port.

        port_index: left port is 0, right port is 1
        return: a VNIs ID list indexed by the chain index or None if no vlan tagging
        """
        if self.chains:
            return [self.chains[chain_index].get_vxlan(port_index)
                    for chain_index in range(self.chain_count)]
        # no openstack
        raise ChainException('VxLAN is only supported with OpenStack')

    def get_dest_macs(self, port_index):
        """Get the list of per chain dest MACs on a given port.

        Should not be called if EXT+ARP is used (in that case the traffic gen will
        have the ARP responses back from VNFs with the dest MAC to use).

        port_index: left port is 0, right port is 1
        return: a list of dest MACs indexed by the chain index
        """
        if self.chains and self.config.service_chain != ChainType.EXT:
            return [self.chains[chain_index].get_dest_mac(port_index)
                    for chain_index in range(self.chain_count)]
        # no openstack or EXT+no-arp
        return self.dest_macs[port_index]

    def get_host_ips(self):
        """Return the IP adresss(es) of the host compute nodes used for this run.

        :return: a list of 1 IP address
        """
        # Since all chains go through the same compute node(s) we can just retrieve the
        # compute node(s) for the first chain
        if self.chains:
            if self.config.service_chain != ChainType.EXT:
                return self.chains[0].get_host_ips()
            # in the case of EXT, the compute node must be retrieved from the port
            # associated to any of the dest MACs
            dst_macs = self.generator_config.get_dest_macs()
            # dest MAC on port 0, chain 0
            dst_mac = dst_macs[0][0]
            host_ip = self.get_host_ip_from_mac(dst_mac)
            if host_ip:
                LOG.info('Found compute node IP for EXT chain: %s', host_ip)
                return [host_ip]
        return []

    def get_compute_nodes(self):
        """Return the name of the host compute nodes used for this run.

        :return: a list of 0 or 1 host name in the az:host format
        """
        # Since all chains go through the same compute node(s) we can just retrieve the
        # compute node name(s) for the first chain
        if self.chains:
            # in the case of EXT, the compute node must be retrieved from the port
            # associated to any of the dest MACs
            return self.chains[0].get_compute_nodes()
        # no openstack = no chains
        return []

    def delete(self):
        """Delete resources for all chains."""
        for chain in self.chains:
            chain.delete()
        for network in self.networks:
            network.delete()
        if self.flavor:
            self.flavor.delete()
