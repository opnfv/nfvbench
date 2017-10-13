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

from attrdict import AttrDict
import logging
from nfvbench.config import config_loads
from nfvbench.credentials import Credentials
from nfvbench.fluentd import FluentLogHandler
import nfvbench.log
from nfvbench.network import Interface
from nfvbench.network import Network
from nfvbench.specs import ChainType
from nfvbench.specs import Encaps
import nfvbench.traffic_gen.traffic_utils as traffic_utils
import os
import pytest
import sys

__location__ = os.path.realpath(os.path.join(os.getcwd(),
                                             os.path.dirname(__file__)))



@pytest.fixture
def openstack_vxlan_spec():
    return AttrDict(
        {
            'openstack': AttrDict({
                'vswitch': "VTS",
                'encaps': Encaps.VxLAN}
            ),
            'run_spec': AttrDict({
                'use_vpp': True
            })
        }
    )

# =========================================================================
# PVP Chain tests
# =========================================================================

def test_chain_interface():
    iface = Interface('testname', 'vpp', tx_packets=1234, rx_packets=4321)
    assert iface.name == 'testname'
    assert iface.device == 'vpp'
    assert iface.get_packet_count('tx') == 1234
    assert iface.get_packet_count('rx') == 4321
    assert iface.get_packet_count('wrong_key') == 0


@pytest.fixture(scope='session')
def iface1():
    return Interface('iface1', 'trex', tx_packets=10000, rx_packets=1234)


@pytest.fixture(scope='session')
def iface2():
    return Interface('iface2', 'n9k', tx_packets=1234, rx_packets=9901)


@pytest.fixture(scope='session')
def iface3():
    return Interface('iface3', 'n9k', tx_packets=9900, rx_packets=1234)


@pytest.fixture(scope='session')
def iface4():
    return Interface('iface4', 'vpp', tx_packets=1234, rx_packets=9801)


@pytest.fixture(scope='session')
def net1(iface1, iface2, iface3, iface4):
    return Network([iface1, iface2, iface3, iface4], reverse=False)


@pytest.fixture(scope='session')
def net2(iface1, iface2, iface3):
    return Network([iface1, iface2, iface3], reverse=True)


def test_chain_network(net1, net2, iface1, iface2, iface3, iface4):
    assert [iface1, iface2, iface3, iface4] == net1.get_interfaces()
    assert [iface3, iface2, iface1] == net2.get_interfaces()
    net2.add_interface(iface4)
    assert [iface4, iface3, iface2, iface1] == net2.get_interfaces()


"""
def test_chain_analysis(net1, monkeypatch, openstack_vxlan_spec):
    def mock_empty(self, *args, **kwargs):
        pass

    monkeypatch.setattr(ServiceChain, '_setup', mock_empty)

    f = ServiceChain(AttrDict({'service_chain': 'DUMMY'}), [], {'tor': {}}, openstack_vxlan_spec,
                     lambda x, y, z: None)
    result = f.get_analysis([net1])
    assert result[1]['packet_drop_count'] == 99
    assert result[1]['packet_drop_percentage'] == 0.99
    assert result[2]['packet_drop_count'] == 1
    assert result[2]['packet_drop_percentage'] == 0.01
    assert result[3]['packet_drop_count'] == 99
    assert result[3]['packet_drop_percentage'] == 0.99

    net1.reverse = True
    result = f.get_analysis([net1])
    assert result[1]['packet_drop_count'] == 0
    assert result[1]['packet_drop_percentage'] == 0.0
    assert result[2]['packet_drop_count'] == 0
    assert result[2]['packet_drop_percentage'] == 0.0
    assert result[3]['packet_drop_count'] == 0
    assert result[3]['packet_drop_percentage'] == 0.0


@pytest.fixture
def pvp_chain(monkeypatch, openstack_vxlan_spec):
    tor_vni1 = Interface('vni-4097', 'n9k', 50, 77)
    vsw_vni1 = Interface('vxlan_tunnel0', 'vpp', 77, 48)
    vsw_vif1 = Interface('VirtualEthernet0/0/2', 'vpp', 48, 77)
    vsw_vif2 = Interface('VirtualEthernet0/0/3', 'vpp', 77, 47)
    vsw_vni2 = Interface('vxlan_tunnel1', 'vpp', 43, 77)
    tor_vni2 = Interface('vni-4098', 'n9k', 77, 40)

    def mock_init(self, *args, **kwargs):
        self.vni_ports = [4097, 4098]
        self.specs = openstack_vxlan_spec
        self.clients = {
            'vpp': AttrDict({
                'set_interface_counters': lambda: None,
            })
        }
        self.worker = AttrDict({
            'run': lambda: None,
        })

    def mock_empty(self, *args, **kwargs):
        pass

    def mock_get_network(self, traffic_port, vni_id, reverse=False):
        if vni_id == 0:
            return Network([tor_vni1, vsw_vni1, vsw_vif1], reverse)
        else:
            return Network([tor_vni2, vsw_vni2, vsw_vif2], reverse)

    def mock_get_data(self):
        return {}

    monkeypatch.setattr(PVPChain, '_get_network', mock_get_network)
    monkeypatch.setattr(PVPChain, '_get_data', mock_get_data)
    monkeypatch.setattr(PVPChain, '_setup', mock_empty)
    monkeypatch.setattr(VxLANWorker, '_clear_interfaces', mock_empty)
    monkeypatch.setattr(PVPChain, '_generate_traffic', mock_empty)
    monkeypatch.setattr(PVPChain, '__init__', mock_init)
    return PVPChain(None, None, {'vm': None, 'vpp': None, 'tor': None, 'traffic': None}, None)


def test_pvp_chain_run(pvp_chain):
    result = pvp_chain.run()
    expected_result = {
        'raw_data': {},
        'stats': None,
        'packet_analysis': {
            'direction-forward': [
                OrderedDict([
                    ('interface', 'vni-4097'),
                    ('device', 'n9k'),
                    ('packet_count', 50)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel0'),
                    ('device', 'vpp'),
                    ('packet_count', 48),
                    ('packet_drop_count', 2),
                    ('packet_drop_percentage', 4.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/2'),
                    ('device', 'vpp'),
                    ('packet_count', 48),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/3'),
                    ('device', 'vpp'),
                    ('packet_count', 47),
                    ('packet_drop_count', 1),
                    ('packet_drop_percentage', 2.0)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel1'),
                    ('device', 'vpp'),
                    ('packet_count', 43),
                    ('packet_drop_count', 4),
                    ('packet_drop_percentage', 8.0)
                ]),
                OrderedDict([
                    ('interface', 'vni-4098'),
                    ('device', 'n9k'),
                    ('packet_count', 40),
                    ('packet_drop_count', 3),
                    ('packet_drop_percentage', 6.0)
                ])
            ],
            'direction-reverse': [
                OrderedDict([
                    ('interface', 'vni-4098'),
                    ('device', 'n9k'),
                    ('packet_count', 77)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel1'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/3'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/2'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel0'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'vni-4097'),
                    ('device', 'n9k'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ])
            ]
        }
    }
    assert result == expected_result
"""


# =========================================================================
# PVVP Chain tests
# =========================================================================

"""
@pytest.fixture
def pvvp_chain(monkeypatch, openstack_vxlan_spec):
    tor_vni1 = Interface('vni-4097', 'n9k', 50, 77)
    vsw_vni1 = Interface('vxlan_tunnel0', 'vpp', 77, 48)
    vsw_vif1 = Interface('VirtualEthernet0/0/2', 'vpp', 48, 77)
    vsw_vif3 = Interface('VirtualEthernet0/0/0', 'vpp', 77, 47)
    vsw_vif4 = Interface('VirtualEthernet0/0/1', 'vpp', 45, 77)
    vsw_vif2 = Interface('VirtualEthernet0/0/3', 'vpp', 77, 44)
    vsw_vni2 = Interface('vxlan_tunnel1', 'vpp', 43, 77)
    tor_vni2 = Interface('vni-4098', 'n9k', 77, 40)

    def mock_init(self, *args, **kwargs):
        self.vni_ports = [4099, 4100]
        self.v2vnet = V2VNetwork()
        self.specs = openstack_vxlan_spec
        self.clients = {
            'vpp': AttrDict({
                'get_v2v_network': lambda reverse=None: Network([vsw_vif3, vsw_vif4], reverse),
                'set_interface_counters': lambda pvvp=None: None,
                'set_v2v_counters': lambda: None,
            })
        }
        self.worker = AttrDict({
            'run': lambda: None,
        })

    def mock_empty(self, *args, **kwargs):
        pass

    def mock_get_network(self, traffic_port, vni_id, reverse=False):
        if vni_id == 0:
            return Network([tor_vni1, vsw_vni1, vsw_vif1], reverse)
        else:
            return Network([tor_vni2, vsw_vni2, vsw_vif2], reverse)

    def mock_get_data(self):
        return {}

    monkeypatch.setattr(PVVPChain, '_get_network', mock_get_network)
    monkeypatch.setattr(PVVPChain, '_get_data', mock_get_data)
    monkeypatch.setattr(PVVPChain, '_setup', mock_empty)
    monkeypatch.setattr(VxLANWorker, '_clear_interfaces', mock_empty)
    monkeypatch.setattr(PVVPChain, '_generate_traffic', mock_empty)
    monkeypatch.setattr(PVVPChain, '__init__', mock_init)

    return PVVPChain(None, None, {'vm': None, 'vpp': None, 'tor': None, 'traffic': None}, None)


def test_pvvp_chain_run(pvvp_chain):
    result = pvvp_chain.run()

    expected_result = {
        'raw_data': {},
        'stats': None,
        'packet_analysis':
            {'direction-forward': [
                OrderedDict([
                    ('interface', 'vni-4097'),
                    ('device', 'n9k'),
                    ('packet_count', 50)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel0'),
                    ('device', 'vpp'),
                    ('packet_count', 48),
                    ('packet_drop_count', 2),
                    ('packet_drop_percentage', 4.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/2'),
                    ('device', 'vpp'),
                    ('packet_count', 48),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/0'),
                    ('device', 'vpp'),
                    ('packet_count', 47),
                    ('packet_drop_count', 1),
                    ('packet_drop_percentage', 2.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/1'),
                    ('device', 'vpp'),
                    ('packet_count', 45),
                    ('packet_drop_count', 2),
                    ('packet_drop_percentage', 4.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/3'),
                    ('device', 'vpp'),
                    ('packet_count', 44),
                    ('packet_drop_count', 1),
                    ('packet_drop_percentage', 2.0)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel1'),
                    ('device', 'vpp'),
                    ('packet_count', 43),
                    ('packet_drop_count', 1),
                    ('packet_drop_percentage', 2.0)
                ]),
                OrderedDict([
                    ('interface', 'vni-4098'),
                    ('device', 'n9k'),
                    ('packet_count', 40),
                    ('packet_drop_count', 3),
                    ('packet_drop_percentage', 6.0)
                ])
            ],
            'direction-reverse': [
                OrderedDict([
                    ('interface', 'vni-4098'),
                    ('device', 'n9k'),
                    ('packet_count', 77)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel1'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/3'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/1'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/0'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'VirtualEthernet0/0/2'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'vxlan_tunnel0'),
                    ('device', 'vpp'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ]),
                OrderedDict([
                    ('interface', 'vni-4097'),
                    ('device', 'n9k'),
                    ('packet_count', 77),
                    ('packet_drop_count', 0),
                    ('packet_drop_percentage', 0.0)
                ])
            ]}
    }
    assert result == expected_result
"""

# =========================================================================
# Traffic client tests
# =========================================================================

def test_parse_rate_str():
    parse_rate_str = traffic_utils.parse_rate_str
    try:
        assert parse_rate_str('100%') == {'rate_percent': '100.0'}
        assert parse_rate_str('37.5%') == {'rate_percent': '37.5'}
        assert parse_rate_str('100%') == {'rate_percent': '100.0'}
        assert parse_rate_str('60pps') == {'rate_pps': '60'}
        assert parse_rate_str('60kpps') == {'rate_pps': '60000'}
        assert parse_rate_str('6Mpps') == {'rate_pps': '6000000'}
        assert parse_rate_str('6gpps') == {'rate_pps': '6000000000'}
        assert parse_rate_str('80bps') == {'rate_bps': '80'}
        assert parse_rate_str('80bps') == {'rate_bps': '80'}
        assert parse_rate_str('80kbps') == {'rate_bps': '80000'}
        assert parse_rate_str('80kBps') == {'rate_bps': '640000'}
        assert parse_rate_str('80Mbps') == {'rate_bps': '80000000'}
        assert parse_rate_str('80 MBps') == {'rate_bps': '640000000'}
        assert parse_rate_str('80Gbps') == {'rate_bps': '80000000000'}
    except Exception as exc:
        assert False, exc.message

    def should_raise_error(str):
        try:
            parse_rate_str(str)
        except Exception:
            return True
        else:
            assert False

    assert should_raise_error('101')
    assert should_raise_error('201%')
    assert should_raise_error('10Kbps')
    assert should_raise_error('0kbps')
    assert should_raise_error('0pps')
    assert should_raise_error('-1bps')

def test_rate_conversion():
    assert traffic_utils.load_to_bps(50, 10000000000) == pytest.approx(5000000000.0)
    assert traffic_utils.load_to_bps(37, 10000000000) == pytest.approx(3700000000.0)
    assert traffic_utils.load_to_bps(100, 10000000000) == pytest.approx(10000000000.0)

    assert traffic_utils.bps_to_load(5000000000.0, 10000000000) == pytest.approx(50.0)
    assert traffic_utils.bps_to_load(3700000000.0, 10000000000) == pytest.approx(37.0)
    assert traffic_utils.bps_to_load(10000000000.0, 10000000000) == pytest.approx(100.0)

    assert traffic_utils.bps_to_pps(500000, 64) == pytest.approx(744.047619048)
    assert traffic_utils.bps_to_pps(388888, 1518) == pytest.approx(31.6066319896)
    assert traffic_utils.bps_to_pps(9298322222, 340.3) == pytest.approx(3225895.85831)

    assert traffic_utils.pps_to_bps(744.047619048, 64) == pytest.approx(500000)
    assert traffic_utils.pps_to_bps(31.6066319896, 1518) == pytest.approx(388888)
    assert traffic_utils.pps_to_bps(3225895.85831, 340.3) == pytest.approx(9298322222)


"""
@pytest.fixture
def traffic_client(monkeypatch):

    def mock_init(self, *args, **kwargs):
        self.run_config = {
            'bidirectional': False,
            'l2frame_size': '64',
            'duration_sec': 30,
            'rates': [{'rate_percent': '10'}, {'rate_pps': '1'}]
        }

        self.config = AttrDict({
            'generator_config': {
                'intf_speed': 10000000000
            },
            'ndr_run': True,
            'pdr_run': True,
            'single_run': False,
            'attempts': 1,
            'measurement': {
                'NDR': 0.0,
                'PDR': 0.1,
                'load_epsilon': 0.1
            }
        })

        self.runner = AttrDict({
            'time_elapsed': lambda: 30,
            'stop': lambda: None,
            'client': AttrDict({'get_stats': lambda: None})
        })

        self.current_load = None
        self.dummy_stats = {
            50.0: 72.6433562831,
            25.0: 45.6095059858,
            12.5: 0.0,
            18.75: 27.218642979,
            15.625: 12.68585861,
            14.0625: 2.47154392563,
            13.28125: 0.000663797066801,
            12.890625: 0.0,
            13.0859375: 0.0,
            13.18359375: 0.00359387347122,
            13.671875: 0.307939922531,
            13.4765625: 0.0207718516156,
            13.57421875: 0.0661795060969
        }

    def mock_modify_load(self, load):
        self.run_config['rates'][0] = {'rate_percent': str(load)}
        self.current_load = load

    def mock_run_traffic(self):
        yield {
            'overall': {
                'drop_rate_percent': self.dummy_stats[self.current_load],
                'rx': {
                    'total_pkts': 1,
                    'avg_delay_usec': 0.0,
                    'max_delay_usec': 0.0,
                    'min_delay_usec': 0.0
                }
            }
        }

    monkeypatch.setattr(TrafficClient, '__init__', mock_init)
    monkeypatch.setattr(TrafficClient, 'modify_load', mock_modify_load)
    monkeypatch.setattr(TrafficClient, 'run_traffic', mock_run_traffic)

    return TrafficClient()


def test_ndr_pdr_search(traffic_client):
    expected_results = {
        'pdr': {
            'l2frame_size': '64',
            'initial_rate_type': 'rate_percent',
            'stats': {
                'overall': {
                    'drop_rate_percent': 0.0661795060969,
                    'min_delay_usec': 0.0,
                    'avg_delay_usec': 0.0,
                    'max_delay_usec': 0.0
                }
            },
            'load_percent_per_direction': 13.57421875,
            'rate_percent': 13.57422547,
            'rate_bps': 1357422547.0,
            'rate_pps': 2019974.0282738095,
            'duration_sec': 30
        },
        'ndr': {
            'l2frame_size': '64',
            'initial_rate_type': 'rate_percent',
            'stats': {
                'overall': {
                    'drop_rate_percent': 0.0,
                    'min_delay_usec': 0.0,
                    'avg_delay_usec': 0.0,
                    'max_delay_usec': 0.0
                }
            },
            'load_percent_per_direction': 13.0859375,
            'rate_percent': 13.08594422,
            'rate_bps': 1308594422.0,
            'rate_pps': 1947313.1279761905,
            'duration_sec': 30
        }
    }

    results = traffic_client.get_ndr_and_pdr()
    assert len(results) == 2
    for result in results.values():
        result.pop('timestamp_sec')
        result.pop('time_taken_sec')
    assert results == expected_results
"""

# =========================================================================
# Other tests
# =========================================================================

def setup_module(module):
    nfvbench.log.setup(mute_stdout=True)

def test_no_credentials():
    cred = Credentials('/completely/wrong/path/openrc', None, False)
    if cred.rc_auth_url:
        # shouldn't get valid data unless user set environment variables
        assert False
    else:
        assert True

# Because trex_stl_lib may not be installed when running unit test
# nfvbench.traffic_client will try to import STLError:
# from trex_stl_lib.api import STLError
# will raise ImportError: No module named trex_stl_lib.api
try:
    import trex_stl_lib.api
    assert(trex_stl_lib.api)
except ImportError:
    # Make up a trex_stl_lib.api.STLError class
    class STLError(Exception):
        pass
    from types import ModuleType
    stl_lib_mod = ModuleType('trex_stl_lib')
    sys.modules['trex_stl_lib'] = stl_lib_mod
    api_mod = ModuleType('trex_stl_lib.api')
    stl_lib_mod.api = api_mod
    sys.modules['trex_stl_lib.api'] = api_mod
    api_mod.STLError = STLError

from nfvbench.traffic_client import Device
from nfvbench.traffic_client import IpBlock


def test_ip_block():
    ipb = IpBlock('10.0.0.0', '0.0.0.1', 256)
    assert(ipb.get_ip() == '10.0.0.0')
    assert(ipb.get_ip(255) == '10.0.0.255')
    with pytest.raises(IndexError):
        ipb.get_ip(256)
    # verify with step larger than 1
    ipb = IpBlock('10.0.0.0', '0.0.0.2', 256)
    assert(ipb.get_ip() == '10.0.0.0')
    assert(ipb.get_ip(1) == '10.0.0.2')
    assert(ipb.get_ip(128) == '10.0.1.0')
    assert(ipb.get_ip(255) == '10.0.1.254')
    with pytest.raises(IndexError):
        ipb.get_ip(256)

def check_config(configs, cc, fc, src_ip, dst_ip, step_ip):
    '''Verify that the range configs for each chain have adjacent IP ranges
    of the right size and without holes between chains
    '''
    step = Device.ip_to_int(step_ip)
    cfc = 0
    sip = Device.ip_to_int(src_ip)
    dip = Device.ip_to_int(dst_ip)
    for index in range(cc):
        config = configs[index]
        assert(config['ip_src_count'] == config['ip_dst_count'])
        assert(Device.ip_to_int(config['ip_src_addr']) == sip)
        assert(Device.ip_to_int(config['ip_dst_addr']) == dip)
        count = config['ip_src_count']
        cfc += count
        sip += count * step
        dip += count * step
    assert(cfc == fc)

def create_device(fc, cc, ip, gip, tggip, step_ip):
    return Device(0, 0, flow_count=fc, chain_count=cc, ip=ip, gateway_ip=gip, tg_gateway_ip=tggip,
                  ip_addrs_step=step_ip,
                  tg_gateway_ip_addrs_step=step_ip,
                  gateway_ip_addrs_step=step_ip)

def check_device_flow_config(step_ip):
    fc = 99999
    cc = 10
    ip0 = '10.0.0.0'
    ip1 = '20.0.0.0'
    tggip = '50.0.0.0'
    gip = '60.0.0.0'
    dev0 = create_device(fc, cc, ip0, gip, tggip, step_ip)
    dev1 = create_device(fc, cc, ip1, gip, tggip, step_ip)
    dev0.set_destination(dev1)
    configs = dev0.get_stream_configs(ChainType.EXT)
    check_config(configs, cc, fc, ip0, ip1, step_ip)

def test_device_flow_config():
    check_device_flow_config('0.0.0.1')
    check_device_flow_config('0.0.0.2')

def test_device_ip_range():
    def ip_range_overlaps(ip0, ip1, flows):
        tggip = '50.0.0.0'
        gip = '60.0.0.0'
        dev0 = create_device(flows, 10, ip0, gip, tggip, '0.0.0.1')
        dev1 = create_device(flows, 10, ip1, gip, tggip, '0.0.0.1')
        dev0.set_destination(dev1)
        return dev0.ip_range_overlaps()
    assert(not ip_range_overlaps('10.0.0.0', '20.0.0.0', 10000))
    assert(ip_range_overlaps('10.0.0.0', '10.0.1.0', 10000))
    assert(ip_range_overlaps('10.0.0.0', '10.0.1.0', 257))
    assert(ip_range_overlaps('10.0.1.0', '10.0.0.0', 257))


def test_config():
    refcfg = {1: 100, 2: {21: 100, 22: 200}, 3: None}
    res1 = {1: 10, 2: {21: 100, 22: 200}, 3: None}
    res2 = {1: 100, 2: {21: 1000, 22: 200}, 3: None}
    res3 = {1: 100, 2: {21: 100, 22: 200}, 3: "abc"}
    assert(config_loads("{}", refcfg) == refcfg)
    assert(config_loads("{1: 10}", refcfg) == res1)
    assert(config_loads("{2: {21: 1000}}", refcfg) == res2)
    assert(config_loads('{3: "abc"}', refcfg) == res3)

    # correctly fails
    # pairs of input string and expected subset (None if identical)
    fail_pairs = [
        ["{4: 0}", None],
        ["{2: {21: 100, 30: 50}}", "{2: {30: 50}}"],
        ["{2: {0: 1, 1: 2}, 5: 5}", None],
        ["{1: 'abc', 2: {21: 0}}", "{1: 'abc'}"],
        ["{2: 100}", None]
    ]
    for fail_pair in fail_pairs:
        with pytest.raises(Exception) as e_info:
            config_loads(fail_pair[0], refcfg)
        expected = fail_pair[1]
        if expected is None:
            expected = fail_pair[0]
        assert expected in e_info.value.message

    # whitelist keys
    flavor = {'flavor': {'vcpus': 2, 'ram': 8192, 'disk': 0,
              'extra_specs': {'hw:cpu_policy': 'dedicated'}}}
    new_flavor = {'flavor': {'vcpus': 2, 'ram': 8192, 'disk': 0,
                  'extra_specs': {'hw:cpu_policy': 'dedicated', 'hw:numa_nodes': 2}}}
    assert(config_loads("{'flavor': {'extra_specs': {'hw:numa_nodes': 2}}}", flavor,
                        whitelist_keys=['alpha', 'extra_specs']) == new_flavor)

def test_fluentd():
    logger = logging.getLogger('fluent-logger')
    handler = FluentLogHandler('nfvbench', fluentd_port=7081)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info('test')
    logger.warning('test %d', 100)
    try:
        raise Exception("test")
    except Exception:
        logger.exception("got exception")
