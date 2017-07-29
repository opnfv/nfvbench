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


class Interface(object):

    def __init__(self, name, device, tx_packets, rx_packets):
        self.name = name
        self.device = device
        self.packets = {
            'tx': tx_packets,
            'rx': rx_packets
        }

    def set_packets(self, tx, rx):
        self.packets = {
            'tx': tx,
            'rx': rx
        }

    def set_packets_diff(self, tx, rx):
        self.packets = {
            'tx': tx - self.packets['tx'],
            'rx': rx - self.packets['rx'],
        }

    def is_no_op(self):
        return self.name is None

    def get_packet_count(self, traffic_type):
        return self.packets.get(traffic_type, 0)

    @staticmethod
    def no_op():
        return Interface(None, None, 0, 0)


class Network(object):

    def __init__(self, interfaces=None, reverse=False):
        if interfaces is None:
            interfaces = []
        self.interfaces = interfaces
        self.reverse = reverse

    def add_interface(self, interface):
        self.interfaces.append(interface)

    def get_interfaces(self):
        return self.interfaces[::-1] if self.reverse else self.interfaces
