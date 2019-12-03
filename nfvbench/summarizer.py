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

from contextlib import contextmanager
from datetime import datetime
import math

import bitmath
import pytz
from tabulate import tabulate

def _annotate_chain_stats(chain_stats, nodrop_marker='=>'):
    """Transform a plain chain stats into an annotated one.

    Example:
    {
         0: {'packets': [2000054, 1999996, 1999996, 1999996],
             'lat_min_usec': 10,
             'lat_max_usec': 187,
             'lat_avg_usec': 45},
         1: {...},
         'total': {...}
    }
    should become:
    {
         0: {'packets': [2000054, -58 (-0.034%), '=>', 1999996],
             'lat_min_usec': 10,
             'lat_max_usec': 187,
             'lat_avg_usec': 45},
         1: {...},
         'total': {...}
    }

    In the case of shared net, some columns in packets array can have ''.
    Some columns cab also be None which means the data is not available.
    """
    for stats in list(chain_stats.values()):
        packets = stats['packets']
        count = len(packets)
        if count > 1:
            # keep the first counter
            annotated_packets = [packets[0]]
            # modify all remaining counters
            prev_count = packets[0]
            for index in range(1, count):
                cur_count = packets[index]
                if cur_count == '':
                    # an empty string indicates an unknown counter for a shared interface
                    # do not annotate those
                    annotated_value = ''
                elif cur_count is None:
                    # Not available
                    annotated_value = 'n/a'
                else:
                    drop = cur_count - prev_count
                    if drop:
                        dr = (drop * 100.0) / prev_count if prev_count else 0
                        annotated_value = '{:+,} ({:+.4f}%)'.format(drop, dr)
                    else:
                        # no drop
                        # if last column we display the value
                        annotated_value = cur_count if index == count - 1 else nodrop_marker
                    prev_count = cur_count
                annotated_packets.append(annotated_value)

            stats['packets'] = annotated_packets

class Formatter(object):
    """Collection of string formatter methods."""

    @staticmethod
    def fixed(data):
        return data

    @staticmethod
    def int(data):
        return '{:,}'.format(data)

    @staticmethod
    def float(decimal):
        return lambda data: '%.{}f'.format(decimal) % (data)

    @staticmethod
    def standard(data):
        if isinstance(data, int):
            return Formatter.int(data)
        if isinstance(data, float):
            return Formatter.float(4)(data)
        return Formatter.fixed(data)

    @staticmethod
    def suffix(suffix_str):
        return lambda data: Formatter.standard(data) + suffix_str

    @staticmethod
    def bits(data):
        # By default, `best_prefix` returns a value in byte format, this hack (multiply by 8.0)
        # will convert it into bit format.
        bit = 8.0 * bitmath.Bit(float(data))
        bit = bit.best_prefix(bitmath.SI)
        byte_to_bit_classes = {
            'kB': bitmath.kb,
            'MB': bitmath.Mb,
            'GB': bitmath.Gb,
            'TB': bitmath.Tb,
            'PB': bitmath.Pb,
            'EB': bitmath.Eb,
            'ZB': bitmath.Zb,
            'YB': bitmath.Yb,
        }
        bps = byte_to_bit_classes.get(bit.unit, bitmath.Bit).from_other(bit) / 8.0
        if bps.unit != 'Bit':
            return bps.format("{value:.4f} {unit}ps")
        return bps.format("{value:.4f} bps")

    @staticmethod
    def percentage(data):
        if data is None:
            return ''
        if math.isnan(data):
            return '-'
        return Formatter.suffix('%')(Formatter.float(4)(data))


class Table(object):
    """ASCII readable table class."""

    def __init__(self, header):
        header_row, self.formatters = list(zip(*header))
        self.data = [header_row]
        self.columns = len(header_row)

    def add_row(self, row):
        assert self.columns == len(row)
        formatted_row = []
        for entry, formatter in zip(row, self.formatters):
            formatted_row.append(formatter(entry))
        self.data.append(formatted_row)

    def get_string(self, indent=0):
        spaces = ' ' * indent
        table = tabulate(self.data,
                         headers='firstrow',
                         tablefmt='grid',
                         stralign='center',
                         floatfmt='.2f')
        return table.replace('\n', '\n' + spaces)


class Summarizer(object):
    """Generic summarizer class."""

    indent_per_level = 2

    def __init__(self):
        self.indent_size = 0
        self.marker_stack = [False]
        self.str = ''

    def __indent(self, marker):
        self.indent_size += self.indent_per_level
        self.marker_stack.append(marker)

    def __unindent(self):
        assert self.indent_size >= self.indent_per_level
        self.indent_size -= self.indent_per_level
        self.marker_stack.pop()

    def __get_indent_string(self):
        current_str = ' ' * self.indent_size
        if self.marker_stack[-1]:
            current_str = current_str[:-2] + '> '
        return current_str

    def _put(self, *args):
        self.str += self.__get_indent_string()
        if args and isinstance(args[-1], dict):
            self.str += ' '.join(map(str, args[:-1])) + '\n'
            self._put_dict(args[-1])
        else:
            self.str += ' '.join(map(str, args)) + '\n'

    def _put_dict(self, data):
        with self._create_block(False):
            for key, value in list(data.items()):
                if isinstance(value, dict):
                    self._put(key + ':')
                    self._put_dict(value)
                else:
                    self._put(key + ':', value)

    def _put_table(self, table):
        self.str += self.__get_indent_string()
        self.str += table.get_string(self.indent_size) + '\n'

    def __str__(self):
        return self.str

    @contextmanager
    def _create_block(self, marker=True):
        self.__indent(marker)
        yield
        self.__unindent()


class NFVBenchSummarizer(Summarizer):
    """Summarize nfvbench json result."""

    ndr_pdr_header = [
        ('-', Formatter.fixed),
        ('L2 Frame Size', Formatter.standard),
        ('Rate (fwd+rev)', Formatter.bits),
        ('Rate (fwd+rev)', Formatter.suffix(' pps')),
        ('Avg Drop Rate', Formatter.suffix('%')),
        ('Avg Latency (usec)', Formatter.standard),
        ('Min Latency (usec)', Formatter.standard),
        ('Max Latency (usec)', Formatter.standard)
    ]

    single_run_header = [
        ('L2 Frame Size', Formatter.standard),
        ('Drop Rate', Formatter.suffix('%')),
        ('Avg Latency (usec)', Formatter.standard),
        ('Min Latency (usec)', Formatter.standard),
        ('Max Latency (usec)', Formatter.standard)
    ]

    config_header = [
        ('Direction', Formatter.standard),
        ('Requested TX Rate (bps)', Formatter.bits),
        ('Actual TX Rate (bps)', Formatter.bits),
        ('RX Rate (bps)', Formatter.bits),
        ('Requested TX Rate (pps)', Formatter.suffix(' pps')),
        ('Actual TX Rate (pps)', Formatter.suffix(' pps')),
        ('RX Rate (pps)', Formatter.suffix(' pps'))
    ]

    direction_keys = ['direction-forward', 'direction-reverse', 'direction-total']
    direction_names = ['Forward', 'Reverse', 'Total']

    def __init__(self, result, sender):
        """Create a summarizer instance."""
        Summarizer.__init__(self)
        self.result = result
        self.config = self.result['config']
        self.record_header = None
        self.record_data = None
        self.sender = sender
        # if sender is available initialize record
        if self.sender:
            self.__record_init()
        self.__summarize()

    def __get_openstack_spec(self, property):
        try:
            return self.result['openstack_spec'][property]
        except KeyError:
            return ''

    def __summarize(self):
        self._put()
        self._put('========== NFVBench Summary ==========')
        self._put('Date:', self.result['date'])
        self._put('NFVBench version', self.result['nfvbench_version'])
        self._put('Openstack Neutron:', {
            'vSwitch': self.__get_openstack_spec('vswitch'),
            'Encapsulation': self.__get_openstack_spec('encaps')
        })
        self.__record_header_put('version', self.result['nfvbench_version'])
        self.__record_header_put('vSwitch', self.__get_openstack_spec('vswitch'))
        self.__record_header_put('Encapsulation', self.__get_openstack_spec('encaps'))
        self._put('Benchmarks:')
        with self._create_block():
            self._put('Networks:')
            with self._create_block():
                network_benchmark = self.result['benchmarks']['network']

                self._put('Components:')
                with self._create_block():
                    self._put('Traffic Generator:')
                    with self._create_block(False):
                        self._put('Profile:', self.config['tg-name'])
                        self._put('Tool:', self.config['tg-tool'])
                    if network_benchmark['versions']:
                        self._put('Versions:')
                        with self._create_block():
                            for component, version in list(network_benchmark['versions'].items()):
                                self._put(component + ':', version)

                if self.config['ndr_run'] or self.config['pdr_run']:
                    self._put('Measurement Parameters:')
                    with self._create_block(False):
                        if self.config['ndr_run']:
                            self._put('NDR:', self.config['measurement']['NDR'])
                        if self.config['pdr_run']:
                            self._put('PDR:', self.config['measurement']['PDR'])
                self._put('Service chain:')
                for result in list(network_benchmark['service_chain'].items()):
                    with self._create_block():
                        self.__chain_summarize(*result)

    def __chain_summarize(self, chain_name, chain_benchmark):
        self._put(chain_name + ':')
        self.__record_header_put('service_chain', chain_name)
        with self._create_block():
            self._put('Traffic:')
            with self._create_block(False):
                self.__traffic_summarize(chain_benchmark['result'])

    def __traffic_summarize(self, traffic_benchmark):
        self._put('Profile:', traffic_benchmark['profile'])
        self._put('Bidirectional:', traffic_benchmark['bidirectional'])
        self._put('Flow count:', traffic_benchmark['flow_count'])
        self._put('Service chains count:', traffic_benchmark['service_chain_count'])
        self._put('Compute nodes:', list(traffic_benchmark['compute_nodes'].keys()))

        self.__record_header_put('profile', traffic_benchmark['profile'])
        self.__record_header_put('bidirectional', traffic_benchmark['bidirectional'])
        self.__record_header_put('flow_count', traffic_benchmark['flow_count'])
        self.__record_header_put('sc_count', traffic_benchmark['service_chain_count'])
        self.__record_header_put('compute_nodes', list(traffic_benchmark['compute_nodes'].keys()))
        with self._create_block(False):
            self._put()
            if not self.config['no_traffic']:
                self._put('Run Summary:')
                self._put()
                with self._create_block(False):
                    self._put_table(self.__get_summary_table(traffic_benchmark['result']))
                    try:
                        self._put()
                        self._put(traffic_benchmark['result']['warning'])
                    except KeyError:
                        pass

            for entry in list(traffic_benchmark['result'].items()):
                if 'warning' in entry:
                    continue
                self.__chain_analysis_summarize(*entry)
            self.__record_send()

    def __chain_analysis_summarize(self, frame_size, analysis):
        self._put()
        self._put('L2 frame size:', frame_size)
        if self.config['ndr_run']:
            self._put('NDR search duration:', Formatter.float(0)(analysis['ndr']['time_taken_sec']),
                      'seconds')
            self.__record_data_put(frame_size, {'ndr_search_duration': Formatter.float(0)(
                analysis['ndr']['time_taken_sec'])})
        if self.config['pdr_run']:
            self._put('PDR search duration:', Formatter.float(0)(analysis['pdr']['time_taken_sec']),
                      'seconds')
            self.__record_data_put(frame_size, {'pdr_search_duration': Formatter.float(0)(
                analysis['pdr']['time_taken_sec'])})
        self._put()

        if not self.config['no_traffic'] and self.config['single_run']:
            self._put('Run Config:')
            self._put()
            with self._create_block(False):
                self._put_table(self.__get_config_table(analysis['run_config'], frame_size))
                if 'warning' in analysis['run_config'] and analysis['run_config']['warning']:
                    self._put()
                    self._put(analysis['run_config']['warning'])
                self._put()

        if 'packet_path_stats' in analysis:
            for dir in ['Forward', 'Reverse']:
                self._put(dir + ' Chain Packet Counters and Latency:')
                self._put()
                with self._create_block(False):
                    self._put_table(self._get_chain_table(analysis['packet_path_stats'][dir]))
                    self._put()

    def __get_summary_table(self, traffic_result):
        if self.config['single_run']:
            summary_table = Table(self.single_run_header)
        else:
            summary_table = Table(self.ndr_pdr_header)

        if self.config['ndr_run']:
            for frame_size, analysis in list(traffic_result.items()):
                if frame_size == 'warning':
                    continue
                summary_table.add_row([
                    'NDR',
                    frame_size,
                    analysis['ndr']['rate_bps'],
                    analysis['ndr']['rate_pps'],
                    analysis['ndr']['stats']['overall']['drop_percentage'],
                    analysis['ndr']['stats']['overall']['avg_delay_usec'],
                    analysis['ndr']['stats']['overall']['min_delay_usec'],
                    analysis['ndr']['stats']['overall']['max_delay_usec']
                ])
                self.__record_data_put(frame_size, {'ndr': {
                    'type': 'NDR',
                    'rate_bps': analysis['ndr']['rate_bps'],
                    'rate_pps': analysis['ndr']['rate_pps'],
                    'drop_percentage': analysis['ndr']['stats']['overall']['drop_percentage'],
                    'avg_delay_usec': analysis['ndr']['stats']['overall']['avg_delay_usec'],
                    'min_delay_usec': analysis['ndr']['stats']['overall']['min_delay_usec'],
                    'max_delay_usec': analysis['ndr']['stats']['overall']['max_delay_usec']
                }})
        if self.config['pdr_run']:
            for frame_size, analysis in list(traffic_result.items()):
                if frame_size == 'warning':
                    continue
                summary_table.add_row([
                    'PDR',
                    frame_size,
                    analysis['pdr']['rate_bps'],
                    analysis['pdr']['rate_pps'],
                    analysis['pdr']['stats']['overall']['drop_percentage'],
                    analysis['pdr']['stats']['overall']['avg_delay_usec'],
                    analysis['pdr']['stats']['overall']['min_delay_usec'],
                    analysis['pdr']['stats']['overall']['max_delay_usec']
                ])
                self.__record_data_put(frame_size, {'pdr': {
                    'type': 'PDR',
                    'rate_bps': analysis['pdr']['rate_bps'],
                    'rate_pps': analysis['pdr']['rate_pps'],
                    'drop_percentage': analysis['pdr']['stats']['overall']['drop_percentage'],
                    'avg_delay_usec': analysis['pdr']['stats']['overall']['avg_delay_usec'],
                    'min_delay_usec': analysis['pdr']['stats']['overall']['min_delay_usec'],
                    'max_delay_usec': analysis['pdr']['stats']['overall']['max_delay_usec']
                }})
        if self.config['single_run']:
            for frame_size, analysis in list(traffic_result.items()):
                summary_table.add_row([
                    frame_size,
                    analysis['stats']['overall']['drop_rate_percent'],
                    analysis['stats']['overall']['rx']['avg_delay_usec'],
                    analysis['stats']['overall']['rx']['min_delay_usec'],
                    analysis['stats']['overall']['rx']['max_delay_usec']
                ])
                self.__record_data_put(frame_size, {'single_run': {
                    'type': 'single_run',
                    'drop_rate_percent': analysis['stats']['overall']['drop_rate_percent'],
                    'avg_delay_usec': analysis['stats']['overall']['rx']['avg_delay_usec'],
                    'min_delay_usec': analysis['stats']['overall']['rx']['min_delay_usec'],
                    'max_delay_usec': analysis['stats']['overall']['rx']['max_delay_usec']
                }})
        return summary_table

    def __get_config_table(self, run_config, frame_size):
        config_table = Table(self.config_header)
        for key, name in zip(self.direction_keys, self.direction_names):
            if key not in run_config:
                continue
            config_table.add_row([
                name,
                run_config[key]['orig']['rate_bps'],
                run_config[key]['tx']['rate_bps'],
                run_config[key]['rx']['rate_bps'],
                int(run_config[key]['orig']['rate_pps']),
                int(run_config[key]['tx']['rate_pps']),
                int(run_config[key]['rx']['rate_pps']),
            ])
            self.__record_data_put(frame_size, {
                name.lower() + "_orig_rate_bps": int(run_config[key]['orig']['rate_bps']),
                name.lower() + "_tx_rate_bps": int(run_config[key]['tx']['rate_bps']),
                name.lower() + "_rx_rate_bps": int(run_config[key]['rx']['rate_bps']),
                name.lower() + "_orig_rate_pps": int(run_config[key]['orig']['rate_pps']),
                name.lower() + "_tx_rate_pps": int(run_config[key]['tx']['rate_pps']),
                name.lower() + "_rx_rate_pps": int(run_config[key]['rx']['rate_pps']),

            })
        return config_table

    def _get_chain_table(self, chain_stats):
        """Retrieve the table for a direction.

        chain_stats: {
             'interfaces': ['Port0', 'drop %'', 'vhost0', 'Port1'],
             'chains': {
                 0: {'packets': [2000054, '-0.023%', 1999996, 1999996],
                     'lat_min_usec': 10,
                     'lat_max_usec': 187,
                     'lat_avg_usec': 45},
                 1: {...},
                 'total': {...}
             }
        }
        """
        chains = chain_stats['chains']
        _annotate_chain_stats(chains)
        header = [('Chain', Formatter.standard)] + \
                 [(ifname, Formatter.standard) for ifname in chain_stats['interfaces']]
        # add latency columns if available Avg, Min, Max
        lat_keys = []
        lat_map = {'lat_avg_usec': 'Avg lat.',
                   'lat_min_usec': 'Min lat.',
                   'lat_max_usec': 'Max lat.'}
        if 'lat_avg_usec' in chains[0]:
            lat_keys = ['lat_avg_usec', 'lat_min_usec', 'lat_max_usec']
            for key in lat_keys:
                header.append((lat_map[key], Formatter.standard))

        table = Table(header)
        for chain in sorted(chains.keys()):
            row = [chain] + chains[chain]['packets']
            for lat_key in lat_keys:
                row.append('{:,} usec'.format(chains[chain][lat_key]))
            table.add_row(row)
        return table

    def __record_header_put(self, key, value):
        if self.sender:
            self.record_header[key] = value

    def __record_data_put(self, key, data):
        if self.sender:
            if key not in self.record_data:
                self.record_data[key] = {}
            self.record_data[key].update(data)

    def __record_send(self):
        if self.sender:
            self.record_header["@timestamp"] = datetime.utcnow().replace(
                tzinfo=pytz.utc).strftime("%Y-%m-%dT%H:%M:%S.%f%z")
            for frame_size in self.record_data:
                data = self.record_header
                data['frame_size'] = frame_size
                data.update(self.record_data[frame_size])
                run_specific_data = {}
                if 'single_run' in data:
                    run_specific_data['single_run'] = data['single_run']
                    del data['single_run']
                if 'ndr' in data:
                    run_specific_data['ndr'] = data['ndr']
                    run_specific_data['ndr']['drop_limit'] = self.config['measurement']['NDR']
                    del data['ndr']
                if 'pdr' in data:
                    run_specific_data['pdr'] = data['pdr']
                    run_specific_data['pdr']['drop_limit'] = self.config['measurement']['PDR']
                    del data['pdr']
                for key in run_specific_data:
                    data_to_send = data.copy()
                    data_to_send.update(run_specific_data[key])
                    self.sender.record_send(data_to_send)
            self.__record_init()

    def __record_init(self):
        # init is called after checking for sender
        self.record_header = {
            "runlogdate": self.sender.runlogdate,
            "user_label": self.config['user_label']
        }
        self.record_data = {}
