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
"""Driver module for TRex traffic generator."""

import math
import os
import sys
import random
import time
import traceback
from functools import reduce

from itertools import count
# pylint: disable=import-error
from scapy.contrib.mpls import MPLS  # flake8: noqa
# pylint: enable=import-error
from nfvbench.log import LOG
from nfvbench.specs import ChainType
from nfvbench.traffic_server import TRexTrafficServer
from nfvbench.utils import cast_integer
from nfvbench.utils import timeout
from nfvbench.utils import TimeoutError

from hdrh.histogram import HdrHistogram

# pylint: disable=import-error
from trex.common.services.trex_service_arp import ServiceARP
from trex.stl.api import ARP
from trex.stl.api import bind_layers
from trex.stl.api import CTRexVmInsFixHwCs
from trex.stl.api import Dot1Q
from trex.stl.api import Ether
from trex.stl.api import FlagsField
from trex.stl.api import IP
from trex.stl.api import Packet
from trex.stl.api import STLClient
from trex.stl.api import STLError
from trex.stl.api import STLFlowLatencyStats
from trex.stl.api import STLFlowStats
from trex.stl.api import STLPktBuilder
from trex.stl.api import STLScVmRaw
from trex.stl.api import STLStream
from trex.stl.api import STLTXCont
from trex.stl.api import STLTXMultiBurst
from trex.stl.api import STLVmFixChecksumHw
from trex.stl.api import STLVmFixIpv4
from trex.stl.api import STLVmFlowVar
from trex.stl.api import STLVmFlowVarRepeatableRandom
from trex.stl.api import STLVmTupleGen
from trex.stl.api import STLVmWrFlowVar
from trex.stl.api import ThreeBytesField
from trex.stl.api import UDP
from trex.stl.api import XByteField

# pylint: enable=import-error

from .traffic_base import AbstractTrafficGenerator
from .traffic_base import TrafficGeneratorException
from . import traffic_utils as utils
from .traffic_utils import IMIX_AVG_L2_FRAME_SIZE
from .traffic_utils import IMIX_L2_SIZES
from .traffic_utils import IMIX_RATIOS

class VXLAN(Packet):
    """VxLAN class."""

    _VXLAN_FLAGS = ['R' * 27] + ['I'] + ['R' * 5]
    name = "VXLAN"
    fields_desc = [FlagsField("flags", 0x08000000, 32, _VXLAN_FLAGS),
                   ThreeBytesField("vni", 0),
                   XByteField("reserved", 0x00)]

    def mysummary(self):
        """Summary."""
        return self.sprintf("VXLAN (vni=%VXLAN.vni%)")

class TRex(AbstractTrafficGenerator):
    """TRex traffic generator driver."""

    LATENCY_PPS = 1000
    CHAIN_PG_ID_MASK = 0x007F
    PORT_PG_ID_MASK = 0x0080
    LATENCY_PG_ID_MASK = 0x0100

    def __init__(self, traffic_client):
        """Trex driver."""
        AbstractTrafficGenerator.__init__(self, traffic_client)
        self.client = None
        self.id = count()
        self.port_handle = []
        self.chain_count = self.generator_config.service_chain_count
        self.rates = []
        self.capture_id = None
        self.packet_list = []
        self.l2_frame_size = 0

    def get_version(self):
        """Get the Trex version."""
        return self.client.get_server_version() if self.client else ''

    def get_pg_id(self, port, chain_id):
        """Calculate the packet group IDs to use for a given port/stream type/chain_id.

        port: 0 or 1
        chain_id: identifies to which chain the pg_id is associated (0 to 255)
        return: pg_id, lat_pg_id

        We use a bit mask to set up the 3 fields:
        0x007F: chain ID (8 bits for a max of 128 chains)
        0x0080: port bit
        0x0100: latency bit
        """
        pg_id = port * TRex.PORT_PG_ID_MASK | chain_id
        return pg_id, pg_id | TRex.LATENCY_PG_ID_MASK

    def extract_stats(self, in_stats, ifstats):
        """Extract stats from dict returned by Trex API.

        :param in_stats: dict as returned by TRex api
        """
        utils.nan_replace(in_stats)
        # LOG.debug(in_stats)

        result = {}
        # port_handles should have only 2 elements: [0, 1]
        # so (1 - ph) will be the index for the far end port
        for ph in self.port_handle:
            stats = in_stats[ph]
            far_end_stats = in_stats[1 - ph]
            result[ph] = {
                'tx': {
                    'total_pkts': cast_integer(stats['opackets']),
                    'total_pkt_bytes': cast_integer(stats['obytes']),
                    'pkt_rate': cast_integer(stats['tx_pps']),
                    'pkt_bit_rate': cast_integer(stats['tx_bps'])
                },
                'rx': {
                    'total_pkts': cast_integer(stats['ipackets']),
                    'total_pkt_bytes': cast_integer(stats['ibytes']),
                    'pkt_rate': cast_integer(stats['rx_pps']),
                    'pkt_bit_rate': cast_integer(stats['rx_bps']),
                    # how many pkts were dropped in RX direction
                    # need to take the tx counter on the far end port
                    'dropped_pkts': cast_integer(
                        far_end_stats['opackets'] - stats['ipackets'])
                }
            }
            self.__combine_latencies(in_stats, result[ph]['rx'], ph)

        total_tx_pkts = result[0]['tx']['total_pkts'] + result[1]['tx']['total_pkts']

        # in case of GARP packets we need to base total_tx_pkts value using flow_stats
        # as no GARP packets have no flow stats and will not be received on the other port
        if self.config.periodic_gratuitous_arp:
            if not self.config.no_flow_stats and not self.config.no_latency_stats:
                global_total_tx_pkts = total_tx_pkts
                total_tx_pkts = 0
                if ifstats:
                    for chain_id, _ in enumerate(ifstats):
                        for ph in self.port_handle:
                            pg_id, lat_pg_id = self.get_pg_id(ph, chain_id)
                            flows_tx_pkts = in_stats['flow_stats'][pg_id]['tx_pkts']['total'] + \
                                            in_stats['flow_stats'][lat_pg_id]['tx_pkts']['total']
                            result[ph]['tx']['total_pkts'] = flows_tx_pkts
                            total_tx_pkts += flows_tx_pkts
                else:
                    for pg_id in in_stats['flow_stats']:
                        if pg_id != 'global':
                            total_tx_pkts += in_stats['flow_stats'][pg_id]['tx_pkts']['total']
                result["garp_total_tx_rate"] = cast_integer(
                    (global_total_tx_pkts - total_tx_pkts) / self.config.duration_sec)
            else:
                LOG.warning("Gratuitous ARP are not received by the other port so TRex and NFVbench"
                            " see these packets as dropped. Please do not activate no_flow_stats"
                            " and no_latency_stats properties to have a better drop rate.")

        result["total_tx_rate"] = cast_integer(total_tx_pkts / self.config.duration_sec)
        # actual offered tx rate in bps
        avg_packet_size = utils.get_average_packet_size(self.l2_frame_size)
        total_tx_bps = utils.pps_to_bps(result["total_tx_rate"], avg_packet_size)
        result['offered_tx_rate_bps'] = total_tx_bps

        result.update(self.get_theoretical_rates(avg_packet_size))

        result["flow_stats"] = in_stats["flow_stats"]
        result["latency"] = in_stats["latency"]

        # Merge HDRHistogram to have an overall value for all chains and ports
        # (provided that the histogram exists in the stats returned by T-Rex)
        # Of course, empty histograms will produce an empty (invalid) histogram.
        try:
            hdrh_list = []
            if ifstats:
                for chain_id, _ in enumerate(ifstats):
                    for ph in self.port_handle:
                        _, lat_pg_id = self.get_pg_id(ph, chain_id)
                        hdrh_list.append(
                            HdrHistogram.decode(in_stats['latency'][lat_pg_id]['latency']['hdrh']))
            else:
                for pg_id in in_stats['latency']:
                    if pg_id != 'global':
                        hdrh_list.append(
                            HdrHistogram.decode(in_stats['latency'][pg_id]['latency']['hdrh']))

            def add_hdrh(x, y):
                x.add(y)
                return x
            decoded_hdrh = reduce(add_hdrh, hdrh_list)
            result["overall_hdrh"] = HdrHistogram.encode(decoded_hdrh).decode('utf-8')
        except KeyError:
            pass

        return result

    def get_stream_stats(self, trex_stats, if_stats, latencies, chain_idx):
        """Extract the aggregated stats for a given chain.

        trex_stats: stats as returned by get_stats()
        if_stats: a list of 2 interface stats to update (port 0 and 1)
        latencies: a list of 2 Latency instances to update for this chain (port 0 and 1)
                   latencies[p] is the latency for packets sent on port p
                   if there are no latency streams, the Latency instances are not modified
        chain_idx: chain index of the interface stats

        The packet counts include normal and latency streams.

        Trex returns flows stats as follows:

        'flow_stats': {0: {'rx_bps': {0: 0, 1: 0, 'total': 0},
                   'rx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                   'rx_bytes': {0: nan, 1: nan, 'total': nan},
                   'rx_pkts': {0: 0, 1: 15001, 'total': 15001},
                   'rx_pps': {0: 0, 1: 0, 'total': 0},
                   'tx_bps': {0: 0, 1: 0, 'total': 0},
                   'tx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                   'tx_bytes': {0: 1020068, 1: 0, 'total': 1020068},
                   'tx_pkts': {0: 15001, 1: 0, 'total': 15001},
                   'tx_pps': {0: 0, 1: 0, 'total': 0}},
               1: {'rx_bps': {0: 0, 1: 0, 'total': 0},
                   'rx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                   'rx_bytes': {0: nan, 1: nan, 'total': nan},
                   'rx_pkts': {0: 0, 1: 15001, 'total': 15001},
                   'rx_pps': {0: 0, 1: 0, 'total': 0},
                   'tx_bps': {0: 0, 1: 0, 'total': 0},
                   'tx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                   'tx_bytes': {0: 1020068, 1: 0, 'total': 1020068},
                   'tx_pkts': {0: 15001, 1: 0, 'total': 15001},
                   'tx_pps': {0: 0, 1: 0, 'total': 0}},
                128: {'rx_bps': {0: 0, 1: 0, 'total': 0},
                'rx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                'rx_bytes': {0: nan, 1: nan, 'total': nan},
                'rx_pkts': {0: 15001, 1: 0, 'total': 15001},
                'rx_pps': {0: 0, 1: 0, 'total': 0},
                'tx_bps': {0: 0, 1: 0, 'total': 0},
                'tx_bps_l1': {0: 0.0, 1: 0.0, 'total': 0.0},
                'tx_bytes': {0: 0, 1: 1020068, 'total': 1020068},
                'tx_pkts': {0: 0, 1: 15001, 'total': 15001},
                'tx_pps': {0: 0, 1: 0, 'total': 0}},etc...

        the pg_id (0, 1, 128,...) is the key of the dict and is obtained using the
        get_pg_id() method.
        packet counters for a given stream sent on port p are reported as:
        - tx_pkts[p] on port p
        - rx_pkts[1-p] on the far end port

        This is a tricky/critical counter transposition operation because
        the results are grouped by port (not by stream):
        tx_pkts_port(p=0) comes from pg_id(port=0, chain_idx)['tx_pkts'][0]
        rx_pkts_port(p=0) comes from pg_id(port=1, chain_idx)['rx_pkts'][0]
        tx_pkts_port(p=1) comes from pg_id(port=1, chain_idx)['tx_pkts'][1]
        rx_pkts_port(p=1) comes from pg_id(port=0, chain_idx)['rx_pkts'][1]

        or using a more generic formula:
        tx_pkts_port(p) comes from pg_id(port=p, chain_idx)['tx_pkts'][p]
        rx_pkts_port(p) comes from pg_id(port=1-p, chain_idx)['rx_pkts'][p]

        the second formula is equivalent to
        rx_pkts_port(1-p) comes from pg_id(port=p, chain_idx)['rx_pkts'][1-p]

        If there are latency streams, those same counters need to be added in the same way
        """
        def get_latency(lval):
            try:
                return int(round(lval))
            except ValueError:
                return 0

        for ifs in if_stats:
            ifs.tx = ifs.rx = 0
        for port in range(2):
            pg_id, lat_pg_id = self.get_pg_id(port, chain_idx)
            for pid in [pg_id, lat_pg_id]:
                try:
                    pg_stats = trex_stats['flow_stats'][pid]
                    if_stats[port].tx += pg_stats['tx_pkts'][port]
                    if_stats[1 - port].rx += pg_stats['rx_pkts'][1 - port]
                except KeyError:
                    pass
            try:
                lat = trex_stats['latency'][lat_pg_id]['latency']
                # dropped_pkts += lat['err_cntrs']['dropped']
                latencies[port].max_usec = get_latency(lat['total_max'])
                if math.isnan(lat['total_min']):
                    latencies[port].min_usec = 0
                    latencies[port].avg_usec = 0
                else:
                    latencies[port].min_usec = get_latency(lat['total_min'])
                    latencies[port].avg_usec = get_latency(lat['average'])
                # pick up the HDR histogram if present (otherwise will raise KeyError)
                latencies[port].hdrh = lat['hdrh']
            except KeyError:
                pass

    def __combine_latencies(self, in_stats, results, port_handle):
        """Traverse TRex result dictionary and combines chosen latency stats.

          example of latency dict returned by trex (2 chains):
         'latency': {256: {'err_cntrs': {'dropped': 0,
                                 'dup': 0,
                                 'out_of_order': 0,
                                 'seq_too_high': 0,
                                 'seq_too_low': 0},
                            'latency': {'average': 26.5,
                                        'hdrh': u'HISTFAAAAEx4nJNpmSgz...bFRgxi',
                                        'histogram': {20: 303,
                                                        30: 320,
                                                        40: 300,
                                                        50: 73,
                                                        60: 4,
                                                        70: 1},
                                        'jitter': 14,
                                        'last_max': 63,
                                        'total_max': 63,
                                        'total_min': 20}},
                    257: {'err_cntrs': {'dropped': 0,
                                        'dup': 0,
                                        'out_of_order': 0,
                                        'seq_too_high': 0,
                                        'seq_too_low': 0},
                            'latency': {'average': 29.75,
                                        'hdrh': u'HISTFAAAAEV4nJN...CALilDG0=',
                                        'histogram': {20: 261,
                                                        30: 431,
                                                        40: 3,
                                                        50: 80,
                                                        60: 225},
                                        'jitter': 23,
                                        'last_max': 67,
                                        'total_max': 67,
                                        'total_min': 20}},
                    384: {'err_cntrs': {'dropped': 0,
                                        'dup': 0,
                                        'out_of_order': 0,
                                        'seq_too_high': 0,
                                        'seq_too_low': 0},
                            'latency': {'average': 18.0,
                                        'hdrh': u'HISTFAAAADR4nJNpm...MjCwDDxAZG',
                                        'histogram': {20: 987, 30: 14},
                                        'jitter': 0,
                                        'last_max': 34,
                                        'total_max': 34,
                                        'total_min': 20}},
                    385: {'err_cntrs': {'dropped': 0,
                                    'dup': 0,
                                    'out_of_order': 0,
                                    'seq_too_high': 0,
                                    'seq_too_low': 0},
                            'latency': {'average': 19.0,
                                        'hdrh': u'HISTFAAAADR4nJNpm...NkYmJgDdagfK',
                                        'histogram': {20: 989, 30: 11},
                                        'jitter': 0,
                                        'last_max': 38,
                                        'total_max': 38,
                                        'total_min': 20}},
                    'global': {'bad_hdr': 0, 'old_flow': 0}},
        """
        total_max = 0
        average = 0
        total_min = float("inf")
        for chain_id in range(self.chain_count):
            try:
                _, lat_pg_id = self.get_pg_id(port_handle, chain_id)
                lat = in_stats['latency'][lat_pg_id]['latency']
                # dropped_pkts += lat['err_cntrs']['dropped']
                total_max = max(lat['total_max'], total_max)
                total_min = min(lat['total_min'], total_min)
                average += lat['average']
            except KeyError:
                pass
        if total_min == float("inf"):
            total_min = 0
        results['min_delay_usec'] = total_min
        results['max_delay_usec'] = total_max
        results['avg_delay_usec'] = int(average / self.chain_count)

    def _bind_vxlan(self):
        bind_layers(UDP, VXLAN, dport=4789)
        bind_layers(VXLAN, Ether)

    def _create_pkt(self, stream_cfg, l2frame_size, disable_random_latency_flow=False):
        """Create a packet of given size.

        l2frame_size: size of the L2 frame in bytes (including the 32-bit FCS)
        """
        # Trex will add the FCS field, so we need to remove 4 bytes from the l2 frame size
        frame_size = int(l2frame_size) - 4
        vm_param = []
        if stream_cfg['vxlan'] is True:
            self._bind_vxlan()
            encap_level = '1'
            pkt_base = Ether(src=stream_cfg['vtep_src_mac'], dst=stream_cfg['vtep_dst_mac'])
            if stream_cfg['vtep_vlan'] is not None:
                pkt_base /= Dot1Q(vlan=stream_cfg['vtep_vlan'])
            pkt_base /= IP(src=stream_cfg['vtep_src_ip'], dst=stream_cfg['vtep_dst_ip'])
            pkt_base /= UDP(sport=random.randint(1337, 32767), dport=4789)
            pkt_base /= VXLAN(vni=stream_cfg['net_vni'])
            pkt_base /= Ether(src=stream_cfg['mac_src'], dst=stream_cfg['mac_dst'])
            # need to randomize the outer header UDP src port based on flow
            vxlan_udp_src_fv = STLVmFlowVar(
                name="vxlan_udp_src",
                min_value=1337,
                max_value=32767,
                size=2,
                op="random")
            vm_param = [vxlan_udp_src_fv,
                        STLVmWrFlowVar(fv_name="vxlan_udp_src", pkt_offset="UDP.sport")]
        elif stream_cfg['mpls'] is True:
            encap_level = '0'
            pkt_base = Ether(src=stream_cfg['vtep_src_mac'], dst=stream_cfg['vtep_dst_mac'])
            if stream_cfg['vtep_vlan'] is not None:
                pkt_base /= Dot1Q(vlan=stream_cfg['vtep_vlan'])
            if stream_cfg['mpls_outer_label'] is not None:
                pkt_base /= MPLS(label=stream_cfg['mpls_outer_label'], cos=1, s=0, ttl=255)
            if stream_cfg['mpls_inner_label'] is not None:
                pkt_base /= MPLS(label=stream_cfg['mpls_inner_label'], cos=1, s=1, ttl=255)
            #  Flow stats and MPLS labels randomization TBD
            pkt_base /= Ether(src=stream_cfg['mac_src'], dst=stream_cfg['mac_dst'])
        else:
            encap_level = '0'
            pkt_base = Ether(src=stream_cfg['mac_src'], dst=stream_cfg['mac_dst'])

        if stream_cfg['vlan_tag'] is not None:
            pkt_base /= Dot1Q(vlan=stream_cfg['vlan_tag'])

        udp_args = {}
        if stream_cfg['udp_src_port']:
            udp_args['sport'] = int(stream_cfg['udp_src_port'])
            if stream_cfg['udp_port_step'] == 'random':
                step = 1
            else:
                step = stream_cfg['udp_port_step']
            udp_args['sport_step'] = int(step)
            udp_args['sport_max'] = int(stream_cfg['udp_src_port_max'])
        if stream_cfg['udp_dst_port']:
            udp_args['dport'] = int(stream_cfg['udp_dst_port'])
            if stream_cfg['udp_port_step'] == 'random':
                step = 1
            else:
                step = stream_cfg['udp_port_step']
            udp_args['dport_step'] = int(step)
            udp_args['dport_max'] = int(stream_cfg['udp_dst_port_max'])

        pkt_base /= IP(src=stream_cfg['ip_src_addr'], dst=stream_cfg['ip_dst_addr']) / \
                    UDP(dport=udp_args['dport'], sport=udp_args['sport'])

        # STLVmTupleGen need flow count >= cores used by TRex, if FC < cores we used STLVmFlowVar
        if stream_cfg['ip_addrs_step'] == '0.0.0.1' and stream_cfg['udp_port_step'] == '1' and \
                stream_cfg['count'] >= self.generator_config.cores:
            src_fv = STLVmTupleGen(ip_min=stream_cfg['ip_src_addr'],
                                   ip_max=stream_cfg['ip_src_addr_max'],
                                   port_min=udp_args['sport'],
                                   port_max=udp_args['sport_max'],
                                   name="tuple_src",
                                   limit_flows=stream_cfg['count'])
            dst_fv = STLVmTupleGen(ip_min=stream_cfg['ip_dst_addr'],
                                   ip_max=stream_cfg['ip_dst_addr_max'],
                                   port_min=udp_args['dport'],
                                   port_max=udp_args['dport_max'],
                                   name="tuple_dst",
                                   limit_flows=stream_cfg['count'])
            vm_param = [
                src_fv,
                STLVmWrFlowVar(fv_name="tuple_src.ip",
                               pkt_offset="IP:{}.src".format(encap_level)),
                STLVmWrFlowVar(fv_name="tuple_src.port",
                               pkt_offset="UDP:{}.sport".format(encap_level)),
                dst_fv,
                STLVmWrFlowVar(fv_name="tuple_dst.ip",
                               pkt_offset="IP:{}.dst".format(encap_level)),
                STLVmWrFlowVar(fv_name="tuple_dst.port",
                               pkt_offset="UDP:{}.dport".format(encap_level)),
            ]
        else:
            if disable_random_latency_flow:
                src_fv_ip = STLVmFlowVar(
                    name="ip_src",
                    min_value=stream_cfg['ip_src_addr'],
                    max_value=stream_cfg['ip_src_addr'],
                    size=4)
                dst_fv_ip = STLVmFlowVar(
                    name="ip_dst",
                    min_value=stream_cfg['ip_dst_addr'],
                    max_value=stream_cfg['ip_dst_addr'],
                    size=4)
            elif stream_cfg['ip_addrs_step'] == 'random':
                src_fv_ip = STLVmFlowVarRepeatableRandom(
                    name="ip_src",
                    min_value=stream_cfg['ip_src_addr'],
                    max_value=stream_cfg['ip_src_addr_max'],
                    size=4,
                    seed=random.randint(0, 32767),
                    limit=stream_cfg['ip_src_count'])
                dst_fv_ip = STLVmFlowVarRepeatableRandom(
                    name="ip_dst",
                    min_value=stream_cfg['ip_dst_addr'],
                    max_value=stream_cfg['ip_dst_addr_max'],
                    size=4,
                    seed=random.randint(0, 32767),
                    limit=stream_cfg['ip_dst_count'])
            else:
                src_fv_ip = STLVmFlowVar(
                    name="ip_src",
                    min_value=stream_cfg['ip_src_addr'],
                    max_value=stream_cfg['ip_src_addr_max'],
                    size=4,
                    op="inc",
                    step=stream_cfg['ip_addrs_step'])
                dst_fv_ip = STLVmFlowVar(
                    name="ip_dst",
                    min_value=stream_cfg['ip_dst_addr'],
                    max_value=stream_cfg['ip_dst_addr_max'],
                    size=4,
                    op="inc",
                    step=stream_cfg['ip_addrs_step'])

            if disable_random_latency_flow:
                src_fv_port = STLVmFlowVar(
                    name="p_src",
                    min_value=udp_args['sport'],
                    max_value=udp_args['sport'],
                    size=2)
                dst_fv_port = STLVmFlowVar(
                    name="p_dst",
                    min_value=udp_args['dport'],
                    max_value=udp_args['dport'],
                    size=2)
            elif stream_cfg['udp_port_step'] == 'random':
                src_fv_port = STLVmFlowVarRepeatableRandom(
                    name="p_src",
                    min_value=udp_args['sport'],
                    max_value=udp_args['sport_max'],
                    size=2,
                    seed=random.randint(0, 32767),
                    limit=stream_cfg['udp_src_count'])
                dst_fv_port = STLVmFlowVarRepeatableRandom(
                    name="p_dst",
                    min_value=udp_args['dport'],
                    max_value=udp_args['dport_max'],
                    size=2,
                    seed=random.randint(0, 32767),
                    limit=stream_cfg['udp_dst_count'])
            else:
                src_fv_port = STLVmFlowVar(
                    name="p_src",
                    min_value=udp_args['sport'],
                    max_value=udp_args['sport_max'],
                    size=2,
                    op="inc",
                    step=udp_args['sport_step'])
                dst_fv_port = STLVmFlowVar(
                    name="p_dst",
                    min_value=udp_args['dport'],
                    max_value=udp_args['dport_max'],
                    size=2,
                    op="inc",
                    step=udp_args['dport_step'])
            vm_param = [
                src_fv_ip,
                STLVmWrFlowVar(fv_name="ip_src", pkt_offset="IP:{}.src".format(encap_level)),
                src_fv_port,
                STLVmWrFlowVar(fv_name="p_src", pkt_offset="UDP:{}.sport".format(encap_level)),
                dst_fv_ip,
                STLVmWrFlowVar(fv_name="ip_dst", pkt_offset="IP:{}.dst".format(encap_level)),
                dst_fv_port,
                STLVmWrFlowVar(fv_name="p_dst", pkt_offset="UDP:{}.dport".format(encap_level)),
            ]
        # Use HW Offload to calculate the outter IP/UDP packet
        vm_param.append(STLVmFixChecksumHw(l3_offset="IP:0",
                                           l4_offset="UDP:0",
                                           l4_type=CTRexVmInsFixHwCs.L4_TYPE_UDP))
        # Use software to fix the inner IP/UDP payload for VxLAN packets
        if int(encap_level):
            vm_param.append(STLVmFixIpv4(offset="IP:1"))
        pad = max(0, frame_size - len(pkt_base)) * 'x'

        return STLPktBuilder(pkt=pkt_base / pad,
                             vm=STLScVmRaw(vm_param, cache_size=int(self.config.cache_size)))

    def _create_gratuitous_arp_pkt(self, stream_cfg):
        """Create a GARP packet.

        """
        pkt_base = Ether(src=stream_cfg['mac_src'], dst="ff:ff:ff:ff:ff:ff")

        if self.config.vxlan or self.config.mpls:
            pkt_base /= Dot1Q(vlan=stream_cfg['vtep_vlan'])
        elif stream_cfg['vlan_tag'] is not None:
            pkt_base /= Dot1Q(vlan=stream_cfg['vlan_tag'])

        pkt_base /= ARP(psrc=stream_cfg['ip_src_tg_gw'], hwsrc=stream_cfg['mac_src'],
                        hwdst=stream_cfg['mac_src'], pdst=stream_cfg['ip_src_tg_gw'])

        return STLPktBuilder(pkt=pkt_base)

    def generate_streams(self, port, chain_id, stream_cfg, l2frame, latency=True,
                         e2e=False):
        """Create a list of streams corresponding to a given chain and stream config.

        port: port where the streams originate (0 or 1)
        chain_id: the chain to which the streams are associated to
        stream_cfg: stream configuration
        l2frame: L2 frame size (including 4-byte FCS) or 'IMIX'
        latency: if True also create a latency stream
        e2e: True if performing "end to end" connectivity check
        """
        streams = []
        pg_id, lat_pg_id = self.get_pg_id(port, chain_id)
        if l2frame == 'IMIX':
            for ratio, l2_frame_size in zip(IMIX_RATIOS, IMIX_L2_SIZES):
                pkt = self._create_pkt(stream_cfg, l2_frame_size)
                if e2e or stream_cfg['mpls']:
                    streams.append(STLStream(packet=pkt,
                                             mode=STLTXCont(pps=ratio)))
                else:
                    if stream_cfg['vxlan'] is True:
                        streams.append(STLStream(packet=pkt,
                                                 flow_stats=STLFlowStats(pg_id=pg_id,
                                                                         vxlan=True)
                                                    if not self.config.no_flow_stats else None,
                                                 mode=STLTXCont(pps=ratio)))
                    else:
                        streams.append(STLStream(packet=pkt,
                                                 flow_stats=STLFlowStats(pg_id=pg_id)
                                                    if not self.config.no_flow_stats else None,
                                                 mode=STLTXCont(pps=ratio)))

            if latency:
                # for IMIX, the latency packets have the average IMIX packet size
                if stream_cfg['ip_addrs_step'] == 'random' or \
                        stream_cfg['udp_port_step'] == 'random':
                    # Force latency flow to only one flow to avoid creating flows
                    # over requested flow count
                    pkt = self._create_pkt(stream_cfg, IMIX_AVG_L2_FRAME_SIZE, True)
                else:
                    pkt = self._create_pkt(stream_cfg, IMIX_AVG_L2_FRAME_SIZE)

        else:
            l2frame_size = int(l2frame)
            pkt = self._create_pkt(stream_cfg, l2frame_size)
            if self.config.periodic_gratuitous_arp:
                requested_pps = int(utils.parse_rate_str(self.rates[0])[
                                        'rate_pps']) - self.config.gratuitous_arp_pps
                if latency:
                    requested_pps -= self.LATENCY_PPS
                stltx_cont = STLTXCont(pps=requested_pps)
            else:
                stltx_cont = STLTXCont()
            if e2e or stream_cfg['mpls']:
                streams.append(STLStream(packet=pkt,
                                         # Flow stats is disabled for MPLS now
                                         # flow_stats=STLFlowStats(pg_id=pg_id),
                                         mode=stltx_cont))
            else:
                if stream_cfg['vxlan'] is True:
                    streams.append(STLStream(packet=pkt,
                                             flow_stats=STLFlowStats(pg_id=pg_id,
                                                                     vxlan=True)
                                                if not self.config.no_flow_stats else None,
                                             mode=stltx_cont))
                else:
                    streams.append(STLStream(packet=pkt,
                                             flow_stats=STLFlowStats(pg_id=pg_id)
                                                if not self.config.no_flow_stats else None,
                                             mode=stltx_cont))
            # for the latency stream, the minimum payload is 16 bytes even in case of vlan tagging
            # without vlan, the min l2 frame size is 64
            # with vlan it is 68
            # This only applies to the latency stream
            if latency:
                if stream_cfg['vlan_tag'] and l2frame_size < 68:
                    l2frame_size = 68
                if stream_cfg['ip_addrs_step'] == 'random' or \
                        stream_cfg['udp_port_step'] == 'random':
                        # Force latency flow to only one flow to avoid creating flows
                        # over requested flow count
                    pkt = self._create_pkt(stream_cfg, l2frame_size, True)
                else:
                    pkt = self._create_pkt(stream_cfg, l2frame_size)

        if latency:
            if self.config.no_latency_stats:
                LOG.info("Latency flow statistics are disabled.")
            if stream_cfg['vxlan'] is True:
                streams.append(STLStream(packet=pkt,
                                         flow_stats=STLFlowLatencyStats(pg_id=lat_pg_id,
                                                                        vxlan=True)
                                            if not self.config.no_latency_stats else None,
                                         mode=STLTXCont(pps=self.LATENCY_PPS)))
            else:
                streams.append(STLStream(packet=pkt,
                                         flow_stats=STLFlowLatencyStats(pg_id=lat_pg_id)
                                            if not self.config.no_latency_stats else None,
                                         mode=STLTXCont(pps=self.LATENCY_PPS)))

        if self.config.periodic_gratuitous_arp and (
                self.config.l3_router or self.config.service_chain == ChainType.EXT):
            # In case of L3 router feature or EXT chain with router
            # and depending on ARP stale time SUT configuration
            # Gratuitous ARP from TG port to the router is needed to keep traffic up
            garp_pkt = self._create_gratuitous_arp_pkt(stream_cfg)
            ibg = self.config.gratuitous_arp_pps * 1000000.0
            packets_count = int(self.config.duration_sec / self.config.gratuitous_arp_pps)
            streams.append(
                STLStream(packet=garp_pkt,
                          mode=STLTXMultiBurst(pkts_per_burst=1, count=packets_count, ibg=ibg)))
        return streams

    @timeout(5)
    def __connect(self, client):
        client.connect()

    def __local_server_status(self):
        """ The TRex server may have started but failed initializing... and stopped.
        This piece of code is especially designed to address
        the case when a fatal failure occurs on a DPDK init call.
        The TRex algorihm should be revised to include some missing timeouts (?)
        status returned:
          0: no error detected
          1: fatal error detected - should lead to exiting the run
          2: error detected that could be solved by starting again
        The diagnostic is based on parsing the local trex log file (improvable)
        """
        status = 0
        message = None
        failure = None
        exited = None
        cause = None
        error = None
        before = None
        after = None
        last = None
        try:
            with open('/tmp/trex.log', 'r', encoding="utf-8") as trex_log:
                for _line in trex_log:
                    line = _line.strip()
                    if line.startswith('Usage:'):
                        break
                    if 'ports are bound' in line:
                        continue
                    if 'please wait' in line:
                        continue
                    if 'exit' in line.lower():
                        exited = line
                    elif 'cause' in line.lower():
                        cause = line
                    elif 'fail' in line.lower():
                        failure = line
                    elif 'msg' in line.lower():
                        message = line
                    elif (error is not None) and line:
                        after = line
                    elif line.startswith('Error:') or line.startswith('ERROR'):
                        error = line
                        before = last
                    last = line
        except FileNotFoundError:
            pass
        if exited is not None:
            status = 1
            LOG.info("\x1b[1m%s\x1b[0m %s", 'TRex failed initializing:', exited)
            if cause is not None:
                LOG.info("TRex [cont'd] %s", cause)
            if failure is not None:
                LOG.info("TRex [cont'd] %s", failure)
            if message is not None:
                LOG.info("TRex [cont'd] %s", message)
                if 'not supported yet' in message.lower():
                    LOG.info("TRex [cont'd] Try starting again!")
                    status = 2
        elif error is not None:
            status = 1
            LOG.info("\x1b[1m%s\x1b[0m %s", 'TRex failed initializing:', error)
            if after is not None:
                LOG.info("TRex [cont'd] %s", after)
            elif before is not None:
                LOG.info("TRex [cont'd] %s", before)
        return status

    def __connect_after_start(self):
        # after start, Trex may take a bit of time to initialize
        # so we need to retry a few times
        # we try to capture recoverable error cases (checking status)
        status = 0
        for it in range(self.config.generic_retry_count):
            try:
                time.sleep(1)
                self.client.connect()
                break
            except Exception as ex:
                if it == (self.config.generic_retry_count - 1):
                    raise
                status = self.__local_server_status()
                if status > 0:
                    # No need to wait anymore, something went wrong and TRex exited
                    if status == 1:
                        LOG.info("\x1b[1m%s\x1b[0m", 'TRex failed starting!')
                        print("More information? Try the command: "
                            + "\x1b[1mnfvbench --show-trex-log\x1b[0m")
                        sys.exit(0)
                    if status == 2:
                        # a new start will follow
                        return status
                LOG.info("Retrying connection to TRex (%s)...", ex.msg)
        return status

    def connect(self):
        """Connect to the TRex server."""
        status = 0
        server_ip = self.generator_config.ip
        LOG.info("Connecting to TRex (%s)...", server_ip)

        # Connect to TRex server
        self.client = STLClient(server=server_ip, sync_port=self.generator_config.zmq_rpc_port,
                                async_port=self.generator_config.zmq_pub_port)
        try:
            self.__connect(self.client)
            if server_ip == '127.0.0.1':
                config_updated = self.__check_config()
                if config_updated or self.config.restart:
                    status = self.__restart()
        except (TimeoutError, STLError) as e:
            if server_ip == '127.0.0.1':
                status = self.__start_local_server()
            else:
                raise TrafficGeneratorException(e.message) from e

        if status == 2:
            # Workaround in case of a failed TRex server initialization
            # we try to start it again (twice maximum)
            # which may allow low level initialization to complete.
            if self.__start_local_server() == 2:
                self.__start_local_server()

        ports = list(self.generator_config.ports)
        self.port_handle = ports
        # Prepare the ports
        self.client.reset(ports)
        # Read HW information from each port
        # this returns an array of dict (1 per port)
        """
        Example of output for Intel XL710
        [{'arp': '-', 'src_ipv4': '-', u'supp_speeds': [40000], u'is_link_supported': True,
          'grat_arp': 'off', 'speed': 40, u'index': 0, 'link_change_supported': 'yes',
          u'rx': {u'counters': 127, u'caps': [u'flow_stats', u'latency']},
          u'is_virtual': 'no', 'prom': 'off', 'src_mac': u'3c:fd:fe:a8:24:48', 'status': 'IDLE',
          u'description': u'Ethernet Controller XL710 for 40GbE QSFP+',
          'dest': u'fa:16:3e:3c:63:04', u'is_fc_supported': False, 'vlan': '-',
          u'driver': u'net_i40e', 'led_change_supported': 'yes', 'rx_filter_mode': 'hardware match',
          'fc': 'none', 'link': 'UP', u'hw_mac': u'3c:fd:fe:a8:24:48', u'pci_addr': u'0000:5e:00.0',
          'mult': 'off', 'fc_supported': 'no', u'is_led_supported': True, 'rx_queue': 'off',
          'layer_mode': 'Ethernet', u'numa': 0}, ...]
        """
        self.port_info = self.client.get_port_info(ports)
        LOG.info('Connected to TRex')
        for id, port in enumerate(self.port_info):
            LOG.info('   Port %d: %s speed=%dGbps mac=%s pci=%s driver=%s',
                     id, port['description'], port['speed'], port['src_mac'],
                     port['pci_addr'], port['driver'])
        # Make sure the 2 ports have the same speed
        if self.port_info[0]['speed'] != self.port_info[1]['speed']:
            raise TrafficGeneratorException('Traffic generator ports speed mismatch: %d/%d Gbps' %
                                            (self.port_info[0]['speed'],
                                             self.port_info[1]['speed']))

    def __start_local_server(self):
        try:
            LOG.info("Starting TRex ...")
            self.__start_server()
            status = self.__connect_after_start()
        except (TimeoutError, STLError) as e:
            LOG.error('Cannot connect to TRex')
            LOG.error(traceback.format_exc())
            logpath = '/tmp/trex.log'
            if os.path.isfile(logpath):
                # Wait for TRex to finish writing error message
                last_size = 0
                for _ in range(self.config.generic_retry_count):
                    size = os.path.getsize(logpath)
                    if size == last_size:
                        # probably not writing anymore
                        break
                    last_size = size
                    time.sleep(1)
                with open(logpath, 'r', encoding="utf-8") as f:
                    message = f.read()
            else:
                message = e.message
            raise TrafficGeneratorException(message) from e
        return status

    def __start_server(self):
        server = TRexTrafficServer()
        server.run_server(self.generator_config)

    def __check_config(self):
        server = TRexTrafficServer()
        return server.check_config_updated(self.generator_config)

    def __restart(self):
        LOG.info("Restarting TRex ...")
        self.__stop_server()
        # Wait for server stopped
        for _ in range(self.config.generic_retry_count):
            time.sleep(1)
            if not self.client.is_connected():
                LOG.info("TRex is stopped...")
                break
        # Start and report a possible failure
        return self.__start_local_server()

    def __stop_server(self):
        if self.generator_config.ip == '127.0.0.1':
            ports = self.client.get_acquired_ports()
            LOG.info('Release ports %s and stopping TRex...', ports)
            try:
                if ports:
                    self.client.release(ports=ports)
                self.client.server_shutdown()
            except STLError as e:
                LOG.warning('Unable to stop TRex. Error: %s', e)
        else:
            LOG.info('Using remote TRex. Unable to stop TRex')

    def resolve_arp(self):
        """Resolve all configured remote IP addresses.

        return: None if ARP failed to resolve for all IP addresses
                else a dict of list of dest macs indexed by port#
                the dest macs in the list are indexed by the chain id
        """
        self.client.set_service_mode(ports=self.port_handle)
        LOG.info('Polling ARP until successful...')
        arp_dest_macs = {}
        for port, device in zip(self.port_handle, self.generator_config.devices):
            # there should be 1 stream config per chain
            stream_configs = device.get_stream_configs()
            chain_count = len(stream_configs)
            ctx = self.client.create_service_ctx(port=port)
            # all dest macs on this port indexed by chain ID
            dst_macs = [None] * chain_count
            dst_macs_count = 0
            # the index in the list is the chain id
            if self.config.vxlan or self.config.mpls:
                arps = [
                    ServiceARP(ctx,
                               src_ip=device.vtep_src_ip,
                               dst_ip=device.vtep_dst_ip,
                               vlan=device.vtep_vlan)
                    for cfg in stream_configs
                ]
            else:
                arps = [
                    ServiceARP(ctx,
                               src_ip=cfg['ip_src_tg_gw'],
                               dst_ip=cfg['mac_discovery_gw'],
                               # will be None if no vlan tagging
                               vlan=cfg['vlan_tag'])
                    for cfg in stream_configs
                ]

            for attempt in range(self.config.generic_retry_count):
                try:
                    ctx.run(arps)
                except STLError:
                    LOG.error(traceback.format_exc())
                    continue

                unresolved = []
                for chain_id, mac in enumerate(dst_macs):
                    if not mac:
                        arp_record = arps[chain_id].get_record()
                        if arp_record.dst_mac:
                            dst_macs[chain_id] = arp_record.dst_mac
                            dst_macs_count += 1
                            LOG.info('   ARP: port=%d chain=%d src IP=%s dst IP=%s -> MAC=%s',
                                     port, chain_id,
                                     arp_record.src_ip,
                                     arp_record.dst_ip, arp_record.dst_mac)
                        else:
                            unresolved.append(arp_record.dst_ip)
                if dst_macs_count == chain_count:
                    arp_dest_macs[port] = dst_macs
                    LOG.info('ARP resolved successfully for port %s', port)
                    break

                retry = attempt + 1
                LOG.info('Retrying ARP for: %s (retry %d/%d)',
                         unresolved, retry, self.config.generic_retry_count)
                if retry < self.config.generic_retry_count:
                    time.sleep(self.config.generic_poll_sec)
            else:
                LOG.error('ARP timed out for port %s (resolved %d out of %d)',
                          port,
                          dst_macs_count,
                          chain_count)
                break

        # A traffic capture may have been started (from a T-Rex console) at this time.
        # If asked so, we keep the service mode enabled here, and disable it otherwise.
        #  | Disabling the service mode while a capture is in progress
        #  | would cause the application to stop/crash with an error.
        if not self.config.service_mode:
            self.client.set_service_mode(ports=self.port_handle, enabled=False)
        if len(arp_dest_macs) == len(self.port_handle):
            return arp_dest_macs
        return None

    def __is_rate_enough(self, l2frame_size, rates, bidirectional, latency):
        """Check if rate provided by user is above requirements. Applies only if latency is True."""
        intf_speed = self.generator_config.intf_speed
        if latency:
            if bidirectional:
                mult = 2
                total_rate = 0
                for rate in rates:
                    r = utils.convert_rates(l2frame_size, rate, intf_speed)
                    total_rate += int(r['rate_pps'])
            else:
                mult = 1
                r = utils.convert_rates(l2frame_size, rates[0], intf_speed)
                total_rate = int(r['rate_pps'])
            # rate must be enough for latency stream and at least 1 pps for base stream per chain
            if self.config.periodic_gratuitous_arp:
                required_rate = (self.LATENCY_PPS + 1 + self.config.gratuitous_arp_pps) \
                                * self.config.service_chain_count * mult
            else:
                required_rate = (self.LATENCY_PPS + 1) * self.config.service_chain_count * mult
            result = utils.convert_rates(l2frame_size,
                                         {'rate_pps': required_rate},
                                         intf_speed * mult)
            result['result'] = total_rate >= required_rate
            return result

        return {'result': True}

    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True, e2e=False):
        """Program all the streams in Trex server.

        l2frame_size: L2 frame size or IMIX
        rates: a list of 2 rates to run each direction
               each rate is a dict like {'rate_pps': '10kpps'}
        bidirectional: True if bidirectional
        latency: True if latency measurement is needed
        e2e: True if performing "end to end" connectivity check
        """
        if self.config.no_flow_stats:
            LOG.info("Traffic flow statistics are disabled.")
        r = self.__is_rate_enough(l2frame_size, rates, bidirectional, latency)
        if not r['result']:
            raise TrafficGeneratorException(
                'Required rate in total is at least one of: \n{pps}pps \n{bps}bps \n{load}%.'
                .format(pps=r['rate_pps'],
                        bps=r['rate_bps'],
                        load=r['rate_percent']))
        self.l2_frame_size = l2frame_size
        # a dict of list of streams indexed by port#
        # in case of fixed size, has self.chain_count * 2 * 2 streams
        # (1 normal + 1 latency stream per direction per chain)
        # for IMIX, has self.chain_count * 2 * 4 streams
        # (3 normal + 1 latency stream per direction per chain)
        streamblock = {}
        for port in self.port_handle:
            streamblock[port] = []
        stream_cfgs = [d.get_stream_configs() for d in self.generator_config.devices]
        if self.generator_config.ip_addrs_step == 'random' \
                or self.generator_config.gen_config.udp_port_step == 'random':
            LOG.warning("Using random step, the number of flows can be less than "
                        "the requested number of flows due to repeatable multivariate random "
                        "generation which can reproduce the same pattern of values")
        self.rates = [utils.to_rate_str(rate) for rate in rates]
        for chain_id, (fwd_stream_cfg, rev_stream_cfg) in enumerate(zip(*stream_cfgs)):
            streamblock[0].extend(self.generate_streams(self.port_handle[0],
                                                        chain_id,
                                                        fwd_stream_cfg,
                                                        l2frame_size,
                                                        latency=latency,
                                                        e2e=e2e))
            if len(self.rates) > 1:
                streamblock[1].extend(self.generate_streams(self.port_handle[1],
                                                            chain_id,
                                                            rev_stream_cfg,
                                                            l2frame_size,
                                                            latency=bidirectional and latency,
                                                            e2e=e2e))

        for port in self.port_handle:
            if self.config.vxlan:
                self.client.set_port_attr(ports=port, vxlan_fs=[4789])
            else:
                self.client.set_port_attr(ports=port, vxlan_fs=None)
            self.client.add_streams(streamblock[port], ports=port)
            LOG.info('Created %d traffic streams for port %s.', len(streamblock[port]), port)

    def clear_streamblock(self):
        """Clear all streams from TRex."""
        self.rates = []
        self.client.reset(self.port_handle)
        LOG.info('Cleared all existing streams')

    def get_stats(self, ifstats=None):
        """Get stats from Trex."""
        stats = self.client.get_stats()
        return self.extract_stats(stats, ifstats)

    def get_macs(self):
        """Return the Trex local port MAC addresses.

        return: a list of MAC addresses indexed by the port#
        """
        return [port['src_mac'] for port in self.port_info]

    def get_port_speed_gbps(self):
        """Return the Trex local port MAC addresses.

        return: a list of speed in Gbps indexed by the port#
        """
        return [port['speed'] for port in self.port_info]

    def clear_stats(self):
        """Clear all stats in the traffic gneerator."""
        if self.port_handle:
            self.client.clear_stats()

    def start_traffic(self):
        """Start generating traffic in all ports."""
        for port, rate in zip(self.port_handle, self.rates):
            self.client.start(ports=port, mult=rate, duration=self.config.duration_sec, force=True)

    def stop_traffic(self):
        """Stop generating traffic."""
        self.client.stop(ports=self.port_handle)

    def start_capture(self):
        """Capture all packets on both ports that are unicast to us."""
        if self.capture_id:
            self.stop_capture()
        # Need to filter out unwanted packets so we do not end up counting
        # src MACs of frames that are not unicast to us
        src_mac_list = self.get_macs()
        bpf_filter = "ether dst %s or ether dst %s" % (src_mac_list[0], src_mac_list[1])
        # ports must be set in service in order to enable capture
        self.client.set_service_mode(ports=self.port_handle)
        self.capture_id = self.client.start_capture \
            (rx_ports=self.port_handle, bpf_filter=bpf_filter)

    def fetch_capture_packets(self):
        """Fetch capture packets in capture mode."""
        if self.capture_id:
            self.packet_list = []
            self.client.fetch_capture_packets(capture_id=self.capture_id['id'],
                                              output=self.packet_list)

    def stop_capture(self):
        """Stop capturing packets."""
        if self.capture_id:
            self.client.stop_capture(capture_id=self.capture_id['id'])
            self.capture_id = None
            # A traffic capture may have been started (from a T-Rex console) at this time.
            # If asked so, we keep the service mode enabled here, and disable it otherwise.
            #  | Disabling the service mode while a capture is in progress
            #  | would cause the application to stop/crash with an error.
            if not self.config.service_mode:
                self.client.set_service_mode(ports=self.port_handle, enabled=False)

    def cleanup(self):
        """Cleanup Trex driver."""
        if self.client:
            try:
                self.client.reset(self.port_handle)
                self.client.disconnect()
            except STLError:
                # TRex does not like a reset while in disconnected state
                pass

    def set_service_mode(self, enabled=True):
        """Enable/disable the 'service' mode."""
        self.client.set_service_mode(ports=self.port_handle, enabled=enabled)
