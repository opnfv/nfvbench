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

import abc
import specs


class ConfigPluginBase(object):
    """Base class for config plugins. Need to implement public interfaces."""
    __metaclass__ = abc.ABCMeta

    class InitializationFailure(Exception):
        pass

    def __init__(self, config):
        if not config:
            raise ConfigPluginBase.InitializationFailure(
                'Initialization parameters need to be assigned.')

        self.config = config

    @abc.abstractmethod
    def get_config(self):
        """Returns updated default configuration file."""

    def set_config(self, config):
        """This method is called when the config has changed after this instance was initialized.

        This is needed in teh frequent case where the main config is changed in a copy and to
        prevent this instance to keep pointing to the old copy of the config
        """
        self.config = config

    @abc.abstractmethod
    def get_openstack_spec(self):
        """Returns OpenStack specs for host."""

    @abc.abstractmethod
    def get_run_spec(self, openstack_spec):
        """Returns RunSpec for given platform."""

    @abc.abstractmethod
    def validate_config(self, cfg, openstack_spec):
        """Validate config file."""

    @abc.abstractmethod
    def prepare_results_config(self, cfg):
        """This function is called before running configuration is copied.
        Example usage is to remove sensitive information like switch credentials.
        """

    @abc.abstractmethod
    def get_version(self):
        """Returns platform version."""


class ConfigPlugin(ConfigPluginBase):
    """No-op config plugin class. Does not change anything."""

    def __init__(self, config):
        ConfigPluginBase.__init__(self, config)

    def get_config(self):
        """Public interface for updating config file. Just returns given config."""
        return self.config

    def get_openstack_spec(self):
        """Returns OpenStack specs for host."""
        return specs.OpenStackSpec()

    def get_run_spec(self, openstack_spec):
        """Returns RunSpec for given platform."""
        return specs.RunSpec(self.config.no_vswitch_access, openstack_spec)

    def validate_config(self, config, openstack_spec):
        pass

    def prepare_results_config(self, cfg):
        return cfg

    def get_version(self):
        return {}
