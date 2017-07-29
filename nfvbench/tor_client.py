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


class TORClientException(Exception):
    pass


class BasicTORClient(object):

    def __init__(self, config):
        pass

    def get_int_counters(self):
        return {}

    def get_vni_counters(self, vni):
        return {}

    def get_vni_interface(self, vni, counters):
        return None

    def get_vni_for_vlan(self, vlans):
        return []

    def attach_tg_interfaces(self, network_vlans, switch_ports):
        pass

    def clear_nve(self):
        pass

    def clear_interface(self, vni):
        pass

    def close(self):
        pass

    def get_version(self):
        return {}
