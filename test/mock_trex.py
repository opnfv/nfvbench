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
"""This module creates the missing Trex library classes when they are not installed."""

import sys

# Because trex_stl_lib may not be installed when running unit test
# nfvbench.traffic_client will try to import STLError:
# from trex.stl.api import STLError
# will raise ImportError: No module named trex.stl.api
# trex_gen.py will also try to import a number of trex.stl.api classes
try:
    import trex.stl.api
    assert trex.stl.api
except ImportError:
    from types import ModuleType

    # Make up a trex.stl.api.STLError class
    class STLDummy(Exception):
        """Dummy class."""

    trex_lib_mod = ModuleType('trex')
    sys.modules['trex'] = trex_lib_mod
    stl_lib_mod = ModuleType('trex.stl')
    trex_lib_mod.stl = stl_lib_mod
    sys.modules['trex.stl'] = stl_lib_mod
    api_mod = ModuleType('trex.stl.api')
    stl_lib_mod.api = api_mod
    sys.modules['trex.stl.api'] = api_mod
    api_mod.STLError = STLDummy
    api_mod.STLxyz = STLDummy
    api_mod.CTRexVmInsFixHwCs = STLDummy
    api_mod.Dot1Q = STLDummy
    api_mod.Ether = STLDummy
    api_mod.IP = STLDummy
    api_mod.STLClient = STLDummy
    api_mod.STLFlowLatencyStats = STLDummy
    api_mod.STLFlowStats = STLDummy
    api_mod.STLPktBuilder = STLDummy
    api_mod.STLScVmRaw = STLDummy
    api_mod.STLStream = STLDummy
    api_mod.STLTXCont = STLDummy
    api_mod.STLVmFixChecksumHw = STLDummy
    api_mod.STLVmFlowVar = STLDummy
    api_mod.STLVmFlowVarRepeatableRandom = STLDummy
    api_mod.STLVmWrFlowVar = STLDummy
    api_mod.UDP = STLDummy
    api_mod.bind_layers = STLDummy
    api_mod.FlagsField = STLDummy
    api_mod.Packet = STLDummy
    api_mod.ThreeBytesField = STLDummy
    api_mod.XByteField = STLDummy

    common_mod = ModuleType('trex.common')
    trex_lib_mod.common = common_mod
    sys.modules['trex.common'] = common_mod
    services_mod = ModuleType('trex.common.services')
    common_mod.services = services_mod
    sys.modules['trex.common.services'] = services_mod
    arp_mod = ModuleType('trex.common.services.trex_service_arp')
    services_mod.trex_stl_service_arp = arp_mod
    sys.modules['trex.common.services.trex_service_arp'] = arp_mod
    arp_mod.ServiceARP = STLDummy

def no_op():
    """Empty function."""
