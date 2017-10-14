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


class BasicWorker(object):

    def __init__(self, config, clients, specs):
        self.config = config
        self.clients = clients
        self.specs = specs

    def set_vlan_tag(self, device, vlan):
        device.set_vlan_tag(vlan)

    def set_vlans(self, vlans):
        pass

    def config_interfaces(self):
        pass

    def get_data(self):
        return {}

    def get_network_interfaces(self, _):
        return []

    def clear_interfaces(self):
        pass

    def run(self):
        return None, None

    def get_compute_nodes_bios(self):
        return {}

    def get_version(self):
        return {}

    def close(self):
        pass
