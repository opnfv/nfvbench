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

import abc
import sys

from nfvbench.log import LOG
from . import traffic_utils
from hdrh.histogram import HdrHistogram
from functools import reduce


class Latency(object):
    """A class to hold latency data."""

    def __init__(self, latency_list=None):
        """Create a latency instance.

        latency_list: aggregate all latency values from list if not None
        """
        self.min_usec = sys.maxsize
        self.max_usec = 0
        self.avg_usec = 0
        self.hdrh = None
        if latency_list:
            hdrh_list = []
            for lat in latency_list:
                if lat.available():
                    self.min_usec = min(self.min_usec, lat.min_usec)
                    self.max_usec = max(self.max_usec, lat.max_usec)
                    self.avg_usec += lat.avg_usec
                if lat.hdrh_available():
                    hdrh_list.append(HdrHistogram.decode(lat.hdrh))

            # aggregate histograms if any
            if hdrh_list:
                def add_hdrh(x, y):
                    x.add(y)
                    return x
                decoded_hdrh = reduce(add_hdrh, hdrh_list)
                self.hdrh = HdrHistogram.encode(decoded_hdrh).decode('utf-8')

            # round to nearest usec
            self.avg_usec = int(round(float(self.avg_usec) / len(latency_list)))

    def available(self):
        """Return True if latency information is available."""
        return self.min_usec != sys.maxsize

    def hdrh_available(self):
        """Return True if latency histogram information is available."""
        return self.hdrh is not None

class TrafficGeneratorException(Exception):
    """Exception for traffic generator."""

class AbstractTrafficGenerator(object):

    def __init__(self, traffic_client):
        self.traffic_client = traffic_client
        self.generator_config = traffic_client.generator_config
        self.config = traffic_client.config

    @abc.abstractmethod
    def get_version(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def connect(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True, e2e=False):
        # Must be implemented by sub classes
        return None

    def modify_rate(self, rate, reverse):
        """Change the rate per port.

        rate: new rate in % (0 to 100)
        reverse: 0 for port 0, 1 for port 1
        """
        port_index = int(reverse)
        port = self.port_handle[port_index]
        self.rates[port_index] = traffic_utils.to_rate_str(rate)
        LOG.info('Modified traffic stream for port %s, new rate=%s.', port, self.rates[port_index])

    @abc.abstractmethod
    def get_stats(self, ifstats):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def start_traffic(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def stop_traffic(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def cleanup(self):
        """Cleanup the traffic generator."""
        return None

    def clear_streamblock(self):
        """Clear all streams from the traffic generator."""

    @abc.abstractmethod
    def resolve_arp(self):
        """Resolve all configured remote IP addresses.

        return: None if ARP failed to resolve for all IP addresses
                else a dict of list of dest macs indexed by port#
                the dest macs in the list are indexed by the chain id
        """

    @abc.abstractmethod
    def get_macs(self):
        """Return the local port MAC addresses.

        return: a list of MAC addresses indexed by the port#
        """

    @abc.abstractmethod
    def get_port_speed_gbps(self):
        """Return the local port speeds.

        return: a list of speed in Gbps indexed by the port#
        """

    def get_theoretical_rates(self, avg_packet_size):

        result = {}

        # actual interface speed? (may be a virtual override)
        intf_speed = self.config.intf_speed_used

        if hasattr(self.config, 'user_info') and self.config.user_info is not None:
            if "extra_encapsulation_bytes" in self.config.user_info:
                frame_size_full_encapsulation = avg_packet_size + self.config.user_info[
                    "extra_encapsulation_bytes"]
                result['theoretical_tx_rate_pps'] = traffic_utils.bps_to_pps(
                    intf_speed, frame_size_full_encapsulation) * 2
                result['theoretical_tx_rate_bps'] = traffic_utils.pps_to_bps(
                    result['theoretical_tx_rate_pps'], avg_packet_size)
        else:
            result['theoretical_tx_rate_pps'] = traffic_utils.bps_to_pps(intf_speed,
                                                                         avg_packet_size) * 2
            result['theoretical_tx_rate_bps'] = traffic_utils.pps_to_bps(
                result['theoretical_tx_rate_pps'], avg_packet_size)
        return result
