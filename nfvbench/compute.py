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
import time
import traceback

from glanceclient import exc as glance_exception
try:
    from glanceclient.openstack.common.apiclient.exceptions import NotFound as GlanceImageNotFound
except ImportError:
    from glanceclient.v1.apiclient.exceptions import NotFound as GlanceImageNotFound
import keystoneauth1
import novaclient

from log import LOG


class Compute(object):
    def __init__(self, nova_client, glance_client, config):
        self.novaclient = nova_client
        self.glance_client = glance_client
        self.config = config

    def find_image(self, image_name):
        try:
            return next(self.glance_client.images.list(filters={'name': image_name}), None)
        except (novaclient.exceptions.NotFound, keystoneauth1.exceptions.http.NotFound,
                GlanceImageNotFound):
            pass
        return None

    def upload_image_via_url(self, final_image_name, image_file, retry_count=60):
        """Directly upload image to Nova via URL if image is not present."""
        retry = 0
        try:
            # check image is file/url based.
            with open(image_file) as f_image:
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
            LOG.error("Authentication error while uploading the image: %s", str(exc))
            return False
        except Exception:
            LOG.error(traceback.format_exc())
            LOG.error("Failed to upload image %s.", image_file)
            return False
        return True

    def delete_image(self, img_name):
        try:
            LOG.log("Deleting image %s...", img_name)
            img = self.find_image(image_name=img_name)
            self.glance_client.images.delete(img.id)
        except Exception:
            LOG.error("Failed to delete the image %s.", img_name)
            return False

        return True

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

    def delete_server(self, server):
        self.novaclient.servers.delete(server)

    def find_flavor(self, flavor_type):
        try:
            flavor = self.novaclient.flavors.find(name=flavor_type)
            return flavor
        except Exception:
            return None

    def create_flavor(self, name, ram, vcpus, disk, ephemeral=0):
        return self.novaclient.flavors.create(name=name, ram=ram, vcpus=vcpus, disk=disk,
                                              ephemeral=ephemeral)

    def normalize_az_host(self, az, host):
        if not az:
            az = self.config.availability_zone
        return az + ':' + host

    def auto_fill_az(self, host_list, host):
        """Auto fill az:host.

        no az provided, if there is a host list we can auto-fill the az
        else we use the configured az if available
        else we return an error
        """
        if host_list:
            for hyp in host_list:
                if hyp.host == host:
                    return self.normalize_az_host(hyp.zone, host)
            # no match on host
            LOG.error('Passed host name does not exist: %s', host)
            return None
        if self.config.availability_zone:
            return self.normalize_az_host(None, host)
        LOG.error('--hypervisor passed without an az and no az configured')
        return None

    def sanitize_az_host(self, host_list, az_host):
        """Sanitize the az:host string.

        host_list: list of hosts as retrieved from openstack (can be empty)
        az_host: either a host or a az:host string
        if a host, will check host is in the list, find the corresponding az and
                    return az:host
        if az:host is passed will check the host is in the list and az matches
        if host_list is empty, will return the configured az if there is no
                    az passed
        """
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
            LOG.error('No match for availability zone and host %s', az_host)
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
    def get_enabled_az_host_list(self, required_count=1):
        """Check which hypervisors are enabled and on which compute nodes they are running.

        Pick up to the required count of hosts (can be less or zero)

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

        hypervisor_list = [h for h in hypervisor_list if h.status == 'enabled' and h.state == 'up']
        if self.config.availability_zone:
            host_list = [h for h in host_list if h.zone == self.config.availability_zone]

        if self.config.compute_nodes:
            host_list = [h for h in host_list if h.host in self.config.compute_nodes]

        hosts = [h.hypervisor_hostname for h in hypervisor_list]
        host_list = [h for h in host_list if h.host in hosts]

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
