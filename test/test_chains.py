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
"""Test Chaining functions."""

from mock import MagicMock
from mock import patch
import pytest

from .mock_trex import no_op

from nfvbench.chain_runner import ChainRunner
from nfvbench.chaining import ChainException
from nfvbench.chaining import ChainVnfPort
from nfvbench.chaining import InstancePlacer
from nfvbench.compute import Compute
import nfvbench.credentials
from nfvbench.factory import BasicFactory
import nfvbench.log
from nfvbench.nfvbench import load_default_config
from nfvbench.nfvbench import NFVBench
from nfvbench.packet_stats import InterfaceStats
from nfvbench.specs import ChainType
from nfvbench.specs import OpenStackSpec
from nfvbench.specs import Specs
from nfvbench.summarizer import _annotate_chain_stats
from nfvbench.traffic_client import TrafficClient
from nfvbench.traffic_gen.traffic_base import Latency
from nfvbench.traffic_gen.trex_gen import TRex

# just to get rid of the unused function warning
no_op()


def setup_module(module):
    """Enable log."""
    nfvbench.log.setup(mute_stdout=False)
    nfvbench.log.set_level(debug=True)

def _get_chain_config(sc=ChainType.PVP, scc=1, shared_net=True, rate='1Mpps'):
    config, _ = load_default_config()
    config.vm_image_file = 'nfvbenchvm-0.0.qcow2'
    config.service_chain_count = scc
    config.service_chain = sc
    config.service_chain_shared_net = shared_net
    config.rate = rate
    config['traffic_generator']['generator_profile'] = [{'name': 'dummy',
                                                         'tool': 'dummy',
                                                         'ip': '127.0.0.1',
                                                         'intf_speed': '10Gbps',
                                                         'interfaces': [{'port': 0, 'pci': '0.0'},
                                                                        {'port': 1, 'pci': '0.0'}]}]
    config.ndr_run = False
    config.pdr_run = False
    config.single_run = True
    config.generator_profile = 'dummy'
    config.duration_sec = 2
    config.interval_sec = 1
    config.openrc_file = "dummy.rc"
    config.no_flow_stats = False
    config.no_latency_stats = False
    config.no_latency_streams = False
    return config

def test_chain_runner_ext_no_openstack():
    """Test ChainRunner EXT no openstack."""
    config = _get_chain_config(sc=ChainType.EXT)
    specs = Specs()
    config.vlans = [100, 200]
    config['traffic_generator']['mac_addrs_left'] = ['00:00:00:00:00:00']
    config['traffic_generator']['mac_addrs_right'] = ['00:00:00:00:01:00']

    for shared_net in [True, False]:
        for no_arp in [False, True]:
            for vlan_tag in [False, True]:
                for scc in [1, 2]:
                    config = _get_chain_config(ChainType.EXT, scc, shared_net)
                    config.no_arp = no_arp
                    if no_arp:
                        # If EXT and no arp, the config must provide mac (1 pair per chain)
                        config['traffic_generator']['mac_addrs_left'] = ['00:00:00:00:00:00'] * scc
                        config['traffic_generator']['mac_addrs_right'] = ['00:00:00:00:01:00'] * scc
                    config['vlan_tagging'] = vlan_tag
                    if vlan_tag:
                        # these are the 2 valid forms of vlan ranges
                        if scc == 1:
                            config.vlans = [100, 200]
                        else:
                            config.vlans = [[port * 100 + index for index in range(scc)]
                                            for port in range(2)]
                    runner = ChainRunner(config, None, specs, BasicFactory())
                    runner.close()


def _mock_find_image(self, image_name):
    return MagicMock()

@patch.object(Compute, 'find_image', _mock_find_image)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
def _test_pvp_chain(config, cred, mock_glance, mock_neutron, mock_client):
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.create_network.return_value = {'network': netw}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': None}
    specs = Specs()
    openstack_spec = OpenStackSpec()
    specs.set_openstack_spec(openstack_spec)
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = True
    runner = ChainRunner(config, cred, specs, BasicFactory())
    runner.close()

def test_pvp_chain_runner():
    """Test PVP chain runner."""
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = True
    for shared_net in [True, False]:
        for sc in [ChainType.PVP]:
            for scc in [1, 2]:
                config = _get_chain_config(sc, scc, shared_net)
                _test_pvp_chain(config, cred)


# Test not admin exception with empty value is raised
@patch.object(Compute, 'find_image', _mock_find_image)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
def _test_pvp_chain_no_admin_no_config_values(config, cred, mock_glance, mock_neutron, mock_client):
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.create_network.return_value = {'network': netw}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': None}
    specs = Specs()
    openstack_spec = OpenStackSpec()
    specs.set_openstack_spec(openstack_spec)
    runner = ChainRunner(config, cred, specs, BasicFactory())
    runner.close()

def test_pvp_chain_runner_no_admin_no_config_values():
    """Test PVP/mock chain runner."""
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = False
    for shared_net in [True, False]:
        for sc in [ChainType.PVP]:
            for scc in [1, 2]:
                config = _get_chain_config(sc, scc, shared_net)
                with pytest.raises(ChainException):
                    _test_pvp_chain_no_admin_no_config_values(config, cred)

# Test not admin with mandatory parameters values in config file
@patch.object(Compute, 'find_image', _mock_find_image)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
def _test_pvp_chain_no_admin_config_values(config, cred, mock_glance, mock_neutron, mock_client):
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.create_network.return_value = {'network': netw}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': None}
    specs = Specs()
    openstack_spec = OpenStackSpec()
    specs.set_openstack_spec(openstack_spec)
    runner = ChainRunner(config, cred, specs, BasicFactory())
    runner.close()

def test_pvp_chain_runner_no_admin_config_values():
    """Test PVP chain runner."""
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = False
    for shared_net in [True, False]:
        for sc in [ChainType.PVP]:
            for scc in [1, 2]:
                config = _get_chain_config(sc, scc, shared_net)
                config.availability_zone = "az"
                config.hypervisor_hostname = "server"
                # these are the 2 valid forms of vlan ranges
                if scc == 1:
                    config.vlans = [100, 200]
                else:
                    config.vlans = [[port * 100 + index for index in range(scc)]
                                    for port in range(2)]
                _test_pvp_chain_no_admin_config_values(config, cred)


@patch.object(Compute, 'find_image', _mock_find_image)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
def _test_ext_chain(config, cred, mock_glance, mock_neutron, mock_client):
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': [netw]}
    specs = Specs()
    openstack_spec = OpenStackSpec()
    specs.set_openstack_spec(openstack_spec)
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = True
    runner = ChainRunner(config, cred, specs, BasicFactory())
    runner.close()

def test_ext_chain_runner():
    """Test openstack+EXT chain runner.

    Test 8 combinations of configs:
    shared/not shared net x arp/no_arp x scc 1 or 2
    """
    cred = MagicMock(spec=nfvbench.credentials.Credentials)
    cred.is_admin = True
    for shared_net in [True, False]:
        for no_arp in [False, True]:
            for scc in [1, 2]:
                config = _get_chain_config(ChainType.EXT, scc, shared_net)
                config.no_arp = no_arp
                # this time use a tuple of network names
                config['external_networks']['left'] = ('ext-lnet00', 'ext-lnet01')
                config['external_networks']['right'] = ('ext-rnet00', 'ext-rnet01')
                if no_arp:
                    # If EXT and no arp, the config must provide mac addresses (1 pair per chain)
                    config['traffic_generator']['mac_addrs_left'] = ['00:00:00:00:00:00'] * scc
                    config['traffic_generator']['mac_addrs_right'] = ['00:00:00:00:01:00'] * scc
                _test_ext_chain(config, cred)

def _check_nfvbench_openstack(sc=ChainType.PVP, l2_loopback=False):
    for scc in range(1, 3):
        config = _get_chain_config(sc, scc=scc, shared_net=True)
        if l2_loopback:
            config.l2_loopback = True
            config.vlans = [[100], [200]]
        if sc == ChainType.EXT:
            config['external_networks']['left'] = 'ext-lnet'
            config['external_networks']['right'] = 'ext-rnet'
        factory = BasicFactory()
        config_plugin = factory.get_config_plugin_class()(config)
        config = config_plugin.get_config()
        openstack_spec = config_plugin.get_openstack_spec()
        nfvb = NFVBench(config, openstack_spec, config_plugin, factory)
        res = nfvb.run({}, 'pytest')
        if res['status'] != 'OK':
            print(res)
        assert res['status'] == 'OK'


mac_seq = 0

def _mock_get_mac(dummy):
    global mac_seq
    mac_seq += 1
    return '01:00:00:00:00:%02x' % mac_seq

@patch.object(Compute, 'find_image', _mock_find_image)
@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
@patch.object(ChainVnfPort, 'get_mac', _mock_get_mac)
@patch.object(TrafficClient, 'is_udp', lambda x, y: True)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
@patch('nfvbench.nfvbench.credentials')
def test_nfvbench_run(mock_cred, mock_glance, mock_neutron, mock_client):
    """Test NFVbench class with openstack+PVP."""
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.create_network.return_value = {'network': netw}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': None}
    _check_nfvbench_openstack()

@patch.object(Compute, 'find_image', _mock_find_image)
@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
@patch.object(TrafficClient, 'is_udp', lambda x, y: True)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
@patch('nfvbench.nfvbench.credentials')
def test_nfvbench_ext_arp(mock_cred, mock_glance, mock_neutron, mock_client):
    """Test NFVbench class with openstack+EXT+ARP."""
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    netw = {'id': 0, 'provider:network_type': 'vlan', 'provider:segmentation_id': 1000}
    mock_neutron.Client.return_value.list_networks.return_value = {'networks': [netw]}
    _check_nfvbench_openstack(sc=ChainType.EXT)

@patch.object(Compute, 'find_image', _mock_find_image)
@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
@patch.object(TrafficClient, 'is_udp', lambda x, y: True)
@patch('nfvbench.chaining.Client')
@patch('nfvbench.chaining.neutronclient')
@patch('nfvbench.chaining.glanceclient')
@patch('nfvbench.nfvbench.credentials')
def test_nfvbench_l2_loopback(mock_cred, mock_glance, mock_neutron, mock_client):
    """Test NFVbench class with l2-loopback."""
    # instance = self.novaclient.servers.create(name=vmname,...)
    # instance.status == 'ACTIVE'
    mock_client.return_value.servers.create.return_value.status = 'ACTIVE'
    _check_nfvbench_openstack(l2_loopback=True)


# This is a reduced version of flow stats coming from Trex
# with 2 chains and latency for a total of 8 packet groups
# Random numbers with random losses
CH0_P0_TX = 1234
CH0_P1_RX = 1200
CH0_P1_TX = 28900
CH0_P0_RX = 28000
LCH0_P0_TX = 167
LCH0_P1_RX = 130
LCH0_P1_TX = 523
LCH0_P0_RX = 490
CH1_P0_TX = 132344
CH1_P1_RX = 132004
CH1_P1_TX = 1289300
CH1_P0_RX = 1280400
LCH1_P0_TX = 51367
LCH1_P1_RX = 5730
LCH1_P1_TX = 35623
LCH1_P0_RX = 67

TREX_STATS = {
    'flow_stats': {
        # chain 0 port 0 normal stream
        0: {'rx_pkts': {0: 0, 1: CH0_P1_RX, 'total': CH0_P1_RX},
            'tx_pkts': {0: CH0_P0_TX, 1: 0, 'total': CH0_P0_TX}},
        # chain 1 port 0 normal stream
        1: {'rx_pkts': {0: 0, 1: CH1_P1_RX, 'total': CH1_P1_RX},
            'tx_pkts': {0: CH1_P0_TX, 1: 0, 'total': CH1_P0_TX}},
        # chain 0 port 1 normal stream
        128: {'rx_pkts': {0: CH0_P0_RX, 1: 0, 'total': CH0_P0_RX},
              'tx_pkts': {0: 0, 1: CH0_P1_TX, 'total': CH0_P1_TX}},
        # chain 1 port 1 normal stream
        129: {'rx_pkts': {0: CH1_P0_RX, 1: 0, 'total': CH1_P0_RX},
              'tx_pkts': {0: 0, 1: CH1_P1_TX, 'total': CH1_P1_TX}},
        # chain 0 port 0 latency stream
        256: {'rx_pkts': {0: 0, 1: LCH0_P1_RX, 'total': LCH0_P1_RX},
              'tx_pkts': {0: LCH0_P0_TX, 1: 0, 'total': LCH0_P0_TX}},
        # chain 1 port 0 latency stream
        257: {'rx_pkts': {0: 0, 1: LCH1_P1_RX, 'total': LCH1_P1_RX},
              'tx_pkts': {0: LCH1_P0_TX, 1: 0, 'total': LCH1_P0_TX}},
        # chain 0 port 1 latency stream
        384: {'rx_pkts': {0: LCH0_P0_RX, 1: 0, 'total': LCH0_P0_RX},
              'tx_pkts': {0: 0, 1: LCH0_P1_TX, 'total': LCH0_P1_TX}},
        # chain 1 port 1 latency stream
        385: {'rx_pkts': {0: LCH1_P0_RX, 1: 0, 'total': LCH1_P0_RX},
              'tx_pkts': {0: 0, 1: LCH1_P1_TX, 'total': LCH1_P1_TX}}}}

def test_trex_streams_stats():
    """Test TRex stats for chains 0 and 1."""
    traffic_client = MagicMock()
    trex = TRex(traffic_client)
    if_stats = [InterfaceStats("p0", "dev0"), InterfaceStats("p1", "dev1")]
    latencies = [Latency()] * 2
    trex.get_stream_stats(TREX_STATS, if_stats, latencies, 0)
    assert if_stats[0].tx == CH0_P0_TX + LCH0_P0_TX
    assert if_stats[0].rx == CH0_P0_RX + LCH0_P0_RX
    assert if_stats[1].tx == CH0_P1_TX + LCH0_P1_TX
    assert if_stats[1].rx == CH0_P1_RX + LCH0_P1_RX

    trex.get_stream_stats(TREX_STATS, if_stats, latencies, 1)
    assert if_stats[0].tx == CH1_P0_TX + LCH1_P0_TX
    assert if_stats[0].rx == CH1_P0_RX + LCH1_P0_RX
    assert if_stats[1].tx == CH1_P1_TX + LCH1_P1_TX
    assert if_stats[1].rx == CH1_P1_RX + LCH1_P1_RX

def check_placer(az, hyp, req_az, resolved=False):
    """Combine multiple combinatoons of placer tests."""
    placer = InstancePlacer(az, hyp)
    assert placer.is_resolved() == resolved
    assert placer.get_required_az() == req_az
    assert placer.register_full_name('nova:comp1')
    assert placer.is_resolved()
    assert placer.get_required_az() == 'nova:comp1'

def test_placer_no_user_pref():
    """Test placement when user does not provide any preference."""
    check_placer(None, None, '')

def test_placer_user_az():
    """Test placement when user only provides an az."""
    check_placer('nova', None, 'nova:')
    check_placer(None, 'nova:', 'nova:')
    check_placer('nebula', 'nova:', 'nova:')

def test_placer_user_hyp():
    """Test placement when user provides a hypervisor."""
    check_placer(None, 'comp1', ':comp1')
    check_placer('nova', 'comp1', 'nova:comp1', resolved=True)
    check_placer(None, 'nova:comp1', 'nova:comp1', resolved=True)
    # hyp overrides az
    check_placer('nebula', 'nova:comp1', 'nova:comp1', resolved=True)
    # also check for cases of extra parts (more than 1 ':')
    check_placer('nova:nebula', 'comp1', 'nova:comp1', resolved=True)


def test_placer_negative():
    """Run negative tests on placer."""
    # AZ mismatch
    with pytest.raises(Exception):
        placer = InstancePlacer('nova', None)
        placer.register('nebula:comp1')
    # comp mismatch
    with pytest.raises(Exception):
        placer = InstancePlacer(None, 'comp1')
        placer.register('nebula:comp2')


# without total, with total and only 2 col
CHAIN_STATS = [{0: {'packets': [2000054, 1999996, 1999996]}},
               {0: {'packets': [2000054, 1999996, 1999996]},
                1: {'packets': [2000054, 2000054, 2000054]},
                'total': {'packets': [4000108, 4000050, 4000050]}},
               {0: {'packets': [2000054, 2000054]}},
               {0: {'packets': [2000054, 1999996]}},
               # shared networks no drops, shared nets will have empty strings
               {0: {'packets': [15000002, '', 15000002, 15000002, '', 15000002]},
                1: {'packets': [15000002, '', 15000002, 15000002, '', 15000002]},
                'total': {'packets': [30000004, 30000004, 30000004, 30000004, 30000004, 30000004]}},
               {0: {'packets': [15000002, '', 14000002, 14000002, '', 13000002]},
                1: {'packets': [15000002, '', 15000002, 15000002, '', 15000002]},
                'total': {'packets': [30000004, 29000004, 29000004, 29000004, 29000004, 28000004]}},
               # example with non-available rx count in last position
               {0: {'packets': [2000054, 1999996, None]},
                1: {'packets': [2000054, 2000054, None]},
                'total': {'packets': [4000108, 4000050, 4000050]}}]
XP_CHAIN_STATS = [{0: {'packets': [2000054, '-58 (-0.0029%)', 1999996]}},
                  {0: {'packets': [2000054, '-58 (-0.0029%)', 1999996]},
                   1: {'packets': [2000054, '=>', 2000054]},
                   'total': {'packets': [4000108, '-58 (-0.0014%)', 4000050]}},
                  {0: {'packets': [2000054, 2000054]}},
                  {0: {'packets': [2000054, '-58 (-0.0029%)']}},
                  # shared net, leave spaces alone
                  {0: {'packets': [15000002, '', '=>', '=>', '', 15000002]},
                   1: {'packets': [15000002, '', '=>', '=>', '', 15000002]},
                   'total': {'packets': [30000004, '=>', '=>', '=>', '=>', 30000004]}},
                  {0: {'packets': [15000002, '', '-1,000,000 (-6.6667%)', '=>', '',
                                   '-1,000,000 (-7.1429%)']},
                   1: {'packets': [15000002, '', '=>', '=>', '', 15000002]},
                   'total': {'packets': [30000004, '-1,000,000 (-3.3333%)', '=>', '=>', '=>',
                                         '-1,000,000 (-3.4483%)']}},
                  {0: {'packets': [2000054, '-58 (-0.0029%)', 'n/a']},
                   1: {'packets': [2000054, '=>', 'n/a']},
                   'total': {'packets': [4000108, '-58 (-0.0014%)', 4000050]}}]


def test_summarizer():
    """Test Summarizer class."""
    for stats, exp_stats in zip(CHAIN_STATS, XP_CHAIN_STATS):
        _annotate_chain_stats(stats)
        assert stats == exp_stats

@patch.object(TrafficClient, 'skip_sleep', lambda x: True)
@patch.object(TrafficClient, 'is_udp', lambda x, y: True)
def test_fixed_rate_no_openstack():
    """Test FIxed Rate run - no openstack."""
    config = _get_chain_config(ChainType.EXT, 1, True, rate='100%')
    specs = Specs()
    config.vlans = [100, 200]
    config['traffic_generator']['mac_addrs_left'] = ['00:00:00:00:00:00']
    config['traffic_generator']['mac_addrs_right'] = ['00:00:00:00:01:00']
    config.no_arp = True
    config['vlan_tagging'] = True
    config['traffic'] = {'profile': 'profile_64',
                         'bidirectional': True}
    config['traffic_profile'] = [{'name': 'profile_64', 'l2frame_size': ['64']}]

    runner = ChainRunner(config, None, specs, BasicFactory())
    tg = runner.traffic_client.gen

    tg.set_response_curve(lr_dr=0, ndr=100, max_actual_tx=50, max_11_tx=50)
    # tx packets should be 50% at requested 50% line rate or higher for 64B and no drops...
    results = runner.run()
    assert results
    # pprint.pprint(results['EXT']['result']['result']['64'])
    runner.close()
