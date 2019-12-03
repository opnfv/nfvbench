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
"""Module to interface with nova and glance."""

import time
import traceback

from glanceclient import exc as glance_exception
try:
    from glanceclient.openstack.common.apiclient.exceptions import NotFound as GlanceImageNotFound
except ImportError:
    from glanceclient.v1.apiclient.exceptions import NotFound as GlanceImageNotFound
import keystoneauth1
import novaclient

from .log import LOG


class Compute(object):
    """Class to interface with nova and glance."""

    def __init__(self, nova_client, glance_client, config):
        """Create a new compute instance to interact with nova and glance."""
        self.novaclient = nova_client
        self.glance_client = glance_client
        self.config = config

    def find_image(self, image_name):
        """Find an image by name."""
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
        """Delete an image by name."""
        try:
            LOG.log("Deleting image %s...", img_name)
            img = self.find_image(image_name=img_name)
            self.glance_client.images.delete(img.id)
        except Exception:
            LOG.error("Failed to delete the image %s.", img_name)
            return False

        return True

    def image_multiqueue_enabled(self, img):
        """Check if multiqueue property is enabled on given image."""
        try:
            return img['hw_vif_multiqueue_enabled'] == 'true'
        except KeyError:
            return False

    def image_set_multiqueue(self, img, enabled):
        """Set multiqueue property as enabled or disabled on given image."""
        cur_mqe = self.image_multiqueue_enabled(img)
        LOG.info('Image %s hw_vif_multiqueue_enabled property is "%s"',
                 img.name, str(cur_mqe).lower())
        if cur_mqe != enabled:
            mqe = str(enabled).lower()
            self.glance_client.images.update(img.id, hw_vif_multiqueue_enabled=mqe)
            img['hw_vif_multiqueue_enabled'] = mqe
            LOG.info('Image %s hw_vif_multiqueue_enabled property changed to "%s"', img.name, mqe)

    # Create a server instance with name vmname
    # and check that it gets into the ACTIVE state
    def create_server(self, vmname, image, flavor, key_name,
                      nic, sec_group, avail_zone=None, user_data=None,
                      config_drive=None, files=None):
        """Create a new server."""
        if sec_group:
            security_groups = [sec_group['id']]
        else:
            security_groups = None

        # Also attach the created security group for the test
        LOG.info('Creating instance %s with AZ: "%s"', vmname, avail_zone)
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
        """Poll a server from its reference."""
        return self.novaclient.servers.get(instance.id)

    def get_server_list(self):
        """Get the list of all servers."""
        servers_list = self.novaclient.servers.list()
        return servers_list

    def delete_server(self, server):
        """Delete a server from its object reference."""
        self.novaclient.servers.delete(server)

    def find_flavor(self, flavor_type):
        """Find a flavor by name."""
        try:
            flavor = self.novaclient.flavors.find(name=flavor_type)
            return flavor
        except Exception:
            return None

    def create_flavor(self, name, ram, vcpus, disk, ephemeral=0):
        """Create a flavor."""
        return self.novaclient.flavors.create(name=name, ram=ram, vcpus=vcpus, disk=disk,
                                              ephemeral=ephemeral)

    def get_hypervisor(self, hyper_name):
        """Get the hypervisor from its name.

        Can raise novaclient.exceptions.NotFound
        """
        # first get the id from name
        hyper = self.novaclient.hypervisors.search(hyper_name)[0]
        # get full hypervisor object
        return self.novaclient.hypervisors.get(hyper.id)
