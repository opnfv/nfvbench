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

from traffic_base import AbstractTrafficGenerator
import traffic_utils as utils



class DummyTG(AbstractTrafficGenerator):
    """Experimental dummy traffic generator.

    This traffic generator will pretend to generate traffic and return fake data.
    Useful for unit testing without actually generating any traffic.
    """

    def __init__(self, runner):
        AbstractTrafficGenerator.__init__(self, runner)
        self.port_handle = []
        self.rates = []

    def get_version(self):
        return "0.1"

    def init(self):
        pass

    def connect(self):
        ports = list(self.config.generator_config.ports)
        self.port_handle = ports

    def is_arp_successful(self):
        return True

    def config_interface(self):
        pass

    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True):
        pass

    def modify_rate(self, rate, reverse):
        port_index = int(reverse)
        port = self.port_handle[port_index]
        self.rates[port_index] = utils.to_rate_str(rate)
        LOG.info('Modified traffic stream for %s, new rate=%s.' % (port, utils.to_rate_str(rate)))

    def clear_streamblock(self):
        pass

    def get_stats(self):
        result = {}
        for ph in self.port_handle:
            result[ph] = {
                'tx': {
                    'total_pkts': 1000,
                    'total_pkt_bytes': 100000,
                    'pkt_rate': 100,
                    'pkt_bit_rate': 1000000
                },
                'rx': {
                    'total_pkts': 1000,
                    'total_pkt_bytes': 100000,
                    'pkt_rate': 100,
                    'pkt_bit_rate': 1000000,
                    'dropped_pkts': 0
                }
            }
            result[ph]['rx']['max_delay_usec'] = 10.0
            result[ph]['rx']['min_delay_usec'] = 1.0
            result[ph]['rx']['avg_delay_usec'] = 2.0
        return result

    def clear_stats(self):
        pass

    def start_traffic(self):
        pass

    def stop_traffic(self):
        pass

    def cleanup(self):
        pass
