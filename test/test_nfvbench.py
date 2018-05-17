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
import json
import logging
import os
import sys

import pytest

from attrdict import AttrDict
from nfvbench.config import config_loads
from nfvbench.credentials import Credentials
from nfvbench.fluentd import FluentLogHandler
import nfvbench.log
from nfvbench.network import Interface
from nfvbench.network import Network
from nfvbench.specs import ChainType
from nfvbench.specs import Encaps
import nfvbench.traffic_gen.traffic_utils as traffic_utils

__location__ = os.path.realpath(os.path.join(os.getcwd(),
                                             os.path.dirname(__file__)))


@pytest.fixture
def openstack_vxlan_spec():
    return AttrDict(
        {
            'openstack': AttrDict({
                'vswitch': "VTS",
                'encaps': Encaps.VxLAN}),
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


# pylint: disable=redefined-outer-name
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


# pylint: enable=redefined-outer-name

# pylint: disable=pointless-string-statement
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
            return False

        return False

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

# pps at 10Gbps line rate for 64 byte frames
LR_64B_PPS = 14880952
LR_1518B_PPS = 812743

def assert_equivalence(reference, value, allowance_pct=1):
    '''Asserts if a value is equivalent to a reference value with given margin

    :param float reference: reference value to compare to
    :param float value: value to compare to reference
    :param float allowance_pct: max allowed percentage of margin
        0 : requires exact match
        1 : must be equal within 1% of the reference value
        ...
        100: always true
    '''
    if reference == 0:
        assert value == 0
    else:
        assert abs(value - reference) * 100 / reference <= allowance_pct

def test_load_from_rate():
    assert traffic_utils.get_load_from_rate('100%') == 100
    assert_equivalence(100, traffic_utils.get_load_from_rate(str(LR_64B_PPS) + 'pps'))
    assert_equivalence(50, traffic_utils.get_load_from_rate(str(LR_64B_PPS / 2) + 'pps'))
    assert_equivalence(100, traffic_utils.get_load_from_rate('10Gbps'))
    assert_equivalence(50, traffic_utils.get_load_from_rate('5000Mbps'))
    assert_equivalence(1, traffic_utils.get_load_from_rate('100Mbps'))
    assert_equivalence(100, traffic_utils.get_load_from_rate(str(LR_1518B_PPS) + 'pps',
                                                             avg_frame_size=1518))
    assert_equivalence(100, traffic_utils.get_load_from_rate(str(LR_1518B_PPS * 2) + 'pps',
                                                             avg_frame_size=1518,
                                                             line_rate='20Gbps'))

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

    def mock_modify_load(self, load):
        self.run_config['rates'][0] = {'rate_percent': str(load)}
        self.current_load = load

    monkeypatch.setattr(TrafficClient, '__init__', mock_init)
    monkeypatch.setattr(TrafficClient, 'modify_load', mock_modify_load)

    return TrafficClient()
"""


# pylint: enable=pointless-string-statement

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

    assert trex_stl_lib.api
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

# pylint: disable=wrong-import-position,ungrouped-imports
from nfvbench.traffic_client import Device
from nfvbench.traffic_client import IpBlock
from nfvbench.traffic_client import TrafficClient
from nfvbench.traffic_client import TrafficGeneratorFactory

def test_ip_block():
    ipb = IpBlock('10.0.0.0', '0.0.0.1', 256)
    assert ipb.get_ip() == '10.0.0.0'
    assert ipb.get_ip(255) == '10.0.0.255'
    with pytest.raises(IndexError):
        ipb.get_ip(256)
    # verify with step larger than 1
    ipb = IpBlock('10.0.0.0', '0.0.0.2', 256)
    assert ipb.get_ip() == '10.0.0.0'
    assert ipb.get_ip(1) == '10.0.0.2'
    assert ipb.get_ip(128) == '10.0.1.0'
    assert ipb.get_ip(255) == '10.0.1.254'
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
        assert config['ip_src_count'] == config['ip_dst_count']
        assert Device.ip_to_int(config['ip_src_addr']) == sip
        assert Device.ip_to_int(config['ip_dst_addr']) == dip
        count = config['ip_src_count']
        cfc += count
        sip += count * step
        dip += count * step
    assert cfc == fc


def create_device(fc, cc, ip, gip, tggip, step_ip, mac):
    return Device(0, 0, flow_count=fc, chain_count=cc, ip=ip, gateway_ip=gip, tg_gateway_ip=tggip,
                  ip_addrs_step=step_ip,
                  tg_gateway_ip_addrs_step=step_ip,
                  gateway_ip_addrs_step=step_ip,
                  dst_mac=mac)


def check_device_flow_config(step_ip):
    fc = 99999
    cc = 10
    ip0 = '10.0.0.0'
    ip1 = '20.0.0.0'
    tggip = '50.0.0.0'
    gip = '60.0.0.0'
    mac = ['00:11:22:33:44:55'] * cc
    dev0 = create_device(fc, cc, ip0, gip, tggip, step_ip, mac)
    dev1 = create_device(fc, cc, ip1, gip, tggip, step_ip, mac)
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
        mac = ['00:11:22:33:44:55'] * 10
        dev0 = create_device(flows, 10, ip0, gip, tggip, '0.0.0.1', mac)
        dev1 = create_device(flows, 10, ip1, gip, tggip, '0.0.0.1', mac)
        dev0.set_destination(dev1)
        return dev0.ip_range_overlaps()

    assert not ip_range_overlaps('10.0.0.0', '20.0.0.0', 10000)
    assert ip_range_overlaps('10.0.0.0', '10.0.1.0', 10000)
    assert ip_range_overlaps('10.0.0.0', '10.0.1.0', 257)
    assert ip_range_overlaps('10.0.1.0', '10.0.0.0', 257)


def test_config():
    refcfg = {1: 100, 2: {21: 100, 22: 200}, 3: None}
    res1 = {1: 10, 2: {21: 100, 22: 200}, 3: None}
    res2 = {1: 100, 2: {21: 1000, 22: 200}, 3: None}
    res3 = {1: 100, 2: {21: 100, 22: 200}, 3: "abc"}
    assert config_loads("{}", refcfg) == refcfg
    assert config_loads("{1: 10}", refcfg) == res1
    assert config_loads("{2: {21: 1000}}", refcfg) == res2
    assert config_loads('{3: "abc"}', refcfg) == res3

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
    assert config_loads("{'flavor': {'extra_specs': {'hw:numa_nodes': 2}}}", flavor,
                        whitelist_keys=['alpha', 'extra_specs']) == new_flavor


def test_fluentd():
    logger = logging.getLogger('fluent-logger')

    class FluentdConfig(dict):
        def __getattr__(self, attr):
            return self.get(attr)

    fluentd_configs = [
        FluentdConfig({
            'logging_tag': 'nfvbench',
            'result_tag': 'resultnfvbench',
            'ip': '127.0.0.1',
            'port': 7081
        }),
        FluentdConfig({
            'logging_tag': 'nfvbench',
            'result_tag': 'resultnfvbench',
            'ip': '127.0.0.1',
            'port': 24224
        }),
        FluentdConfig({
            'logging_tag': None,
            'result_tag': 'resultnfvbench',
            'ip': '127.0.0.1',
            'port': 7082
        }),
        FluentdConfig({
            'logging_tag': 'nfvbench',
            'result_tag': None,
            'ip': '127.0.0.1',
            'port': 7083
        })
    ]

    handler = FluentLogHandler(fluentd_configs=fluentd_configs)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info('test')
    logger.warning('test %d', 100)

    try:
        raise Exception("test")
    except Exception:
        logger.exception("got exception")

def assert_ndr_pdr(stats, ndr, ndr_dr, pdr, pdr_dr):
    assert stats['ndr']['rate_percent'] == ndr
    assert stats['ndr']['stats']['overall']['drop_percentage'] == ndr_dr
    assert_equivalence(pdr, stats['pdr']['rate_percent'])
    assert_equivalence(pdr_dr, stats['pdr']['stats']['overall']['drop_percentage'])

def get_dummy_tg_config(chain_type, rate):
    return AttrDict({
        'traffic_generator': {'host_name': 'nfvbench_tg',
                              'default_profile': 'dummy',
                              'generator_profile': [{'name': 'dummy',
                                                     'tool': 'dummy',
                                                     'ip': '127.0.0.1',
                                                     'intf_speed': '10Gbps',
                                                     'interfaces': [{'port': 0, 'pci': '0.0'},
                                                                    {'port': 1, 'pci': '0.0'}]}],
                              'ip_addrs_step': '0.0.0.1',
                              'ip_addrs': ['10.0.0.0/8', '20.0.0.0/8'],
                              'tg_gateway_ip_addrs': ['1.1.0.100', '2.2.0.100'],
                              'tg_gateway_ip_addrs_step': '0.0.0.1',
                              'gateway_ip_addrs': ['1.1.0.2', '2.2.0.2'],
                              'gateway_ip_addrs_step': '0.0.0.1',
                              'mac_addrs_left': None,
                              'mac_addrs_right': None,
                              'udp_src_port': None,
                              'udp_dst_port': None},
        'service_chain': chain_type,
        'service_chain_count': 1,
        'flow_count': 10,
        'vlan_tagging': True,
        'no_arp': False,
        'duration_sec': 1,
        'interval_sec': 1,
        'pause_sec': 1,
        'rate': rate,
        'check_traffic_time_sec': 200,
        'generic_poll_sec': 2,
        'measurement': {'NDR': 0.001, 'PDR': 0.1, 'load_epsilon': 0.1},
        'l2_loopback': False
    })

def get_traffic_client():
    config = get_dummy_tg_config('PVP', 'ndr_pdr')
    config['ndr_run'] = True
    config['pdr_run'] = True
    config['generator_profile'] = 'dummy'
    config['single_run'] = False
    generator_factory = TrafficGeneratorFactory(config)
    config.generator_config = generator_factory.get_generator_config(config.generator_profile)
    traffic_client = TrafficClient(config, skip_sleep=True)
    traffic_client.start_traffic_generator()
    traffic_client.set_traffic('64', True)
    return traffic_client

def test_ndr_at_lr():
    traffic_client = get_traffic_client()
    tg = traffic_client.gen

    # this is a perfect sut with no loss at LR
    tg.set_response_curve(lr_dr=0, ndr=100, max_actual_tx=100, max_11_tx=100)
    # tx packets should be line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(100) == (LR_64B_PPS, 0)
    # NDR and PDR should be at 100%
    traffic_client.ensure_end_to_end()
    results = traffic_client.get_ndr_and_pdr()

    assert_ndr_pdr(results, 200.0, 0.0, 200.0, 0.0)

def test_ndr_at_50():
    traffic_client = get_traffic_client()
    tg = traffic_client.gen
    # this is a sut with an NDR of 50% and linear drop rate after NDR up to 20% drops at LR
    # (meaning that if you send 100% TX, you will only receive 80% RX)
    # the tg requested TX/actual TX ratio is 1up to 50%, after 50%
    # is linear up 80% actuak TX when requesting 100%
    tg.set_response_curve(lr_dr=20, ndr=50, max_actual_tx=80, max_11_tx=50)
    # tx packets should be half line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(50) == (LR_64B_PPS / 2, 0)
    # at 100% TX requested, actual TX is 80% where the drop rate is 3/5 of 20% of the actual TX
    assert tg.get_tx_pps_dropped_pps(100) == (int(LR_64B_PPS * 0.8),
                                              int(LR_64B_PPS * 0.8 * 0.6 * 0.2))
    results = traffic_client.get_ndr_and_pdr()
    assert_ndr_pdr(results, 100.0, 0.0, 100.781, 0.09374)

def test_ndr_pdr_low_cpu():
    traffic_client = get_traffic_client()
    tg = traffic_client.gen
    # This test is for the case where the TG is underpowered and cannot send fast enough for the NDR
    # true NDR=40%, actual TX at 50% = 30%, actual measured DR is 0%
    # The ndr/pdr should bail out with a warning and a best effort measured NDR of 30%
    tg.set_response_curve(lr_dr=50, ndr=40, max_actual_tx=60, max_11_tx=0)
    # tx packets should be 30% at requested half line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(50) == (int(LR_64B_PPS * 0.3), 0)
    results = traffic_client.get_ndr_and_pdr()
    assert results
    # import pprint
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(results)

import nfvbench.nfvbench

def test_no_openstack():
    config = get_dummy_tg_config('EXT', '1000pps')
    config.openrc_file = None
    old_argv = sys.argv
    sys.argv = [old_argv[0], '-c', json.dumps(config)]
    nfvbench.nfvbench.main()
    sys.argv = old_argv
