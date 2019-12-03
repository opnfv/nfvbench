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
import sys

from attrdict import AttrDict
from mock import patch
import pytest

from nfvbench.config import config_loads
from nfvbench.credentials import Credentials
from nfvbench.fluentd import FluentLogHandler
import nfvbench.log
import nfvbench.nfvbench
from nfvbench.traffic_client import Device
from nfvbench.traffic_client import GeneratorConfig
from nfvbench.traffic_client import IpBlock
from nfvbench.traffic_client import TrafficClient
import nfvbench.traffic_gen.traffic_utils as traffic_utils

from .mock_trex import no_op

# just to get rid of the unused function warning
no_op()

def setup_module(module):
    """Enable log."""
    nfvbench.log.setup(mute_stdout=True)

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
    """Assert if a value is equivalent to a reference value with given margin.

    :param float reference: reference value to compare to
    :param float value: value to compare to reference
    :param float allowance_pct: max allowed percentage of margin
        0 : requires exact match
        1 : must be equal within 1% of the reference value
        ...
        100: always true
    """
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

# =========================================================================
# Other tests
# =========================================================================

def test_no_credentials():
    cred = Credentials('/completely/wrong/path/openrc', None, False)
    if cred.rc_auth_url:
        # shouldn't get valid data unless user set environment variables
        assert False
    else:
        assert True

def test_ip_block():
    ipb = IpBlock('10.0.0.0', '0.0.0.1', 256)
    assert ipb.get_ip() == '10.0.0.0'
    assert ipb.get_ip(255) == '10.0.0.255'
    with pytest.raises(IndexError):
        ipb.get_ip(256)
    ipb = IpBlock('10.0.0.0', '0.0.0.1', 1)
    assert ipb.get_ip() == '10.0.0.0'
    with pytest.raises(IndexError):
        ipb.get_ip(1)

    ipb = IpBlock('10.0.0.0', '0.0.0.2', 256)
    assert ipb.get_ip() == '10.0.0.0'
    assert ipb.get_ip(1) == '10.0.0.2'
    assert ipb.get_ip(127) == '10.0.0.254'
    assert ipb.get_ip(128) == '10.0.1.0'
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

def check_stream_configs(gen_config):
    """Verify that the range for each chain have adjacent IP ranges without holes between chains."""
    config = gen_config.config
    tgc = config['traffic_generator']
    step = Device.ip_to_int(tgc['ip_addrs_step'])
    cfc = 0
    sip = Device.ip_to_int(tgc['ip_addrs'][0].split('/')[0])
    dip = Device.ip_to_int(tgc['ip_addrs'][1].split('/')[0])
    stream_configs = gen_config.devices[0].get_stream_configs()
    for index in range(config['service_chain_count']):
        stream_cfg = stream_configs[index]
        assert stream_cfg['ip_src_count'] == stream_cfg['ip_dst_count']
        assert Device.ip_to_int(stream_cfg['ip_src_addr']) == sip
        assert Device.ip_to_int(stream_cfg['ip_dst_addr']) == dip
        count = stream_cfg['ip_src_count']
        cfc += count
        sip += count * step
        dip += count * step
    assert cfc == int(config['flow_count'] / 2)

def _check_device_flow_config(step_ip):
    config = _get_dummy_tg_config('PVP', '1Mpps', scc=10, fc=99999, step_ip=step_ip)
    gen_config = GeneratorConfig(config)
    check_stream_configs(gen_config)

def test_device_flow_config():
    _check_device_flow_config('0.0.0.1')
    _check_device_flow_config('0.0.0.2')

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
        assert expected in str(e_info)

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

def _get_dummy_tg_config(chain_type, rate, scc=1, fc=10, step_ip='0.0.0.1',
                         ip0='10.0.0.0/8', ip1='20.0.0.0/8'):
    return AttrDict({
        'traffic_generator': {'host_name': 'nfvbench_tg',
                              'default_profile': 'dummy',
                              'generator_profile': [{'name': 'dummy',
                                                     'tool': 'dummy',
                                                     'ip': '127.0.0.1',
                                                     'intf_speed': '10Gbps',
                                                     'interfaces': [{'port': 0, 'pci': '0.0'},
                                                                    {'port': 1, 'pci': '0.0'}]}],
                              'ip_addrs_step': step_ip,
                              'ip_addrs': [ip0, ip1],
                              'tg_gateway_ip_addrs': ['1.1.0.100', '2.2.0.100'],
                              'tg_gateway_ip_addrs_step': step_ip,
                              'gateway_ip_addrs': ['1.1.0.2', '2.2.0.2'],
                              'gateway_ip_addrs_step': step_ip,
                              'mac_addrs_left': None,
                              'mac_addrs_right': None,
                              'udp_src_port': None,
                              'udp_dst_port': None},
        'traffic': {'profile': 'profile_64',
                    'bidirectional': True},
        'traffic_profile': [{'name': 'profile_64', 'l2frame_size': ['64']}],
        'generator_profile': None,
        'service_chain': chain_type,
        'service_chain_count': scc,
        'flow_count': fc,
        'vlan_tagging': True,
        'no_arp': False,
        'duration_sec': 1,
        'interval_sec': 1,
        'pause_sec': 1,
        'rate': rate,
        'check_traffic_time_sec': 200,
        'generic_poll_sec': 2,
        'measurement': {'NDR': 0.001, 'PDR': 0.1, 'load_epsilon': 0.1},
        'l2_loopback': False,
        'cores': None,
        'mbuf_factor': None,
        'disable_hdrh': None,
        'mbuf_64': None,
        'service_mode': False,
        'no_flow_stats': False,
        'no_latency_stats': False,
        'no_latency_streams': False

    })

def _get_traffic_client():
    config = _get_dummy_tg_config('PVP', 'ndr_pdr')
    config['vxlan'] = False
    config['ndr_run'] = True
    config['pdr_run'] = True
    config['generator_profile'] = 'dummy'
    config['single_run'] = False
    traffic_client = TrafficClient(config)
    traffic_client.start_traffic_generator()
    traffic_client.set_traffic('64', True)
    return traffic_client

@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
def test_ndr_at_lr():
    """Test NDR at line rate."""
    traffic_client = _get_traffic_client()
    tg = traffic_client.gen
    # this is a perfect sut with no loss at LR
    tg.set_response_curve(lr_dr=0, ndr=100, max_actual_tx=100, max_11_tx=100)
    # tx packets should be line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(100) == (LR_64B_PPS, 0)
    # NDR and PDR should be at 100%
    # traffic_client.ensure_end_to_end()
    results = traffic_client.get_ndr_and_pdr()
    assert_ndr_pdr(results, 200.0, 0.0, 200.0, 0.0)

@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
def test_ndr_at_50():
    """Test NDR at 50% line rate.

    This is a sut with an NDR of 50% and linear drop rate after NDR up to 20% drops at LR
    (meaning that if you send 100% TX, you will only receive 80% RX)
    the tg requested TX/actual TX ratio is up to 50%, after 50%
    is linear up 80% actuak TX when requesting 100%
    """
    traffic_client = _get_traffic_client()
    tg = traffic_client.gen

    tg.set_response_curve(lr_dr=20, ndr=50, max_actual_tx=80, max_11_tx=50)
    # tx packets should be half line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(50) == (LR_64B_PPS / 2, 0)
    # at 100% TX requested, actual TX is 80% where the drop rate is 3/5 of 20% of the actual TX
    assert tg.get_tx_pps_dropped_pps(100) == (int(LR_64B_PPS * 0.8),
                                              int(LR_64B_PPS * 0.8 * 0.6 * 0.2))
    results = traffic_client.get_ndr_and_pdr()
    assert_ndr_pdr(results, 100.0, 0.0, 100.781, 0.09374)

@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
def test_ndr_pdr_low_cpu():
    """Test NDR and PDR with too low cpu.

    This test is for the case where the TG is underpowered and cannot send fast enough for the NDR
    true NDR=40%, actual TX at 50% = 30%, actual measured DR is 0%
    The ndr/pdr should bail out with a warning and a best effort measured NDR of 30%
    """
    traffic_client = _get_traffic_client()
    tg = traffic_client.gen
    tg.set_response_curve(lr_dr=50, ndr=40, max_actual_tx=60, max_11_tx=0)
    # tx packets should be 30% at requested half line rate for 64B and no drops...
    assert tg.get_tx_pps_dropped_pps(50) == (int(LR_64B_PPS * 0.3), 0)
    results = traffic_client.get_ndr_and_pdr()
    assert results
    # import pprint
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(results)

@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
def test_no_openstack():
    """Test nfvbench using main."""
    config = _get_dummy_tg_config('EXT', '1000pps')
    config.openrc_file = None
    config.vlans = [[100], [200]]
    config['traffic_generator']['mac_addrs_left'] = ['00:00:00:00:00:00']
    config['traffic_generator']['mac_addrs_right'] = ['00:00:00:00:01:00']
    del config['generator_profile']
    old_argv = sys.argv
    sys.argv = [old_argv[0], '-c', json.dumps(config)]
    nfvbench.nfvbench.main()
    sys.argv = old_argv
