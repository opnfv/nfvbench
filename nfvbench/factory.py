#!/usr/bin/env python
# Copyright 2017 Cisco Systems, Inc.  All rights reserved.
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
"""Factory for creating worker and config plugin instances."""

from . import chain_workers as workers
from .config_plugin import ConfigPlugin


class BasicFactory(object):
    """Basic factory class to be overridden for advanced customization."""

    def get_chain_worker(self, encaps, service_chain):
        """Get a chain worker based on encaps and service chain type."""
        return workers.BasicWorker

    def get_config_plugin_class(self):
        """Get a config plugin."""
        return ConfigPlugin
