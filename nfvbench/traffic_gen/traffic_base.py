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

class TrafficGeneratorException(Exception):
    pass


class AbstractTrafficGenerator(object):

    # src_mac (6) + dst_mac (6) + mac_type (2) + frame_check (4) = 18
    l2_header_size = 18

    imix_l2_sizes = [64, 594, 1518]
    imix_l3_sizes = [size - l2_header_size for size in imix_l2_sizes]
    imix_ratios = [7, 4, 1]
    imix_avg_l2_size = sum(map(
        lambda imix: 1.0 * imix[0] * imix[1],
        zip(imix_l2_sizes, imix_ratios))) / sum(imix_ratios)

    def __init__(self, config):
        self.config = config

    @abc.abstractmethod
    def get_version():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def init():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def connect():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def config_interface():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def create_traffic():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def modify_traffic():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def get_stats():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def clear_traffic():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def start_traffic():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def stop_traffic():
        # Must be implemented by sub classes
        return None

    @abc.abstractmethod
    def cleanup():
        # Must be implemented by sub classes
        return None
