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


class Encaps(object):
    VLAN = "VLAN"
    VxLAN = "VxLAN"
    BASIC = "BASIC"

    encaps_mapping = {
        'VLAN': VLAN,
        'VXLAN': VxLAN
    }

    @classmethod
    def get(cls, network_type):
        return cls.encaps_mapping.get(network_type.upper(), None)


class ChainType(object):
        PVP = "PVP"
        PVVP = "PVVP"
        EXT = "EXT"

        chain_mapping = {
            'PVP': PVP,
            'PVVP': PVVP,
            'EXT': EXT
        }

        @classmethod
        def get_chain_type(cls, chain):
            return cls.chain_mapping.get(chain.upper(), None)


class OpenStackSpec(object):

    def __init__(self):
        self.__vswitch = "BASIC"
        self.__encaps = Encaps.BASIC

    @property
    def vswitch(self):
        return self.__vswitch

    @vswitch.setter
    def vswitch(self, vsw):
        if vsw is None:
            raise Exception('Trying to set vSwitch as None.')

        self.__vswitch = vsw.upper()

    @property
    def encaps(self):
        return self.__encaps

    @encaps.setter
    def encaps(self, enc):
        if enc is None:
            raise Exception('Trying to set Encaps as None.')

        self.__encaps = enc


class RunSpec(object):

    def __init__(self, no_vswitch_access, openstack_spec):
        self.use_vswitch = (not no_vswitch_access) and openstack_spec.vswitch != "BASIC"


class Specs(object):

    def __init__(self):
        self.openstack = None
        self.run_spec = None

    def set_openstack_spec(self, openstack_spec):
        self.openstack = openstack_spec

    def set_run_spec(self, run_spec):
        self.run_spec = run_spec
