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


import time


class StatsCollector(object):
    """Base class for all stats collector classes."""

    def __init__(self, start_time):
        self.start_time = start_time
        self.stats = []

    def get(self):
        return self.stats

    def peek(self):
        return self.stats[-1]

    @staticmethod
    def _get_drop_percentage(drop_pkts, total_pkts):
        return float(drop_pkts * 100) / total_pkts

    @staticmethod
    def _get_rx_pps(tx_pps, drop_percentage):
        return (tx_pps * (100 - drop_percentage)) / 100

    def _get_current_time_diff(self):
        return int((time.time() - self.start_time) * 1000)


class IntervalCollector(StatsCollector):
    """Collects stats while traffic is running. Frequency is specified by 'interval_sec' setting."""

    last_tx_pkts = 0
    last_rx_pkts = 0
    last_time = 0

    def __init__(self, start_time):
        StatsCollector.__init__(self, start_time)
        self.notifier = None

    def attach_notifier(self, notifier):
        self.notifier = notifier

    def add(self, stats):
        if self.notifier:
            current_stats = self.__compute_tx_rx_diff(stats)
            self.notifier.send_interval_stats(**current_stats)

    def reset(self):
        # don't reset time!
        self.last_rx_pkts = 0
        self.last_tx_pkts = 0

    def add_ndr_pdr(self, tag, stats):
        if self.notifier:

            current_time = self._get_current_time_diff()
            rx_pps = self._get_rx_pps(stats['tx_pps'], stats['drop_percentage'])

            self.last_tx_pkts = stats['tx_pps'] / 1000 * (current_time - self.last_time)
            self.last_rx_pkts = rx_pps / 1000 * (current_time - self.last_time)
            self.last_time = current_time

            # 'drop_pct' key is an unfortunate name, since in iteration stats it means
            # number of the packets. More suitable would be 'drop_percentage'.
            # FDS frontend depends on this key
            current_stats = {
                '{}_pps'.format(tag): stats['tx_pps'],
                'tx_pps': stats['tx_pps'],
                'rx_pps': rx_pps,
                'drop_pct': stats['drop_percentage'],
                'time_ms': current_time
            }

            self.notifier.send_interval_stats(time_ms=current_stats['time_ms'],
                                              tx_pps=current_stats['tx_pps'],
                                              rx_pps=current_stats['rx_pps'],
                                              drop_pct=current_stats['drop_pct'])
            if tag == 'ndr':
                self.notifier.send_ndr_found(stats['tx_pps'])
            else:
                self.notifier.send_pdr_found(stats['tx_pps'])

    def __compute_tx_rx_diff(self, stats):
        current_time = self._get_current_time_diff()
        tx_diff = stats['overall']['tx']['total_pkts'] - self.last_tx_pkts
        tx_pps = (tx_diff * 1000) / (current_time - self.last_time)
        rx_diff = stats['overall']['rx']['total_pkts'] - self.last_rx_pkts
        rx_pps = (rx_diff * 1000) / (current_time - self.last_time)

        self.last_rx_pkts = stats['overall']['rx']['total_pkts']
        self.last_tx_pkts = stats['overall']['tx']['total_pkts']
        self.last_time = current_time

        return {
            'tx_pps': tx_pps,
            'rx_pps': rx_pps,
            'drop_pct': max(0.0, (1 - (float(rx_pps) / tx_pps)) * 100),
            'time_ms': current_time
        }


class IterationCollector(StatsCollector):
    """Collects stats after traffic is stopped. Frequency is specified by 'duration_sec' setting."""

    def __init__(self, start_time):
        StatsCollector.__init__(self, start_time)

    def add(self, stats, tx_pps):
        drop_percentage = self._get_drop_percentage(stats['overall']['rx']['dropped_pkts'],
                                                    stats['overall']['tx']['total_pkts'])

        record = {
            'total_tx_pps': int(stats['total_tx_rate']),
            'tx_pps': tx_pps,
            'tx_pkts': stats['overall']['tx']['total_pkts'],
            'rx_pps': self._get_rx_pps(tx_pps, drop_percentage),
            'rx_pkts': stats['overall']['rx']['total_pkts'],
            'drop_pct': stats['overall']['rx']['dropped_pkts'],
            'drop_percentage': drop_percentage,
            'time_ms': int(time.time() * 1000)
        }

        if 'warning' in stats:
            record['warning'] = stats['warning']

        self.stats.append(record)

    def add_ndr_pdr(self, tag, rate):
        last_stats = self.peek()
        last_stats['{}_pps'.format(tag)] = rate
