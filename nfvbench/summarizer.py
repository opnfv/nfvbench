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

import bitmath
from contextlib import contextmanager
from datetime import datetime
from fluentd import sender
import math
import pytz
from specs import ChainType
from tabulate import tabulate




class Formatter(object):
    """Collection of string formatter methods"""

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
        if type(data) == int:
            return Formatter.int(data)
        elif type(data) == float:
            return Formatter.float(4)(data)
        else:
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
        else:
            return bps.format("{value:.4f} bps")

    @staticmethod
    def percentage(data):
        if data is None:
            return ''
        elif math.isnan(data):
            return '-'
        else:
            return Formatter.suffix('%')(Formatter.float(4)(data))


class Table(object):
    """ASCII readable table class"""

    def __init__(self, header):
        header_row, self.formatters = zip(*header)
        self.data = [header_row]
        self.columns = len(header_row)

    def add_row(self, row):
        assert (self.columns == len(row))
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
    """Generic summarizer class"""

    indent_per_level = 2

    def __init__(self):
        self.indent_size = 0
        self.marker_stack = [False]
        self.str = ''

    def __indent(self, marker):
        self.indent_size += self.indent_per_level
        self.marker_stack.append(marker)

    def __unindent(self):
        assert (self.indent_size >= self.indent_per_level)
        self.indent_size -= self.indent_per_level
        self.marker_stack.pop()

    def __get_indent_string(self):
        current_str = ' ' * self.indent_size
        if self.marker_stack[-1]:
            current_str = current_str[:-2] + '> '
        return current_str

    def _put(self, *args):
        self.str += self.__get_indent_string()
        if len(args) and type(args[-1]) == dict:
            self.str += ' '.join(map(str, args[:-1])) + '\n'
            self._put_dict(args[-1])
        else:
            self.str += ' '.join(map(str, args)) + '\n'

    def _put_dict(self, data):
        with self._create_block(False):
            for key, value in data.iteritems():
                if type(value) == dict:
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
    """Summarize nfvbench json result"""

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

    chain_analysis_header = [
        ('Interface', Formatter.standard),
        ('Device', Formatter.standard),
        ('Packets (fwd)', Formatter.standard),
        ('Drops (fwd)', Formatter.standard),
        ('Drop% (fwd)', Formatter.percentage),
        ('Packets (rev)', Formatter.standard),
        ('Drops (rev)', Formatter.standard),
        ('Drop% (rev)', Formatter.percentage)
    ]

    direction_keys = ['direction-forward', 'direction-reverse', 'direction-total']
    direction_names = ['Forward', 'Reverse', 'Total']

    def __init__(self, result, runlogdate, fluentd_ip, fluentd_port):
        Summarizer.__init__(self)
        self.result = result
        self.config = self.result['config']
        self.runlogdate = runlogdate
        self.fluent_record_header = None
        self.fluent_record_data = None
        self.fluent_sender = None
        # runlogdate is set iff fluentd logger is enabled
        if self.runlogdate:
            self.fluent_sender = sender.FluentSender("resultnfvbench", host=fluentd_ip,
                                                     port=fluentd_port)
            self.__fluent_record_init()
        self.__summarize()

    def __summarize(self):
        self._put()
        self._put('========== NFVBench Summary ==========')
        self._put('Date:', self.result['date'])
        self._put('NFVBench version', self.result['nfvbench_version'])
        self._put('Openstack Neutron:', {
            'vSwitch': self.result['openstack_spec']['vswitch'],
            'Encapsulation': self.result['openstack_spec']['encaps']
        })
        self.__fluent_record_header_put('version', self.result['nfvbench_version'])
        self.__fluent_record_header_put('vSwitch', self.result['openstack_spec']['vswitch'])
        self.__fluent_record_header_put('Encapsulation', self.result['openstack_spec']['encaps'])
        self._put('Benchmarks:')
        with self._create_block():
            self._put('Networks:')
            with self._create_block():
                network_benchmark = self.result['benchmarks']['network']

                self._put('Components:')
                with self._create_block():
                    self._put('TOR:')
                    with self._create_block(False):
                        self._put('Type:', self.config['tor']['type'])
                    self._put('Traffic Generator:')
                    with self._create_block(False):
                        self._put('Profile:', self.config['generator_config']['name'])
                        self._put('Tool:', self.config['generator_config']['tool'])
                    if network_benchmark['versions']:
                        self._put('Versions:')
                        with self._create_block():
                            for component, version in network_benchmark['versions'].iteritems():
                                self._put(component + ':', version)

                if self.config['ndr_run'] or self.config['pdr_run']:
                    self._put('Measurement Parameters:')
                    with self._create_block(False):
                        if self.config['ndr_run']:
                            self._put('NDR:', self.config['measurement']['NDR'])
                        if self.config['pdr_run']:
                            self._put('PDR:', self.config['measurement']['PDR'])
                self._put('Service chain:')
                for result in network_benchmark['service_chain'].iteritems():
                    with self._create_block():
                        self.__chain_summarize(*result)

    def __chain_summarize(self, chain_name, chain_benchmark):
        self._put(chain_name + ':')
        if chain_name == ChainType.PVVP:
            self._put('Mode:', chain_benchmark.get('mode'))
            chain_name += "-" + chain_benchmark.get('mode')
        self.__fluent_record_header_put('service_chain', chain_name)
        with self._create_block():
            self._put('Traffic:')
            with self._create_block(False):
                self.__traffic_summarize(chain_benchmark['result'])

    def __traffic_summarize(self, traffic_benchmark):
        self._put('Profile:', traffic_benchmark['profile'])
        self._put('Bidirectional:', traffic_benchmark['bidirectional'])
        self._put('Flow count:', traffic_benchmark['flow_count'])
        self._put('Service chains count:', traffic_benchmark['service_chain_count'])
        self._put('Compute nodes:', traffic_benchmark['compute_nodes'].keys())

        self.__fluent_record_header_put('profile', traffic_benchmark['profile'])
        self.__fluent_record_header_put('bidirectional', traffic_benchmark['bidirectional'])
        self.__fluent_record_header_put('flow_count', traffic_benchmark['flow_count'])
        self.__fluent_record_header_put('sc_count',
                                        traffic_benchmark['service_chain_count'])
        self.__fluent_record_header_put('compute_nodes', traffic_benchmark['compute_nodes'].keys())
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

            for entry in traffic_benchmark['result'].iteritems():
                if 'warning' in entry:
                    continue
                self.__chain_analysis_summarize(*entry)
                self.__fluent_record_send()

    def __chain_analysis_summarize(self, frame_size, analysis):
        self._put()
        self._put('L2 frame size:', frame_size)
        if 'analysis_duration_sec' in analysis:
            self._put('Chain analysis duration:',
                      Formatter.float(3)(analysis['analysis_duration_sec']), 'seconds')
            self.__fluent_record_data_put(frame_size, {'chain_analysis_duration':
                                                       Formatter.float(3)(
                                                           analysis['analysis_duration_sec'])})
        if self.config['ndr_run']:
            self._put('NDR search duration:', Formatter.float(0)(analysis['ndr']['time_taken_sec']),
                      'seconds')
            self.__fluent_record_data_put(frame_size, {'ndr_search_duration': Formatter.float(0)(
                analysis['ndr']['time_taken_sec'])})
        if self.config['pdr_run']:
            self._put('PDR search duration:', Formatter.float(0)(analysis['pdr']['time_taken_sec']),
                      'seconds')
            self.__fluent_record_data_put(frame_size, {'pdr_search_duration': Formatter.float(0)(
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

        if 'packet_analysis' in analysis:
            self._put('Chain Analysis:')
            self._put()
            with self._create_block(False):
                self._put_table(self.__get_chain_analysis_table(analysis['packet_analysis']))
                self._put()

    def __get_summary_table(self, traffic_result):
        if self.config['single_run']:
            summary_table = Table(self.single_run_header)
        else:
            summary_table = Table(self.ndr_pdr_header)

        if self.config['ndr_run']:
            for frame_size, analysis in traffic_result.iteritems():
                if frame_size == 'warning':
                    continue
                summary_table.add_row([
                    'NDR',
                    frame_size,
                    analysis['ndr']['rate_bps'],
                    int(analysis['ndr']['rate_pps']),
                    analysis['ndr']['stats']['overall']['drop_percentage'],
                    analysis['ndr']['stats']['overall']['avg_delay_usec'],
                    analysis['ndr']['stats']['overall']['min_delay_usec'],
                    analysis['ndr']['stats']['overall']['max_delay_usec']
                ])
                self.__fluent_record_data_put(frame_size, {'ndr': {
                    'type': 'NDR',
                    'rate_bps': int(analysis['ndr']['rate_bps']),
                    'rate_pps': int(analysis['ndr']['rate_pps']),
                    'drop_percantage': analysis['ndr']['stats']['overall']['drop_percentage'],
                    'avg_delay_usec': int(analysis['ndr']['stats']['overall']['avg_delay_usec']),
                    'min_delay_usec': analysis['ndr']['stats']['overall']['min_delay_usec'],
                    'max_delay_usec': analysis['ndr']['stats']['overall']['max_delay_usec']
                }})
        if self.config['pdr_run']:
            for frame_size, analysis in traffic_result.iteritems():
                if frame_size == 'warning':
                    continue
                summary_table.add_row([
                    'PDR',
                    frame_size,
                    analysis['pdr']['rate_bps'],
                    int(analysis['pdr']['rate_pps']),
                    analysis['pdr']['stats']['overall']['drop_percentage'],
                    analysis['pdr']['stats']['overall']['avg_delay_usec'],
                    analysis['pdr']['stats']['overall']['min_delay_usec'],
                    analysis['pdr']['stats']['overall']['max_delay_usec']
                ])
                self.__fluent_record_data_put(frame_size, {'pdr': {
                    'type': 'PDR',
                    'rate_bps': int(analysis['pdr']['rate_bps']),
                    'rate_pps': int(analysis['pdr']['rate_pps']),
                    'drop_percantage': analysis['pdr']['stats']['overall']['drop_percentage'],
                    'avg_delay_usec': int(analysis['pdr']['stats']['overall']['avg_delay_usec']),
                    'min_delay_usec': analysis['pdr']['stats']['overall']['min_delay_usec'],
                    'max_delay_usec': analysis['pdr']['stats']['overall']['max_delay_usec']
                }})
        if self.config['single_run']:
            for frame_size, analysis in traffic_result.iteritems():
                summary_table.add_row([
                    frame_size,
                    analysis['stats']['overall']['drop_rate_percent'],
                    analysis['stats']['overall']['rx']['avg_delay_usec'],
                    analysis['stats']['overall']['rx']['min_delay_usec'],
                    analysis['stats']['overall']['rx']['max_delay_usec']
                ])
                self.__fluent_record_data_put(frame_size, {'single_run': {
                    'type': 'single_run',
                    'drop_rate_percent': analysis['stats']['overall']['drop_rate_percent'],
                    'avg_delay_usec': int(analysis['stats']['overall']['rx']['avg_delay_usec']),
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
            self.__fluent_record_data_put(frame_size, {
                name.lower() + "_orig_rate_bps": int(run_config[key]['orig']['rate_bps']),
                name.lower() + "_tx_rate_bps": int(run_config[key]['tx']['rate_bps']),
                name.lower() + "_rx_rate_bps": int(run_config[key]['rx']['rate_bps']),
                name.lower() + "_orig_rate_pps": int(run_config[key]['orig']['rate_pps']),
                name.lower() + "_tx_rate_pps": int(run_config[key]['tx']['rate_pps']),
                name.lower() + "_rx_rate_pps": int(run_config[key]['rx']['rate_pps']),

            })
        return config_table

    def __get_chain_analysis_table(self, packet_analysis):
        chain_analysis_table = Table(self.chain_analysis_header)
        forward_analysis = packet_analysis['direction-forward']
        reverse_analysis = packet_analysis['direction-reverse']
        reverse_analysis.reverse()
        for fwd, rev in zip(forward_analysis, reverse_analysis):
            chain_analysis_table.add_row([
                fwd['interface'],
                fwd['device'],
                fwd['packet_count'],
                fwd.get('packet_drop_count', None),
                fwd.get('packet_drop_percentage', None),
                rev['packet_count'],
                rev.get('packet_drop_count', None),
                rev.get('packet_drop_percentage', None),
            ])
        return chain_analysis_table

    def __fluent_record_header_put(self, key, value):
        if self.fluent_sender:
            self.fluent_record_header[key] = value

    def __fluent_record_data_put(self, key, data):
        if self.fluent_sender:
            if key not in self.fluent_record_data:
                self.fluent_record_data[key] = {}
            self.fluent_record_data[key].update(data)

    def __fluent_record_send(self):
        if self.fluent_sender:
            self.fluent_record_header["@timestamp"] = datetime.utcnow().replace(
                tzinfo=pytz.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f%z")
            for frame_size in self.fluent_record_data:
                data = self.fluent_record_header
                data['frame_size'] = frame_size
                data.update(self.fluent_record_data[frame_size])
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
                    self.fluent_sender.emit(None, data_to_send)
            self.__fluent_record_init()

    def __fluent_record_init(self):
        self.fluent_record_header = {
            "runlogdate": self.runlogdate,
        }
        self.fluent_record_data = {}
