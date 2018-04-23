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

import os
import random
import time
import traceback

from collections import defaultdict
from itertools import count
from nfvbench.log import LOG
from nfvbench.specs import ChainType
from nfvbench.traffic_server import TRexTrafficServer
from nfvbench.utils import cast_integer
from nfvbench.utils import timeout
from nfvbench.utils import TimeoutError
from traffic_base import AbstractTrafficGenerator
from traffic_base import TrafficGeneratorException
import traffic_utils as utils

# pylint: disable=import-error
from trex_stl_lib.api import CTRexVmInsFixHwCs
from trex_stl_lib.api import Dot1Q
from trex_stl_lib.api import Ether
from trex_stl_lib.api import IP
from trex_stl_lib.api import STLClient
from trex_stl_lib.api import STLError
from trex_stl_lib.api import STLFlowLatencyStats
from trex_stl_lib.api import STLFlowStats
from trex_stl_lib.api import STLPktBuilder
from trex_stl_lib.api import STLScVmRaw
from trex_stl_lib.api import STLStream
from trex_stl_lib.api import STLTXCont
from trex_stl_lib.api import STLVmFixChecksumHw
from trex_stl_lib.api import STLVmFlowVar
from trex_stl_lib.api import STLVmFlowVarRepetableRandom
from trex_stl_lib.api import STLVmWrFlowVar
from trex_stl_lib.api import UDP
from trex_stl_lib.services.trex_stl_service_arp import STLServiceARP


# pylint: enable=import-error


class TRex(AbstractTrafficGenerator):
    LATENCY_PPS = 1000

    def __init__(self, runner):
        AbstractTrafficGenerator.__init__(self, runner)
        self.client = None
        self.id = count()
        self.latencies = defaultdict(list)
        self.stream_ids = defaultdict(list)
        self.port_handle = []
        self.streamblock = defaultdict(list)
        self.rates = []
        self.arps = {}
        self.capture_id = None
        self.packet_list = []

    def get_version(self):
        return self.client.get_server_version()

    def extract_stats(self, in_stats):
        """Extract stats from dict returned by Trex API.

        :param in_stats: dict as returned by TRex api
        """
        utils.nan_replace(in_stats)
        LOG.debug(in_stats)

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

            lat = self.__combine_latencies(in_stats, ph)
            result[ph]['rx']['max_delay_usec'] = cast_integer(
                lat['total_max']) if 'total_max' in lat else float('nan')
            result[ph]['rx']['min_delay_usec'] = cast_integer(
                lat['total_min']) if 'total_min' in lat else float('nan')
            result[ph]['rx']['avg_delay_usec'] = cast_integer(
                lat['average']) if 'average' in lat else float('nan')
        total_tx_pkts = result[0]['tx']['total_pkts'] + result[1]['tx']['total_pkts']
        result["total_tx_rate"] = cast_integer(total_tx_pkts / self.config.duration_sec)
        return result

    def __combine_latencies(self, in_stats, port_handle):
        """Traverses TRex result dictionary and combines chosen latency stats."""
        if not self.latencies[port_handle]:
            return {}

        result = defaultdict(float)
        result['total_min'] = float("inf")
        for lat_id in self.latencies[port_handle]:
            lat = in_stats['latency'][lat_id]
            result['dropped_pkts'] += lat['err_cntrs']['dropped']
            result['total_max'] = max(lat['latency']['total_max'], result['total_max'])
            result['total_min'] = min(lat['latency']['total_min'], result['total_min'])
            result['average'] += lat['latency']['average']

        result['average'] /= len(self.latencies[port_handle])

        return result

    def create_pkt(self, stream_cfg, l2frame_size):

        pkt_base = Ether(src=stream_cfg['mac_src'], dst=stream_cfg['mac_dst'])
        if stream_cfg['vlan_tag'] is not None:
            # 50 = 14 (Ethernet II) + 4 (Vlan tag) + 4 (CRC Checksum) + 20 (IPv4) + 8 (UDP)
            pkt_base /= Dot1Q(vlan=stream_cfg['vlan_tag'])
            l2payload_size = int(l2frame_size) - 50
        else:
            # 46 = 14 (Ethernet II) + 4 (CRC Checksum) + 20 (IPv4) + 8 (UDP)
            l2payload_size = int(l2frame_size) - 46
        payload = 'x' * l2payload_size
        udp_args = {}
        if stream_cfg['udp_src_port']:
            udp_args['sport'] = int(stream_cfg['udp_src_port'])
        if stream_cfg['udp_dst_port']:
            udp_args['dport'] = int(stream_cfg['udp_dst_port'])
        pkt_base /= IP() / UDP(**udp_args)

        if stream_cfg['ip_addrs_step'] == 'random':
            src_fv = STLVmFlowVarRepetableRandom(
                name="ip_src",
                min_value=stream_cfg['ip_src_addr'],
                max_value=stream_cfg['ip_src_addr_max'],
                size=4,
                seed=random.randint(0, 32767),
                limit=stream_cfg['ip_src_count'])
            dst_fv = STLVmFlowVarRepetableRandom(
                name="ip_dst",
                min_value=stream_cfg['ip_dst_addr'],
                max_value=stream_cfg['ip_dst_addr_max'],
                size=4,
                seed=random.randint(0, 32767),
                limit=stream_cfg['ip_dst_count'])
        else:
            src_fv = STLVmFlowVar(
                name="ip_src",
                min_value=stream_cfg['ip_src_addr'],
                max_value=stream_cfg['ip_src_addr'],
                size=4,
                op="inc",
                step=stream_cfg['ip_addrs_step'])
            dst_fv = STLVmFlowVar(
                name="ip_dst",
                min_value=stream_cfg['ip_dst_addr'],
                max_value=stream_cfg['ip_dst_addr_max'],
                size=4,
                op="inc",
                step=stream_cfg['ip_addrs_step'])

        vm_param = [
            src_fv,
            STLVmWrFlowVar(fv_name="ip_src", pkt_offset="IP.src"),
            dst_fv,
            STLVmWrFlowVar(fv_name="ip_dst", pkt_offset="IP.dst"),
            STLVmFixChecksumHw(l3_offset="IP",
                               l4_offset="UDP",
                               l4_type=CTRexVmInsFixHwCs.L4_TYPE_UDP)
        ]

        return STLPktBuilder(pkt=pkt_base / payload, vm=STLScVmRaw(vm_param))

    def generate_streams(self, port_handle, stream_cfg, l2frame, isg=0.0, latency=True):
        idx_lat = None
        streams = []
        if l2frame == 'IMIX':
            min_size = 64 if stream_cfg['vlan_tag'] is None else 68
            self.adjust_imix_min_size(min_size)
            for t, (ratio, l2_frame_size) in enumerate(zip(self.imix_ratios, self.imix_l2_sizes)):
                pkt = self.create_pkt(stream_cfg, l2_frame_size)
                streams.append(STLStream(packet=pkt,
                                         isg=0.1 * t,
                                         flow_stats=STLFlowStats(
                                             pg_id=self.stream_ids[port_handle]),
                                         mode=STLTXCont(pps=ratio)))

            if latency:
                idx_lat = self.id.next()
                pkt = self.create_pkt(stream_cfg, self.imix_avg_l2_size)
                sl = STLStream(packet=pkt,
                               isg=isg,
                               flow_stats=STLFlowLatencyStats(pg_id=idx_lat),
                               mode=STLTXCont(pps=self.LATENCY_PPS))
                streams.append(sl)
        else:
            pkt = self.create_pkt(stream_cfg, l2frame)
            streams.append(STLStream(packet=pkt,
                                     flow_stats=STLFlowStats(pg_id=self.stream_ids[port_handle]),
                                     mode=STLTXCont()))

            if latency:
                idx_lat = self.id.next()
                streams.append(STLStream(packet=pkt,
                                         flow_stats=STLFlowLatencyStats(pg_id=idx_lat),
                                         mode=STLTXCont(pps=self.LATENCY_PPS)))

        if latency:
            self.latencies[port_handle].append(idx_lat)

        return streams

    def init(self):
        pass

    @timeout(5)
    def __connect(self, client):
        client.connect()

    def __connect_after_start(self):
        # after start, Trex may take a bit of time to initialize
        # so we need to retry a few times
        for it in xrange(self.config.generic_retry_count):
            try:
                time.sleep(1)
                self.client.connect()
                break
            except Exception as ex:
                if it == (self.config.generic_retry_count - 1):
                    raise ex
                LOG.info("Retrying connection to TRex (%s)...", ex.message)

    def connect(self):
        LOG.info("Connecting to TRex...")
        server_ip = self.config.generator_config.ip

        # Connect to TRex server
        self.client = STLClient(server=server_ip)
        try:
            self.__connect(self.client)
        except (TimeoutError, STLError) as e:
            if server_ip == '127.0.0.1':
                try:
                    self.__start_server()
                    self.__connect_after_start()
                except (TimeoutError, STLError) as e:
                    LOG.error('Cannot connect to TRex')
                    LOG.error(traceback.format_exc())
                    logpath = '/tmp/trex.log'
                    if os.path.isfile(logpath):
                        # Wait for TRex to finish writing error message
                        last_size = 0
                        for _ in xrange(self.config.generic_retry_count):
                            size = os.path.getsize(logpath)
                            if size == last_size:
                                # probably not writing anymore
                                break
                            last_size = size
                            time.sleep(1)
                        with open(logpath, 'r') as f:
                            message = f.read()
                    else:
                        message = e.message
                    raise TrafficGeneratorException(message)
            else:
                raise TrafficGeneratorException(e.message)

        ports = list(self.config.generator_config.ports)
        self.port_handle = ports
        # Prepare the ports
        self.client.reset(ports)

    def set_mode(self):
        if self.config.service_chain == ChainType.EXT and not self.config.no_arp:
            self.__set_l3_mode()
        else:
            self.__set_l2_mode()

    def __set_l3_mode(self):
        self.client.set_service_mode(ports=self.port_handle, enabled=True)
        for port, device in zip(self.port_handle, self.config.generator_config.devices):
            try:
                self.client.set_l3_mode(port=port,
                                        src_ipv4=device.tg_gateway_ip,
                                        dst_ipv4=device.dst.gateway_ip,
                                        vlan=device.vlan_tag if device.vlan_tagging else None)
            except STLError:
                # TRex tries to resolve ARP already, doesn't have to be successful yet
                continue
        self.client.set_service_mode(ports=self.port_handle, enabled=False)

    def __set_l2_mode(self):
        self.client.set_service_mode(ports=self.port_handle, enabled=True)
        for port, device in zip(self.port_handle, self.config.generator_config.devices):
            for cfg in device.get_stream_configs(self.config.generator_config.service_chain):
                self.client.set_l2_mode(port=port, dst_mac=cfg['mac_dst'])
        self.client.set_service_mode(ports=self.port_handle, enabled=False)

    def __start_server(self):
        server = TRexTrafficServer()
        server.run_server(self.config.generator_config, self.config.vlan_tagging)

    def resolve_arp(self):
        self.client.set_service_mode(ports=self.port_handle)
        LOG.info('Polling ARP until successful')
        resolved = 0
        attempt = 0
        for port, device in zip(self.port_handle, self.config.generator_config.devices):
            ctx = self.client.create_service_ctx(port=port)

            arps = [
                STLServiceARP(ctx,
                              src_ip=cfg['ip_src_tg_gw'],
                              dst_ip=cfg['mac_discovery_gw'],
                              vlan=device.vlan_tag if device.vlan_tagging else None)
                for cfg in device.get_stream_configs(self.config.generator_config.service_chain)
            ]

            for _ in xrange(self.config.generic_retry_count):
                attempt += 1
                try:
                    ctx.run(arps)
                except STLError:
                    LOG.error(traceback.format_exc())
                    continue

                self.arps[port] = [arp.get_record().dst_mac for arp in arps
                                   if arp.get_record().dst_mac is not None]

                if len(self.arps[port]) == self.config.service_chain_count:
                    resolved += 1
                    LOG.info('ARP resolved successfully for port %s', port)
                    break
                else:
                    failed = [arp.get_record().dst_ip for arp in arps
                              if arp.get_record().dst_mac is None]
                    LOG.info('Retrying ARP for: %s (%d / %d)',
                             failed, attempt, self.config.generic_retry_count)
                    time.sleep(self.config.generic_poll_sec)

        self.client.set_service_mode(ports=self.port_handle, enabled=False)
        return resolved == len(self.port_handle)

    def config_interface(self):
        pass

    def __is_rate_enough(self, l2frame_size, rates, bidirectional, latency):
        """Check if rate provided by user is above requirements. Applies only if latency is True."""
        intf_speed = self.config.generator_config.intf_speed
        if latency:
            if bidirectional:
                mult = 2
                total_rate = 0
                for rate in rates:
                    r = utils.convert_rates(l2frame_size, rate, intf_speed)
                    total_rate += int(r['rate_pps'])
            else:
                mult = 1
                total_rate = utils.convert_rates(l2frame_size, rates[0], intf_speed)
            # rate must be enough for latency stream and at least 1 pps for base stream per chain
            required_rate = (self.LATENCY_PPS + 1) * self.config.service_chain_count * mult
            result = utils.convert_rates(l2frame_size,
                                         {'rate_pps': required_rate},
                                         intf_speed * mult)
            result['result'] = total_rate >= required_rate
            return result

        return {'result': True}

    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True):
        r = self.__is_rate_enough(l2frame_size, rates, bidirectional, latency)
        if not r['result']:
            raise TrafficGeneratorException(
                'Required rate in total is at least one of: \n{pps}pps \n{bps}bps \n{load}%.'
                .format(pps=r['rate_pps'],
                        bps=r['rate_bps'],
                        load=r['rate_percent']))

        stream_cfgs = [d.get_stream_configs(self.config.generator_config.service_chain)
                       for d in self.config.generator_config.devices]
        self.rates = [utils.to_rate_str(rate) for rate in rates]

        for ph in self.port_handle:
            # generate one pg_id for each direction
            self.stream_ids[ph] = self.id.next()

        for i, (fwd_stream_cfg, rev_stream_cfg) in enumerate(zip(*stream_cfgs)):
            if self.config.service_chain == ChainType.EXT and not self.config.no_arp:
                fwd_stream_cfg['mac_dst'] = self.arps[self.port_handle[0]][i]
                rev_stream_cfg['mac_dst'] = self.arps[self.port_handle[1]][i]

            self.streamblock[0].extend(self.generate_streams(self.port_handle[0],
                                                             fwd_stream_cfg,
                                                             l2frame_size,
                                                             latency=latency))
            if len(self.rates) > 1:
                self.streamblock[1].extend(self.generate_streams(self.port_handle[1],
                                                                 rev_stream_cfg,
                                                                 l2frame_size,
                                                                 isg=10.0,
                                                                 latency=bidirectional and latency))

        for ph in self.port_handle:
            self.client.add_streams(self.streamblock[ph], ports=ph)
            LOG.info('Created traffic stream for port %s.', ph)

    def clear_streamblock(self):
        self.streamblock = defaultdict(list)
        self.latencies = defaultdict(list)
        self.stream_ids = defaultdict(list)
        self.rates = []
        self.client.reset(self.port_handle)
        LOG.info('Cleared all existing streams.')

    def get_stats(self):
        stats = self.client.get_stats()
        return self.extract_stats(stats)

    def get_macs(self):
        return [self.client.get_port_attr(port=port)['src_mac'] for port in self.port_handle]

    def clear_stats(self):
        if self.port_handle:
            self.client.clear_stats()

    def start_traffic(self):
        for port, rate in zip(self.port_handle, self.rates):
            self.client.start(ports=port, mult=rate, duration=self.config.duration_sec, force=True)

    def stop_traffic(self):
        self.client.stop(ports=self.port_handle)

    def start_capture(self):
        if self.capture_id:
            self.stop_capture()
        self.client.set_service_mode(ports=self.port_handle)
        self.capture_id = self.client.start_capture(rx_ports=self.port_handle)

    def fetch_capture_packets(self):
        if self.capture_id:
            self.packet_list = []
            self.client.fetch_capture_packets(capture_id=self.capture_id['id'],
                                              output=self.packet_list)

    def stop_capture(self):
        if self.capture_id:
            self.client.stop_capture(capture_id=self.capture_id['id'])
            self.capture_id = None
            self.client.set_service_mode(ports=self.port_handle, enabled=False)

    def cleanup(self):
        if self.client:
            try:
                self.client.reset(self.port_handle)
                self.client.disconnect()
            except STLError:
                # TRex does not like a reset while in disconnected state
                pass
