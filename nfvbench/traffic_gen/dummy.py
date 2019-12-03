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

from nfvbench.log import LOG
from .traffic_base import AbstractTrafficGenerator
from . import traffic_utils as utils


class DummyTG(AbstractTrafficGenerator):
    """Experimental dummy traffic generator.

    This traffic generator will pretend to generate traffic and return fake data.
    Useful for unit testing without actually generating any traffic.
    """

    def __init__(self, traffic_client):
        AbstractTrafficGenerator.__init__(self, traffic_client)
        self.port_handle = []
        self.rates = []
        self.l2_frame_size = 0
        self.duration_sec = traffic_client.config.duration_sec
        self.intf_speed = traffic_client.generator_config.intf_speed
        self.set_response_curve()
        self.packet_list = None

    def get_version(self):
        return "0.1"

    def get_tx_pps_dropped_pps(self, tx_rate):
        """Get actual tx packets based on requested tx rate.

        :param tx_rate: requested TX rate with unit ('40%', '1Mbps', '1000pps')

        :return: the actual TX pps and the dropped pps corresponding to the requested TX rate
        """
        dr, tx = self.__get_dr_actual_tx(tx_rate)
        actual_tx_bps = utils.load_to_bps(tx, self.intf_speed)
        avg_packet_size = utils.get_average_packet_size(self.l2_frame_size)
        tx_packets = utils.bps_to_pps(actual_tx_bps, avg_packet_size)

        dropped = tx_packets * dr / 100
        # print '===get_tx_pkts_dropped_pkts req tex=', tx_rate, 'dr=', dr,
        # 'actual tx rate=', tx, 'actual tx pkts=', tx_packets, 'dropped=', dropped
        return int(tx_packets), int(dropped)

    def set_response_curve(self, lr_dr=0, ndr=100, max_actual_tx=100, max_11_tx=100):
        """Set traffic gen response characteristics.

        Specifies the drop rate curve and the actual TX curve
        :param float lr_dr: The actual drop rate at TX line rate (in %, 0..100)
        :param float ndr: The true NDR  (0 packet drop) in % (0..100) of line rate"
        :param float max_actual_tx: highest actual TX when requested TX is 100%
        :param float max_11_tx: highest requested TX that results in same actual TX
        """
        self.target_ndr = ndr
        if ndr < 100:
            self.dr_slope = float(lr_dr) / (100 - ndr)
        else:
            self.dr_slope = 0
        self.max_11_tx = max_11_tx
        self.max_actual_tx = max_actual_tx
        if max_11_tx < 100:
            self.tx_slope = float(max_actual_tx - max_11_tx) / (100 - max_11_tx)
        else:
            self.tx_slope = 0

    def __get_dr_actual_tx(self, requested_tx_rate):
        """Get drop rate at given requested tx rate.

        :param float requested_tx_rate: requested tx rate in % (0..100)
        :return: the drop rate and actual tx rate at that requested_tx_rate in % (0..100)
        """
        if requested_tx_rate <= self.max_11_tx:
            actual_tx = requested_tx_rate
        else:
            actual_tx = self.max_11_tx + (requested_tx_rate - self.max_11_tx) * self.tx_slope
        if actual_tx <= self.target_ndr:
            dr = 0.0
        else:
            dr = (actual_tx - self.target_ndr) * self.dr_slope
        return dr, actual_tx

    def connect(self):
        ports = list(self.traffic_client.generator_config.ports)
        self.port_handle = ports

    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True, e2e=False):
        self.rates = [utils.to_rate_str(rate) for rate in rates]
        self.l2_frame_size = l2frame_size

    def clear_streamblock(self):
        pass

    def get_stats(self):
        """Get stats from current run.

        The binary search mainly looks at 2 results to make the decision:
            actual tx packets
            actual rx dropped packets
        From the Requested TX rate - we get the Actual TX rate and the RX drop rate
        From the Run duration and actual TX rate - we get the actual total tx packets
        From the Actual tx packets and RX drop rate - we get the RX dropped packets
        """
        result = {}
        total_tx_pps = 0

        # use dummy values for all other result field as the goal is to
        # test the ndr/pdr convergence code
        for idx, ph in enumerate(self.port_handle):
            requested_tx_rate = utils.get_load_from_rate(self.rates[idx])
            tx_pps, dropped_pps = self.get_tx_pps_dropped_pps(requested_tx_rate)

            # total packets sent per direction - used by binary search
            total_pkts = tx_pps * self.duration_sec
            dropped_pkts = dropped_pps * self.duration_sec
            _, tx_pkt_rate = self.__get_dr_actual_tx(requested_tx_rate)
            result[ph] = {
                'tx': {
                    'total_pkts': total_pkts,
                    'total_pkt_bytes': 100000,
                    'pkt_rate': tx_pkt_rate,
                    'pkt_bit_rate': 1000000
                },
                'rx': {
                    # total packets received
                    'total_pkts': total_pkts - dropped_pkts,
                    'total_pkt_bytes': 100000,
                    'pkt_rate': 100,
                    'pkt_bit_rate': 1000000,
                    'dropped_pkts': dropped_pkts
                }
            }
            result[ph]['rx']['max_delay_usec'] = 10.0
            result[ph]['rx']['min_delay_usec'] = 1.0
            result[ph]['rx']['avg_delay_usec'] = 2.0
            total_tx_pps += tx_pps
        # actual total tx rate in pps
        result['total_tx_rate'] = total_tx_pps
        return result

    def get_stream_stats(self, tg_stats, if_stats, latencies, chain_idx):
        for port in range(2):
            if_stats[port].tx = 1000
            if_stats[port].rx = 1000
            latencies[port].min_usec = 10
            latencies[port].max_usec = 100
            latencies[port].avg_usec = 50

    def get_macs(self):
        return ['00:00:00:00:00:01', '00:00:00:00:00:02']

    def get_port_speed_gbps(self):
        """Return the local port speeds.

        return: a list of speed in Gbps indexed by the port#
        """
        return [10, 10]

    def clear_stats(self):
        pass

    def start_traffic(self):
        pass

    def fetch_capture_packets(self):
        def _get_packet_capture(mac):
            # convert text to binary
            src_mac = bytearray.fromhex(mac.replace(':', '')).decode()
            return {'binary': bytes('SSSSSS' + src_mac, 'ascii')}

        # for packet capture, generate 2*scc random packets
        # normally we should generate packets coming from the right dest macs
        self.packet_list = []
        for dest_macs in self.traffic_client.generator_config.get_dest_macs():
            for mac in dest_macs:
                self.packet_list.append(_get_packet_capture(mac))

    def stop_traffic(self):
        pass

    def start_capture(self):
        pass

    def stop_capture(self):
        pass

    def cleanup(self):
        pass

    def set_mode(self):
        pass

    def set_service_mode(self, enabled=True):
        pass

    def resolve_arp(self):
        """Resolve ARP sucessfully."""
        def get_macs(port, scc):
            return ['00:00:00:00:%02x:%02x' % (port, chain) for chain in range(scc)]
        scc = self.traffic_client.generator_config.service_chain_count
        res = [get_macs(port, scc) for port in range(2)]
        LOG.info('Dummy TG ARP: %s', str(res))
        return res
