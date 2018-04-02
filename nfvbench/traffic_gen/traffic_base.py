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

from nfvbench.log import LOG
import traffic_utils


class TrafficGeneratorException(Exception):
    pass


class AbstractTrafficGenerator(object):
    def __init__(self, config):
        self.config = config
        self.imix_l2_sizes = [64, 594, 1518]
        self.imix_ratios = [7, 4, 1]
        self.imix_avg_l2_size = 0
        self.adjust_imix_min_size(64)

    @abc.abstractmethod
    def get_version(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def init(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def connect(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def config_interface(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def create_traffic(self, l2frame_size, rates, bidirectional, latency=True):
        # Must be implemented by sub classes
        return None

    def modify_rate(self, rate, reverse):
        port_index = int(reverse)
        port = self.port_handle[port_index]
        self.rates[port_index] = traffic_utils.to_rate_str(rate)
        LOG.info('Modified traffic stream for %s, new rate=%s.', port,
                 traffic_utils.to_rate_str(rate))

    def modify_traffic(self):
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def get_stats(self):
        # Must be implemented by sub classes
        return None

    def clear_traffic(self):
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
        # Must be implemented by sub classes
        return None

    def adjust_imix_min_size(self, min_size):
        # assume the min size is always the first entry
        self.imix_l2_sizes[0] = min_size
        self.imix_avg_l2_size = sum(
            [1.0 * imix[0] * imix[1] for imix in zip(self.imix_l2_sizes, self.imix_ratios)]) / sum(
                self.imix_ratios)
        traffic_utils.imix_avg_l2_size = self.imix_avg_l2_size
