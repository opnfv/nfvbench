# Copyright 2018 Cisco Systems, Inc.  All rights reserved.
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
"""Manage all classes related to counting packet stats.

InterfaceStats counts RX/TX packet counters for one interface.
PacketPathStats manages all InterfaceStats instances for a given chain.
PacketPathStatsManager manages all packet path stats for all chains.
"""

import copy

from .traffic_gen.traffic_base import Latency

class InterfaceStats(object):
    """A class to hold the RX and TX counters for a virtual or physical interface.

    An interface stats instance can represent a real interface (e.g. traffic gen port or
    vhost interface) or can represent an aggegation of multiple interfaces when packets
    are faned out (e.g. one vlan subinterface can fan out to multiple vhost interfaces
    in the case of multi-chaining and when the network is shared across chains).
    """

    TX = 0
    RX = 1

    def __init__(self, name, device, shared=False):
        """Create a new interface instance.

        name: interface name specific to each chain (e.g. "trex port 0 chain 0")
        device: on which device this interface resides (e.g. "trex server")
        fetch_tx_rx: a fetch method that takes name, chain_index and returns a (tx, rx) tuple
        shared: if true this interface stats is shared across all chains
        """
        self.name = name
        self.device = device
        self.shared = shared
        # RX and TX counters for this interface
        # A None value can be set to mean that the data is not available
        self.tx = 0
        self.rx = 0
        # This is a special field to hold an optional total rx count that is only
        # used for column aggregation to compute a total intertface stats
        # Set to non zero to be picked by the add interface stats method for rx total
        self.rx_total = None

    def get_packet_count(self, direction):
        """Get packet count for given direction.

        direction: InterfaceStats.TX or InterfaceStats.RX
        """
        return self.tx if direction == InterfaceStats.TX else self.rx

    @staticmethod
    def get_reverse_direction(direction):
        """Get the reverse direction of a given direction.

        direction: InterfaceStats.TX or InterfaceStats.RX
        return: RX if TX given, or TX is RX given
        """
        return 1 - direction

    @staticmethod
    def get_direction_name(direction):
        """Get the rdisplay name of a given direction.

        direction: InterfaceStats.TX or InterfaceStats.RX
        return: "TX" or "RX"
        """
        if direction == InterfaceStats.TX:
            return 'TX'
        return 'RX'

    def add_if_stats(self, if_stats):
        """Add another ifstats to this instance."""
        def added_counter(old_value, new_value_to_add):
            if new_value_to_add:
                if old_value is None:
                    return new_value_to_add
                return old_value + new_value_to_add
            return old_value

        self.tx = added_counter(self.tx, if_stats.tx)
        self.rx = added_counter(self.rx, if_stats.rx)
        # Add special rx total value if set
        self.rx = added_counter(self.rx, if_stats.rx_total)

    def update_stats(self, tx, rx, diff):
        """Update stats for this interface.

        tx: new TX packet count
        rx: new RX packet count
        diff: if True, perform a diff of new value with previous baselined value,
              otherwise store the new value
        """
        if diff:
            self.tx = tx - self.tx
            self.rx = rx - self.rx
        else:
            self.tx = tx
            self.rx = rx

    def get_display_name(self, dir, name=None, aggregate=False):
        """Get the name to use to display stats for this interface stats.

        dir: direction InterfaceStats.TX or InterfaceStats.RX
        name: override self.name
        aggregate: true if this is for an aggregate of multiple chains
        """
        if name is None:
            name = self.name
        return self.device + '.' + InterfaceStats.get_direction_name(dir) + '.' + name


class PacketPathStats(object):
    """Manage the packet path stats for 1 chain in both directions.

    A packet path stats instance manages an ordered list of InterfaceStats objects
    that can be traversed in the forward and reverse direction to display packet
    counters in each direction.
    The requirement is that RX and TX counters must always alternate as we travel
    along one direction. For example with 4 interfaces per chain:
    [ifstat0, ifstat1, ifstat2, ifstat3]
    Packet counters in the forward direction are:
    [ifstat0.TX, ifstat1.RX, ifstat2.TX, ifstat3.RX]
    Packet counters in the reverse direction are:
    [ifstat3.TX, ifstat2.RX, ifstat1.TX, ifstat0.RX]

    A packet path stats also carries the latency data for each direction of the
    chain.
    """

    def __init__(self, if_stats, aggregate=False):
        """Create a packet path stats intance with the list of associated if stats.

        if_stats: a list of interface stats that compose this packet path stats
        aggregate: True if this is an aggregate packet path stats

        Aggregate packet path stats are the only one that should show counters for shared
        interface stats
        """
        self.if_stats = if_stats
        # latency for packets sent from port 0 and 1
        self.latencies = [Latency(), Latency()]
        self.aggregate = aggregate


    def add_packet_path_stats(self, pps):
        """Add another packet path stat to this instance.

        pps: the other packet path stats to add to this instance

        This is used only for aggregating/collapsing multiple pps into 1
        to form a "total" pps
        """
        for index, ifstats in enumerate(self.if_stats):
            # shared interface stats must not be self added
            if not ifstats.shared:
                ifstats.add_if_stats(pps.if_stats[index])

    @staticmethod
    def get_agg_packet_path_stats(pps_list):
        """Get the aggregated packet path stats from a list of packet path stats.

        Interface counters are added, latency stats are updated.
        """
        agg_pps = None
        for pps in pps_list:
            if agg_pps is None:
                # Get a clone of the first in the list
                agg_pps = PacketPathStats(pps.get_cloned_if_stats(), aggregate=True)
            else:
                agg_pps.add_packet_path_stats(pps)
        # aggregate all latencies
        agg_pps.latencies = [Latency([pps.latencies[port] for pps in pps_list])
                             for port in [0, 1]]
        return agg_pps

    def get_if_stats(self, reverse=False):
        """Get interface stats for given direction.

        reverse: if True, get the list of interface stats in the reverse direction
                 else (default) gets the ist in the forward direction.
        return: the list of interface stats indexed by the chain index
        """
        return self.if_stats[::-1] if reverse else self.if_stats

    def get_cloned_if_stats(self):
        """Get a clone copy of the interface stats list."""
        return [copy.copy(ifstat) for ifstat in self.if_stats]


    def get_header_labels(self, reverse=False, aggregate=False):
        """Get the list of header labels for this packet path stats."""
        labels = []
        dir = InterfaceStats.TX
        for ifstat in self.get_if_stats(reverse):
            # starts at TX then RX then TX again etc...
            labels.append(ifstat.get_display_name(dir, aggregate=aggregate))
            dir = InterfaceStats.get_reverse_direction(dir)
        return labels

    def get_stats(self, reverse=False):
        """Get the list of packet counters and latency data for this packet path stats.

        return: a dict of packet counters and latency stats

        {'packets': [2000054, 1999996, 1999996],
         'min_usec': 10, 'max_usec': 187, 'avg_usec': 45},
        """
        counters = []
        dir = InterfaceStats.TX
        for ifstat in self.get_if_stats(reverse):
            # starts at TX then RX then TX again etc...
            if ifstat.shared and not self.aggregate:
                # shared if stats countesr are only shown in aggregate pps
                counters.append('')
            else:
                counters.append(ifstat.get_packet_count(dir))
            dir = InterfaceStats.get_reverse_direction(dir)

        # latency: use port 0 latency for forward, port 1 latency for reverse
        latency = self.latencies[1] if reverse else self.latencies[0]

        if latency.available():
            results = {'lat_min_usec': latency.min_usec,
                       'lat_max_usec': latency.max_usec,
                       'lat_avg_usec': latency.avg_usec}
            if latency.hdrh:
                results['hdrh'] = latency.hdrh
        else:
            results = {}
        results['packets'] = counters
        return results


class PacketPathStatsManager(object):
    """Manages all the packet path stats for all chains.

    Each run will generate packet path stats for 1 or more chains.
    """

    def __init__(self, pps_list):
        """Create a packet path stats intance with the list of associated if stats.

        pps_list: a list of packet path stats indexed by the chain id.
        All packet path stats must have the same length.
        """
        self.pps_list = pps_list

    def insert_pps_list(self, chain_index, if_stats):
        """Insert a list of interface stats for given chain right after the first in the list.

        chain_index: index of chain where to insert
        if_stats: list of interface stats to insert
        """
        # use slicing to insert the list
        self.pps_list[chain_index].if_stats[1:1] = if_stats

    def _get_if_agg_name(self, reverse):
        """Get the aggegated name for all interface stats across all pps.

        return: a list of aggregated names for each position of the chain for all chains

        The agregated name is the interface stats name if there is only 1 chain.
        Otherwise it is the common prefix for all interface stats names at same position in the
        chain.
        """
        # if there is only one chain, use the if_stats names directly
        return self.pps_list[0].get_header_labels(reverse, aggregate=(len(self.pps_list) > 1))

    def _get_results(self, reverse=False):
        """Get the digested stats for the forward or reverse directions.

        return: a dict with all the labels, total and per chain counters
        """
        chains = {}
        # insert the aggregated row if applicable
        if len(self.pps_list) > 1:
            agg_pps = PacketPathStats.get_agg_packet_path_stats(self.pps_list)
            chains['total'] = agg_pps.get_stats(reverse)

        for index, pps in enumerate(self.pps_list):
            chains[index] = pps.get_stats(reverse)
        return {'interfaces': self._get_if_agg_name(reverse),
                'chains': chains}

    def get_results(self):
        """Get the digested stats for the forward and reverse directions.

        return: a dictionary of results for each direction and each chain

        Example:

        {
            'Forward': {
                'interfaces': ['Port0', 'vhost0', 'Port1'],
                'chains': {
                    0: {'packets': [2000054, 1999996, 1999996],
                        'min_usec': 10,
                        'max_usec': 187,
                        'avg_usec': 45},
                    1: {...},
                    'total': {...}
                }
            },
            'Reverse': {...
            }
        }

        """
        results = {'Forward': self._get_results(),
                   'Reverse': self._get_results(reverse=True)}
        return results
