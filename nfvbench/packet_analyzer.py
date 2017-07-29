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

from collections import OrderedDict
from log import LOG


class PacketAnalyzer(object):
    """Analyze packet drop counter in a chain"""

    def __init__(self):
        self.last_packet_count = 0
        self.chain = []

    def record(self, interface, traffic_type):
        """Records the counter of the next interface with the corresponding traffic type"""
        if interface.is_no_op():
            return
        packet_count = interface.get_packet_count(traffic_type)
        packet_drop_count = self.last_packet_count - packet_count
        path_data = OrderedDict()
        path_data['interface'] = interface.name
        path_data['device'] = interface.device
        path_data['packet_count'] = packet_count

        if self.chain:
            path_data['packet_drop_count'] = packet_drop_count

        self.chain.append(path_data)
        self.last_packet_count = packet_count

    def get_analysis(self):
        """Gets the analysis of packet drops"""
        transmitted_packets = self.chain[0]['packet_count']

        for (index, path_data) in enumerate(self.chain):
            LOG.info('[Packet Analyze] Interface: %s' % (path_data['interface']))
            LOG.info('[Packet Analyze]            > Count: %d' % (path_data['packet_count']))

            if index:
                if transmitted_packets:
                    self.chain[index]['packet_drop_percentage'] = \
                        100.0 * path_data['packet_drop_count'] / transmitted_packets
                else:
                    self.chain[index]['packet_drop_percentage'] = float('nan')
                LOG.info('[Packet Analyze]            > Packet Drops: %d' %
                         (path_data['packet_drop_count']))
                LOG.info('[Packet Analyze]            > Percentage: %s' %
                         (path_data['packet_drop_percentage']))

        return self.chain
