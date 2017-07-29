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

'''Module for Openstack compute operations'''
from glanceclient import exc as glance_exception
import keystoneauth1
from log import LOG
import novaclient
import os
import time
import traceback


try:
    from glanceclient.openstack.common.apiclient.exceptions import NotFound as GlanceImageNotFound
except ImportError:
    from glanceclient.v1.apiclient.exceptions import NotFound as GlanceImageNotFound


class Compute(object):

    def __init__(self, nova_client, glance_client, neutron_client, config):
        self.novaclient = nova_client
        self.glance_client = glance_client
        self.neutronclient = neutron_client
        self.config = config

    def find_image(self, image_name):
        try:
            return next(self.glance_client.images.list(filters={'name': image_name}), None)
        except (novaclient.exceptions.NotFound, keystoneauth1.exceptions.http.NotFound,
                GlanceImageNotFound):
            pass
        return None

    def upload_image_via_url(self, final_image_name, image_file, retry_count=60):
        '''
        Directly uploads image to Nova via URL if image is not present
        '''
        retry = 0
        try:
            # check image is file/url based.
            file_prefix = "file://"
            image_location = image_file.split(file_prefix)[1]
            with open(image_location) as f_image:
                img = self.glance_client.images.create(name=str(final_image_name),
                                                       disk_format="qcow2",
                                                       container_format="bare",
                                                       visibility="public")
                self.glance_client.images.upload(img.id, image_data=f_image)
            # Check for the image in glance
            while img.status in ['queued', 'saving'] and retry < retry_count:
                img = self.glance_client.images.get(img.id)
                retry += 1
                LOG.debug("Image not yet active, retrying %s of %s...", retry, retry_count)
                time.sleep(self.config.generic_poll_sec)
            if img.status != 'active':
                LOG.error("Image uploaded but too long to get to active state")
                raise Exception("Image update active state timeout")
        except glance_exception.HTTPForbidden:
            LOG.error("Cannot upload image without admin access. Please make "
                      "sure the image is uploaded and is either public or owned by you.")
            return False
        except IOError:
            # catch the exception for file based errors.
            LOG.error("Failed while uploading the image. Please make sure the "
                      "image at the specified location %s is correct.", image_file)
            return False
        except keystoneauth1.exceptions.http.NotFound as exc:
            LOG.error("Authentication error while uploading the image:" + str(exc))
            return False
        except Exception:
            LOG.error(traceback.format_exc())
            LOG.error("Failed while uploading the image, please make sure the "
                      "cloud under test has the access to file: %s.", image_file)
            return False
        return True

    def delete_image(self, img_name):
        try:
            LOG.log("Deleting image %s...", img_name)
            img = self.glance_client.images.find(name=img_name)
            self.glance_client.images.delete(img.id)
        except Exception:
            LOG.error("Failed to delete the image %s.", img_name)
            return False

        return True

    # Remove keypair name from openstack if exists
    def remove_public_key(self, name):
        keypair_list = self.novaclient.keypairs.list()
        for key in keypair_list:
            if key.name == name:
                self.novaclient.keypairs.delete(name)
                LOG.info('Removed public key %s', name)
                break

    # Test if keypair file is present if not create it
    def create_keypair(self, name, private_key_pair_file):
        self.remove_public_key(name)
        keypair = self.novaclient.keypairs.create(name)
        # Now write the keypair to the file if requested
        if private_key_pair_file:
            kpf = os.open(private_key_pair_file,
                          os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(kpf, 'w') as kpf:
                kpf.write(keypair.private_key)
        return keypair

    # Add an existing public key to openstack
    def add_public_key(self, name, public_key_file):
        self.remove_public_key(name)
        # extract the public key from the file
        public_key = None
        try:
            with open(os.path.expanduser(public_key_file)) as pkf:
                public_key = pkf.read()
        except IOError as exc:
            LOG.error('Cannot open public key file %s: %s', public_key_file, exc)
            return None
        keypair = self.novaclient.keypairs.create(name, public_key)
        return keypair

    def init_key_pair(self, kp_name, ssh_access):
        '''Initialize the key pair for all test VMs
        if a key pair is specified in access, use that key pair else
        create a temporary key pair
        '''
        if ssh_access.public_key_file:
            return self.add_public_key(kp_name, ssh_access.public_key_file)
        else:
            keypair = self.create_keypair(kp_name, None)
            ssh_access.private_key = keypair.private_key
            return keypair

    def find_network(self, label):
        net = self.novaclient.networks.find(label=label)
        return net

    # Create a server instance with name vmname
    # and check that it gets into the ACTIVE state
    def create_server(self, vmname, image, flavor, key_name,
                      nic, sec_group, avail_zone=None, user_data=None,
                      config_drive=None, files=None):

        if sec_group:
            security_groups = [sec_group['id']]
        else:
            security_groups = None

        # Also attach the created security group for the test
        instance = self.novaclient.servers.create(name=vmname,
                                                  image=image,
                                                  flavor=flavor,
                                                  key_name=key_name,
                                                  nics=nic,
                                                  availability_zone=avail_zone,
                                                  userdata=user_data,
                                                  config_drive=config_drive,
                                                  files=files,
                                                  security_groups=security_groups)
        return instance

    def poll_server(self, instance):
        return self.novaclient.servers.get(instance.id)

    def get_server_list(self):
        servers_list = self.novaclient.servers.list()
        return servers_list

    def find_floating_ips(self):
        floating_ip = self.novaclient.floating_ips.list()
        return floating_ip

    def create_floating_ips(self, pool):
        return self.novaclient.floating_ips.create(pool)

    # Return the server network for a server
    def find_server_network(self, vmname):
        servers_list = self.get_server_list()
        for server in servers_list:
            if server.name == vmname and server.status == "ACTIVE":
                return server.networks
        return None

    # Returns True if server is present false if not.
    # Retry for a few seconds since after VM creation sometimes
    # it takes a while to show up
    def find_server(self, vmname, retry_count):
        for retry_attempt in range(retry_count):
            servers_list = self.get_server_list()
            for server in servers_list:
                if server.name == vmname and server.status == "ACTIVE":
                    return True
            # Sleep between retries
            LOG.debug("[%s] VM not yet found, retrying %s of %s...",
                      vmname, (retry_attempt + 1), retry_count)
            time.sleep(self.config.generic_poll_sec)
        LOG.error("[%s] VM not found, after %s attempts", vmname, retry_count)
        return False

    # Returns True if server is found and deleted/False if not,
    # retry the delete if there is a delay
    def delete_server_by_name(self, vmname):
        servers_list = self.get_server_list()
        for server in servers_list:
            if server.name == vmname:
                LOG.info('Deleting server %s', server)
                self.novaclient.servers.delete(server)
                return True
        return False

    def delete_server(self, server):
        self.novaclient.servers.delete(server)

    def find_flavor(self, flavor_type):
        try:
            flavor = self.novaclient.flavors.find(name=flavor_type)
            return flavor
        except Exception:
            return None

    def create_flavor(self, name, ram, vcpus, disk, ephemeral=0, override=False):
        if override:
            self.delete_flavor(name)
        return self.novaclient.flavors.create(name=name, ram=ram, vcpus=vcpus, disk=disk,
                                              ephemeral=ephemeral)

    def delete_flavor(self, flavor=None, name=None):
        try:
            if not flavor:
                flavor = self.find_flavor(name)
            flavor.delete()
            return True
        except Exception:
            return False

    def normalize_az_host(self, az, host):
        if not az:
            az = self.config.availability_zone
        return az + ':' + host

    def auto_fill_az(self, host_list, host):
        '''
        no az provided, if there is a host list we can auto-fill the az
        else we use the configured az if available
        else we return an error
        '''
        if host_list:
            for hyp in host_list:
                if hyp.host == host:
                    return self.normalize_az_host(hyp.zone, host)
            # no match on host
            LOG.error('Passed host name does not exist: ' + host)
            return None
        if self.config.availability_zone:
            return self.normalize_az_host(None, host)
        LOG.error('--hypervisor passed without an az and no az configured')
        return None

    def sanitize_az_host(self, host_list, az_host):
        '''
        host_list: list of hosts as retrieved from openstack (can be empty)
        az_host: either a host or a az:host string
        if a host, will check host is in the list, find the corresponding az and
                    return az:host
        if az:host is passed will check the host is in the list and az matches
        if host_list is empty, will return the configured az if there is no
                    az passed
        '''
        if ':' in az_host:
            # no host_list, return as is (no check)
            if not host_list:
                return az_host
            # if there is a host_list, extract and verify the az and host
            az_host_list = az_host.split(':')
            zone = az_host_list[0]
            host = az_host_list[1]
            for hyp in host_list:
                if hyp.host == host:
                    if hyp.zone == zone:
                        # matches
                        return az_host
                    # else continue - another zone with same host name?
            # no match
            LOG.error('No match for availability zone and host ' + az_host)
            return None
        else:
            return self.auto_fill_az(host_list, az_host)

    #
    #   Return a list of 0, 1 or 2 az:host
    #
    #   The list is computed as follows:
    #   The list of all hosts is retrieved first from openstack
    #        if this fails, checks and az auto-fill are disabled
    #
    #   If the user provides a list of hypervisors (--hypervisor)
    #       that list is checked and returned
    #
    #   If the user provides a configured az name (config.availability_zone)
    #       up to the first 2 hosts from the list that match the az are returned
    #
    #   If the user did not configure an az name
    #       up to the first 2 hosts from the list are returned
    #   Possible return values:
    #   [ az ]
    #   [ az:hyp ]
    #   [ az1:hyp1, az2:hyp2 ]
    #   []  if an error occurred (error message printed to console)
    #
    def get_az_host_list(self):
        avail_list = []
        host_list = []

        try:
            host_list = self.novaclient.services.list()
        except novaclient.exceptions.Forbidden:
            LOG.warning('Operation Forbidden: could not retrieve list of hosts'
                        ' (likely no permission)')

        for host in host_list:
            # this host must be a compute node
            if host.binary != 'nova-compute' or host.state != 'up':
                continue
            candidate = None
            if self.config.availability_zone:
                if host.zone == self.config.availability_zone:
                    candidate = self.normalize_az_host(None, host.host)
            else:
                candidate = self.normalize_az_host(host.zone, host.host)
            if candidate:
                avail_list.append(candidate)
                # pick first 2 matches at most
                if len(avail_list) == 2:
                    break

        # if empty we insert the configured az
        if not avail_list:

            if not self.config.availability_zone:
                LOG.error('Availability_zone must be configured')
            elif host_list:
                LOG.error('No host matching the selection for availability zone: ' +
                          self.config.availability_zone)
                avail_list = []
            else:
                avail_list = [self.config.availability_zone]
        return avail_list

    def get_enabled_az_host_list(self, required_count=1):
        """
        Check which hypervisors are enabled and on which compute nodes they are running.
        Pick required count of hosts.

        :param required_count: count of compute-nodes to return
        :return: list of enabled available compute nodes
        """
        host_list = []
        hypervisor_list = []

        try:
            hypervisor_list = self.novaclient.hypervisors.list()
            host_list = self.novaclient.services.list()
        except novaclient.exceptions.Forbidden:
            LOG.warning('Operation Forbidden: could not retrieve list of hypervisors'
                        ' (likely no permission)')

        hypervisor_list = filter(lambda h: h.status == 'enabled' and h.state == 'up',
                                 hypervisor_list)
        if self.config.availability_zone:
            host_list = filter(lambda h: h.zone == self.config.availability_zone, host_list)

        if self.config.compute_nodes:
            host_list = filter(lambda h: h.host in self.config.compute_nodes, host_list)

        hosts = [h.hypervisor_hostname for h in hypervisor_list]
        host_list = filter(lambda h: h.host in hosts, host_list)

        avail_list = []
        for host in host_list:
            candidate = self.normalize_az_host(host.zone, host.host)
            if candidate:
                avail_list.append(candidate)
                if len(avail_list) == required_count:
                    return avail_list

        return avail_list

    def get_hypervisor(self, hyper_name):
        # can raise novaclient.exceptions.NotFound
        # first get the id from name
        hyper = self.novaclient.hypervisors.search(hyper_name)[0]
        # get full hypervisor object
        return self.novaclient.hypervisors.get(hyper.id)

    # Given 2 VMs test if they are running on same Host or not
    def check_vm_placement(self, vm_instance1, vm_instance2):
        try:
            server_instance_1 = self.novaclient.servers.get(vm_instance1)
            server_instance_2 = self.novaclient.servers.get(vm_instance2)
            if server_instance_1.hostId == server_instance_2.hostId:
                return True
            else:
                return False
        except novaclient.exceptions:
            LOG.warning("Exception in retrieving the hostId of servers")

    # Create a new security group with appropriate rules
    def security_group_create(self):
        # check first the security group exists
        sec_groups = self.neutronclient.list_security_groups()['security_groups']
        group = [x for x in sec_groups if x['name'] == self.config.security_group_name]
        if len(group) > 0:
            return group[0]

        body = {
            'security_group': {
                'name': self.config.security_group_name,
                'description': 'PNS Security Group'
            }
        }
        group = self.neutronclient.create_security_group(body)['security_group']
        self.security_group_add_rules(group)

        return group

    # Delete a security group
    def security_group_delete(self, group):
        if group:
            LOG.info("Deleting security group")
            self.neutronclient.delete_security_group(group['id'])

    # Add rules to the security group
    def security_group_add_rules(self, group):
        body = {
            'security_group_rule': {
                'direction': 'ingress',
                'security_group_id': group['id'],
                'remote_group_id': None
            }
        }
        if self.config.ipv6_mode:
            body['security_group_rule']['ethertype'] = 'IPv6'
            body['security_group_rule']['remote_ip_prefix'] = '::/0'
        else:
            body['security_group_rule']['ethertype'] = 'IPv4'
            body['security_group_rule']['remote_ip_prefix'] = '0.0.0.0/0'

        # Allow ping traffic
        body['security_group_rule']['protocol'] = 'icmp'
        body['security_group_rule']['port_range_min'] = None
        body['security_group_rule']['port_range_max'] = None
        self.neutronclient.create_security_group_rule(body)

        # Allow SSH traffic
        body['security_group_rule']['protocol'] = 'tcp'
        body['security_group_rule']['port_range_min'] = 22
        body['security_group_rule']['port_range_max'] = 22
        self.neutronclient.create_security_group_rule(body)

        # Allow TCP/UDP traffic for perf tools like iperf/nuttcp
        # 5001: Data traffic (standard iperf data port)
        # 5002: Control traffic (non standard)
        # note that 5000/tcp is already picked by openstack keystone
        body['security_group_rule']['protocol'] = 'tcp'
        body['security_group_rule']['port_range_min'] = 5001
        body['security_group_rule']['port_range_max'] = 5002
        self.neutronclient.create_security_group_rule(body)
        body['security_group_rule']['protocol'] = 'udp'
        self.neutronclient.create_security_group_rule(body)
