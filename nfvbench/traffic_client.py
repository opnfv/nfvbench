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

from attrdict import AttrDict
import bitmath
from datetime import datetime
from log import LOG
from netaddr import IPNetwork
from network import Interface
import socket
from specs import ChainType
from stats_collector import IntervalCollector
from stats_collector import IterationCollector
import struct
import time
import traffic_gen.traffic_utils as utils


class TrafficClientException(Exception):
    pass


class TrafficRunner(object):

    def __init__(self, client, duration_sec, interval_sec=0):
        self.client = client
        self.start_time = None
        self.duration_sec = duration_sec
        self.interval_sec = interval_sec

    def run(self):
        LOG.info('Running traffic generator')
        self.client.gen.clear_stats()
        self.client.gen.start_traffic()
        self.start_time = time.time()
        return self.poll_stats()

    def stop(self):
        if self.is_running():
            self.start_time = None
            self.client.gen.stop_traffic()

    def is_running(self):
        return self.start_time is not None

    def time_elapsed(self):
        if self.is_running():
            return time.time() - self.start_time
        else:
            return self.duration_sec

    def poll_stats(self):
        if not self.is_running():
            return None
        time_elapsed = self.time_elapsed()
        if time_elapsed > self.duration_sec:
            self.stop()
            return None
        time_left = self.duration_sec - time_elapsed
        if self.interval_sec > 0.0:
            if time_left <= self.interval_sec:
                time.sleep(time_left)
                self.stop()
            else:
                time.sleep(self.interval_sec)
        else:
            time.sleep(self.duration_sec)
            self.stop()
        return self.client.get_stats()


class Device(object):

    def __init__(self, port, pci, switch_port=None, vtep_vlan=None, ip=None, tg_gateway_ip=None,
                 gateway_ip=None, ip_addrs_step=None, tg_gateway_ip_addrs_step=None,
                 gateway_ip_addrs_step=None, udp_src_port=None, udp_dst_port=None,
                 chain_count=1, flow_count=1, vlan_tagging=False):
        self.chain_count = chain_count
        self.flow_count = flow_count
        self.dst = None
        self.port = port
        self.switch_port = switch_port
        self.vtep_vlan = vtep_vlan
        self.vlan_tag = None
        self.vlan_tagging = vlan_tagging
        self.pci = pci
        self.mac = None
        self.vm_mac_list = None
        subnet = IPNetwork(ip)
        self.ip = subnet.ip.format()
        self.ip_prefixlen = subnet.prefixlen
        self.ip_addrs_step = ip_addrs_step
        self.tg_gateway_ip_addrs_step = tg_gateway_ip_addrs_step
        self.gateway_ip_addrs_step = gateway_ip_addrs_step
        self.ip_list = self.expand_ip(self.ip, self.ip_addrs_step, self.flow_count)
        self.gateway_ip = gateway_ip
        self.gateway_ip_list = self.expand_ip(self.gateway_ip,
                                              self.gateway_ip_addrs_step,
                                              self.chain_count)
        self.tg_gateway_ip = tg_gateway_ip
        self.tg_gateway_ip_list = self.expand_ip(self.tg_gateway_ip,
                                                 self.tg_gateway_ip_addrs_step,
                                                 self.chain_count)
        self.udp_src_port = udp_src_port
        self.udp_dst_port = udp_dst_port

    def set_mac(self, mac):
        if mac is None:
            raise TrafficClientException('Trying to set traffic generator MAC address as None')
        self.mac = mac

    def set_destination(self, dst):
        self.dst = dst

    def set_vm_mac_list(self, vm_mac_list):
        self.vm_mac_list = map(str, vm_mac_list)

    def set_vlan_tag(self, vlan_tag):
        if self.vlan_tagging and vlan_tag is None:
            raise TrafficClientException('Trying to set VLAN tag as None')
        self.vlan_tag = vlan_tag

    def get_stream_configs(self, service_chain):
        configs = []
        flow_idx = 0
        for chain_idx in xrange(self.chain_count):
            current_flow_count = (self.flow_count - flow_idx) / (self.chain_count - chain_idx)
            max_idx = flow_idx + current_flow_count - 1
            ip_src_count = self.ip_to_int(self.ip_list[max_idx]) - \
                self.ip_to_int(self.ip_list[flow_idx]) + 1
            ip_dst_count = self.ip_to_int(self.dst.ip_list[max_idx]) - \
                self.ip_to_int(self.dst.ip_list[flow_idx]) + 1

            configs.append({
                'count': current_flow_count,
                'mac_src': self.mac,
                'mac_dst': self.dst.mac if service_chain == ChainType.EXT
                else self.vm_mac_list[chain_idx],
                'ip_src_addr': self.ip_list[flow_idx],
                'ip_src_addr_max': self.ip_list[max_idx],
                'ip_src_count': ip_src_count,
                'ip_dst_addr': self.dst.ip_list[flow_idx],
                'ip_dst_addr_max': self.dst.ip_list[max_idx],
                'ip_dst_count': ip_dst_count,
                'ip_addrs_step': self.ip_addrs_step,
                'udp_src_port': self.udp_src_port,
                'udp_dst_port': self.udp_dst_port,
                'mac_discovery_gw': self.gateway_ip_list[chain_idx],
                'ip_src_tg_gw': self.tg_gateway_ip_list[chain_idx],
                'ip_dst_tg_gw': self.dst.tg_gateway_ip_list[chain_idx],
                'vlan_tag': self.vlan_tag if self.vlan_tagging else None
            })

            flow_idx += current_flow_count
        return configs

    @classmethod
    def expand_ip(cls, ip, step_ip, count):
        if step_ip == 'random':
            # Repeatable Random will used in the stream src/dst IP pairs, but we still need
            # to expand the IP based on the number of chains and flows configured. So we use
            # "0.0.0.1" as the step to have the exact IP flow ranges for every chain.
            step_ip = '0.0.0.1'

        step_ip_in_int = cls.ip_to_int(step_ip)
        subnet = IPNetwork(ip)
        ip_list = []
        for _ in xrange(count):
            ip_list.append(subnet.ip.format())
            subnet = subnet.next(step_ip_in_int)
        return ip_list

    @staticmethod
    def mac_to_int(mac):
        return int(mac.translate(None, ":.- "), 16)

    @staticmethod
    def int_to_mac(i):
        mac = format(i, 'x').zfill(12)
        blocks = [mac[x:x + 2] for x in xrange(0, len(mac), 2)]
        return ':'.join(blocks)

    @staticmethod
    def ip_to_int(addr):
        return struct.unpack("!I", socket.inet_aton(addr))[0]


class RunningTrafficProfile(object):
    """Represents traffic configuration for currently running traffic profile."""

    DEFAULT_IP_STEP = '0.0.0.1'
    DEFAULT_SRC_DST_IP_STEP = '0.0.0.1'

    def __init__(self, config, generator_profile):
        generator_config = self.__match_generator_profile(config.traffic_generator,
                                                          generator_profile)
        self.generator_config = generator_config
        self.service_chain = config.service_chain
        self.service_chain_count = config.service_chain_count
        self.flow_count = config.flow_count
        self.host_name = generator_config.host_name
        self.name = generator_config.name
        self.tool = generator_config.tool
        self.cores = generator_config.get('cores', 1)
        self.ip_addrs_step = generator_config.ip_addrs_step or self.DEFAULT_SRC_DST_IP_STEP
        self.tg_gateway_ip_addrs_step = \
            generator_config.tg_gateway_ip_addrs_step or self.DEFAULT_IP_STEP
        self.gateway_ip_addrs_step = generator_config.gateway_ip_addrs_step or self.DEFAULT_IP_STEP
        self.gateway_ips = generator_config.gateway_ip_addrs
        self.ip = generator_config.ip
        self.intf_speed = bitmath.parse_string(generator_config.intf_speed.replace('ps', '')).bits
        self.vlan_tagging = config.vlan_tagging
        self.no_arp = config.no_arp
        self.src_device = None
        self.dst_device = None
        self.vm_mac_list = None
        self.__prep_interfaces(generator_config)

    def to_json(self):
        return dict(self.generator_config)

    def set_vm_mac_list(self, vm_mac_list):
        self.src_device.set_vm_mac_list(vm_mac_list[0])
        self.dst_device.set_vm_mac_list(vm_mac_list[1])

    @staticmethod
    def __match_generator_profile(traffic_generator, generator_profile):
        generator_config = AttrDict(traffic_generator)
        generator_config.pop('default_profile')
        generator_config.pop('generator_profile')
        matching_profile = filter(lambda profile: profile.name == generator_profile,
                                  traffic_generator.generator_profile)
        if len(matching_profile) != 1:
            raise Exception('Traffic generator profile not found: ' + generator_profile)

        generator_config.update(matching_profile[0])

        return generator_config

    def __prep_interfaces(self, generator_config):
        src_config = {
            'chain_count': self.service_chain_count,
            'flow_count': self.flow_count / 2,
            'ip': generator_config.ip_addrs[0],
            'ip_addrs_step': self.ip_addrs_step,
            'gateway_ip': self.gateway_ips[0],
            'gateway_ip_addrs_step': self.gateway_ip_addrs_step,
            'tg_gateway_ip': generator_config.tg_gateway_ip_addrs[0],
            'tg_gateway_ip_addrs_step': self.tg_gateway_ip_addrs_step,
            'udp_src_port': generator_config.udp_src_port,
            'udp_dst_port': generator_config.udp_dst_port,
            'vlan_tagging': self.vlan_tagging
        }
        dst_config = {
            'chain_count': self.service_chain_count,
            'flow_count': self.flow_count / 2,
            'ip': generator_config.ip_addrs[1],
            'ip_addrs_step': self.ip_addrs_step,
            'gateway_ip': self.gateway_ips[1],
            'gateway_ip_addrs_step': self.gateway_ip_addrs_step,
            'tg_gateway_ip': generator_config.tg_gateway_ip_addrs[1],
            'tg_gateway_ip_addrs_step': self.tg_gateway_ip_addrs_step,
            'udp_src_port': generator_config.udp_src_port,
            'udp_dst_port': generator_config.udp_dst_port,
            'vlan_tagging': self.vlan_tagging
        }

        self.src_device = Device(**dict(src_config, **generator_config.interfaces[0]))
        self.dst_device = Device(**dict(dst_config, **generator_config.interfaces[1]))
        self.src_device.set_destination(self.dst_device)
        self.dst_device.set_destination(self.src_device)

        if self.service_chain == ChainType.EXT and not self.no_arp \
                and not self.__are_unique(self.src_device.ip_list, self.dst_device.ip_list):
            raise Exception('Computed IP addresses are not unique, choose different base. '
                            'Start IPs: {start}. End IPs: {end}'
                            .format(start=self.src_device.ip_list,
                                    end=self.dst_device.ip_list))

    def __are_unique(self, list1, list2):
        return set(list1).isdisjoint(set(list2))

    @property
    def devices(self):
        return [self.src_device, self.dst_device]

    @property
    def vlans(self):
        return [self.src_device.vtep_vlan, self.dst_device.vtep_vlan]

    @property
    def ports(self):
        return [self.src_device.port, self.dst_device.port]

    @property
    def switch_ports(self):
        return [self.src_device.switch_port, self.dst_device.switch_port]

    @property
    def pcis(self):
        return [self.src_device.pci, self.dst_device.pci]


class TrafficGeneratorFactory(object):

    def __init__(self, config):
        self.config = config

    def get_tool(self):
        return self.config.generator_config.tool

    def get_generator_client(self):
        tool = self.get_tool().lower()
        if tool == 'trex':
            from traffic_gen import trex
            return trex.TRex(self.config)
        elif tool == 'dummy':
            from traffic_gen import dummy
            return dummy.DummyTG(self.config)
        else:
            return None

    def list_generator_profile(self):
        return [profile.name for profile in self.config.traffic_generator.generator_profile]

    def get_generator_config(self, generator_profile):
        return RunningTrafficProfile(self.config, generator_profile)

    def get_matching_profile(self, traffic_profile_name):
        matching_profile = filter(lambda profile: profile.name == traffic_profile_name,
                                  self.config.traffic_profile)

        if len(matching_profile) > 1:
            raise Exception('Multiple traffic profiles with the same name found.')
        elif len(matching_profile) == 0:
            raise Exception('No traffic profile found.')

        return matching_profile[0]

    def get_frame_sizes(self, traffic_profile):
        matching_profile = self.get_matching_profile(traffic_profile)
        return matching_profile.l2frame_size


class TrafficClient(object):

    PORTS = [0, 1]

    def __init__(self, config, notifier=None):
        generator_factory = TrafficGeneratorFactory(config)
        self.gen = generator_factory.get_generator_client()
        self.tool = generator_factory.get_tool()
        self.config = config
        self.notifier = notifier
        self.interval_collector = None
        self.iteration_collector = None
        self.runner = TrafficRunner(self, self.config.duration_sec, self.config.interval_sec)
        if self.gen is None:
            raise TrafficClientException('%s is not a supported traffic generator' % self.tool)

        self.run_config = {
            'l2frame_size': None,
            'duration_sec': self.config.duration_sec,
            'bidirectional': True,
            'rates': None
        }
        self.current_total_rate = {'rate_percent': '10'}
        if self.config.single_run:
            self.current_total_rate = utils.parse_rate_str(self.config.rate)

    def set_macs(self):
        for mac, device in zip(self.gen.get_macs(), self.config.generator_config.devices):
            device.set_mac(mac)

    def start_traffic_generator(self):
        self.gen.init()
        self.gen.connect()

    def setup(self):
        self.gen.set_mode()
        self.gen.config_interface()
        self.gen.clear_stats()

    def get_version(self):
        return self.gen.get_version()

    def ensure_end_to_end(self):
        """
        Ensure traffic generator receives packets it has transmitted.
        This ensures end to end connectivity and also waits until VMs are ready to forward packets.

        At this point all VMs are in active state, but forwarding does not have to work.
        Small amount of traffic is sent to every chain. Then total of sent and received packets
        is compared. If ratio between received and transmitted packets is higher than (N-1)/N,
        N being number of chains, traffic flows through every chain and real measurements can be
        performed.

        Example:
            PVP chain (1 VM per chain)
            N = 10 (number of chains)
            threshold = (N-1)/N = 9/10 = 0.9 (acceptable ratio ensuring working conditions)
            if total_received/total_sent > 0.9, traffic is flowing to more than 9 VMs meaning
            all 10 VMs are in operational state.
        """
        LOG.info('Starting traffic generator to ensure end-to-end connectivity')
        rate_pps = {'rate_pps': str(self.config.service_chain_count * 100)}
        self.gen.create_traffic('64', [rate_pps, rate_pps], bidirectional=True, latency=False)

        # ensures enough traffic is coming back
        threshold = (self.config.service_chain_count - 1) / float(self.config.service_chain_count)

        for it in xrange(self.config.generic_retry_count):
            self.gen.clear_stats()
            self.gen.start_traffic()
            LOG.info('Waiting for packets to be received back... ({} / {})'.format(it + 1,
                     self.config.generic_retry_count))
            time.sleep(self.config.generic_poll_sec)
            self.gen.stop_traffic()
            stats = self.gen.get_stats()

            # compute total sent and received traffic on both ports
            total_rx = 0
            total_tx = 0
            for port in self.PORTS:
                total_rx += float(stats[port]['rx'].get('total_pkts', 0))
                total_tx += float(stats[port]['tx'].get('total_pkts', 0))

            # how much of traffic came back
            ratio = total_rx / total_tx if total_tx else 0

            if ratio > threshold:
                self.gen.clear_stats()
                self.gen.clear_streamblock()
                LOG.info('End-to-end connectivity ensured')
                return

            time.sleep(self.config.generic_poll_sec)

        raise TrafficClientException('End-to-end connectivity cannot be ensured')

    def ensure_arp_successful(self):
        if not self.gen.resolve_arp():
            raise TrafficClientException('ARP cannot be resolved')

    def set_traffic(self, frame_size, bidirectional):
        self.run_config['bidirectional'] = bidirectional
        self.run_config['l2frame_size'] = frame_size
        self.run_config['rates'] = [self.get_per_direction_rate()]
        if bidirectional:
            self.run_config['rates'].append(self.get_per_direction_rate())
        else:
            unidir_reverse_pps = int(self.config.unidir_reverse_traffic_pps)
            if unidir_reverse_pps > 0:
                self.run_config['rates'].append({'rate_pps': str(unidir_reverse_pps)})

        self.gen.clear_streamblock()
        self.gen.create_traffic(frame_size, self.run_config['rates'], bidirectional, latency=True)

    def modify_load(self, load):
        self.current_total_rate = {'rate_percent': str(load)}
        rate_per_direction = self.get_per_direction_rate()

        self.gen.modify_rate(rate_per_direction, False)
        self.run_config['rates'][0] = rate_per_direction
        if self.run_config['bidirectional']:
            self.gen.modify_rate(rate_per_direction, True)
            self.run_config['rates'][1] = rate_per_direction

    def get_ndr_and_pdr(self):
        dst = 'Bidirectional' if self.run_config['bidirectional'] else 'Unidirectional'
        targets = {}
        if self.config.ndr_run:
            LOG.info('*** Searching NDR for %s (%s)...', self.run_config['l2frame_size'], dst)
            targets['ndr'] = self.config.measurement.NDR
        if self.config.pdr_run:
            LOG.info('*** Searching PDR for %s (%s)...', self.run_config['l2frame_size'], dst)
            targets['pdr'] = self.config.measurement.PDR

        self.run_config['start_time'] = time.time()
        self.interval_collector = IntervalCollector(self.run_config['start_time'])
        self.interval_collector.attach_notifier(self.notifier)
        self.iteration_collector = IterationCollector(self.run_config['start_time'])
        results = {}
        self.__range_search(0.0, 200.0, targets, results)

        results['iteration_stats'] = {
            'ndr_pdr': self.iteration_collector.get()
        }

        if self.config.ndr_run:
            LOG.info('NDR load: %s', results['ndr']['rate_percent'])
            results['ndr']['time_taken_sec'] = \
                results['ndr']['timestamp_sec'] - self.run_config['start_time']
            if self.config.pdr_run:
                LOG.info('PDR load: %s', results['pdr']['rate_percent'])
                results['pdr']['time_taken_sec'] = \
                    results['pdr']['timestamp_sec'] - results['ndr']['timestamp_sec']
        else:
            LOG.info('PDR load: %s', results['pdr']['rate_percent'])
            results['pdr']['time_taken_sec'] = \
                results['pdr']['timestamp_sec'] - self.run_config['start_time']
        return results

    def __get_dropped_rate(self, result):
        dropped_pkts = result['rx']['dropped_pkts']
        total_pkts = result['tx']['total_pkts']
        if not total_pkts:
            return float('inf')
        else:
            return float(dropped_pkts) / total_pkts * 100

    def get_stats(self):
        stats = self.gen.get_stats()
        retDict = {'total_tx_rate': stats['total_tx_rate']}
        for port in self.PORTS:
            retDict[port] = {'tx': {}, 'rx': {}}

        tx_keys = ['total_pkts', 'total_pkt_bytes', 'pkt_rate', 'pkt_bit_rate']
        rx_keys = tx_keys + ['dropped_pkts']

        for port in self.PORTS:
            for key in tx_keys:
                retDict[port]['tx'][key] = int(stats[port]['tx'][key])
            for key in rx_keys:
                try:
                    retDict[port]['rx'][key] = int(stats[port]['rx'][key])
                except ValueError:
                    retDict[port]['rx'][key] = 0
            retDict[port]['rx']['avg_delay_usec'] = float(stats[port]['rx']['avg_delay_usec'])
            retDict[port]['rx']['min_delay_usec'] = float(stats[port]['rx']['min_delay_usec'])
            retDict[port]['rx']['max_delay_usec'] = float(stats[port]['rx']['max_delay_usec'])
            retDict[port]['drop_rate_percent'] = self.__get_dropped_rate(retDict[port])

        ports = sorted(retDict.keys())
        if self.run_config['bidirectional']:
            retDict['overall'] = {'tx': {}, 'rx': {}}
            for key in tx_keys:
                retDict['overall']['tx'][key] = \
                    retDict[ports[0]]['tx'][key] + retDict[ports[1]]['tx'][key]
            for key in rx_keys:
                retDict['overall']['rx'][key] = \
                    retDict[ports[0]]['rx'][key] + retDict[ports[1]]['rx'][key]
            total_pkts = [retDict[ports[0]]['rx']['total_pkts'],
                          retDict[ports[1]]['rx']['total_pkts']]
            avg_delays = [retDict[ports[0]]['rx']['avg_delay_usec'],
                          retDict[ports[1]]['rx']['avg_delay_usec']]
            max_delays = [retDict[ports[0]]['rx']['max_delay_usec'],
                          retDict[ports[1]]['rx']['max_delay_usec']]
            min_delays = [retDict[ports[0]]['rx']['min_delay_usec'],
                          retDict[ports[1]]['rx']['min_delay_usec']]
            retDict['overall']['rx']['avg_delay_usec'] = utils.weighted_avg(total_pkts, avg_delays)
            retDict['overall']['rx']['min_delay_usec'] = min(min_delays)
            retDict['overall']['rx']['max_delay_usec'] = max(max_delays)
            for key in ['pkt_bit_rate', 'pkt_rate']:
                for dirc in ['tx', 'rx']:
                    retDict['overall'][dirc][key] /= 2.0
        else:
            retDict['overall'] = retDict[ports[0]]
        retDict['overall']['drop_rate_percent'] = self.__get_dropped_rate(retDict['overall'])
        return retDict

    def __convert_rates(self, rate):
        return utils.convert_rates(self.run_config['l2frame_size'],
                                   rate,
                                   self.config.generator_config.intf_speed)

    def __ndr_pdr_found(self, tag, load):
        rates = self.__convert_rates({'rate_percent': load})
        self.iteration_collector.add_ndr_pdr(tag, rates['rate_pps'])
        last_stats = self.iteration_collector.peek()
        self.interval_collector.add_ndr_pdr(tag, last_stats)

    def __format_output_stats(self, stats):
        for key in (self.PORTS + ['overall']):
            interface = stats[key]
            stats[key] = {
                'tx_pkts': interface['tx']['total_pkts'],
                'rx_pkts': interface['rx']['total_pkts'],
                'drop_percentage': interface['drop_rate_percent'],
                'drop_pct': interface['rx']['dropped_pkts'],
                'avg_delay_usec': interface['rx']['avg_delay_usec'],
                'max_delay_usec': interface['rx']['max_delay_usec'],
                'min_delay_usec': interface['rx']['min_delay_usec'],
            }

        return stats

    def __targets_found(self, rate, targets, results):
        for tag, target in targets.iteritems():
            LOG.info('Found {} ({}) load: {}'.format(tag, target, rate))
            self.__ndr_pdr_found(tag, rate)
            results[tag]['timestamp_sec'] = time.time()

    def __range_search(self, left, right, targets, results):
        '''Perform a binary search for a list of targets inside a [left..right] range or rate

        left    the left side of the range to search as a % the line rate (100 = 100% line rate)
                indicating the rate to send on each interface
        right   the right side of the range to search as a % of line rate
                indicating the rate to send on each interface
        targets a dict of drop rates to search (0.1 = 0.1%), indexed by the DR name or "tag" ('ndr', 'pdr')
        results a dict to store results
        '''
        if len(targets) == 0:
            return
        LOG.info('Range search [{} .. {}] targets: {}'.format(left, right, targets))

        # Terminate search when gap is less than load epsilon
        if right - left < self.config.measurement.load_epsilon:
            self.__targets_found(left, targets, results)
            return

        # Obtain the average drop rate in for middle load
        middle = (left + right) / 2.0
        stats, rates = self.__run_search_iteration(middle)

        # Split target dicts based on the avg drop rate
        left_targets = {}
        right_targets = {}
        for tag, target in targets.iteritems():
            if stats['overall']['drop_rate_percent'] <= target:
                # record the best possible rate found for this target
                results[tag] = rates
                results[tag].update({
                    'load_percent_per_direction': middle,
                    'stats': self.__format_output_stats(dict(stats)),
                    'timestamp_sec': None
                })
                right_targets[tag] = target
            else:
                left_targets[tag] = target

        # search lower half
        self.__range_search(left, middle, left_targets, results)

        # search upper half only if the upper rate does not exceed
        # 100%, this only happens when the first search at 100%
        # yields a DR that is < target DR
        if middle >= 100:
            self.__targets_found(100, right_targets, results)
        else:
            self.__range_search(middle, right, right_targets, results)

    def __run_search_iteration(self, rate):
        # set load
        self.modify_load(rate)

        # poll interval stats and collect them
        for stats in self.run_traffic():
            self.interval_collector.add(stats)
            time_elapsed_ratio = self.runner.time_elapsed() / self.run_config['duration_sec']
            if time_elapsed_ratio >= 1:
                self.cancel_traffic()
        self.interval_collector.reset()

        # get stats from the run
        stats = self.runner.client.get_stats()
        current_traffic_config = self.get_traffic_config()
        warning = self.compare_tx_rates(current_traffic_config['direction-total']['rate_pps'],
                                        stats['total_tx_rate'])
        if warning is not None:
            stats['warning'] = warning

        # save reliable stats from whole iteration
        self.iteration_collector.add(stats, current_traffic_config['direction-total']['rate_pps'])
        LOG.info('Average drop rate: {}'.format(stats['overall']['drop_rate_percent']))

        return stats, current_traffic_config['direction-total']

    @staticmethod
    def log_stats(stats):
        report = {
            'datetime': str(datetime.now()),
            'tx_packets': stats['overall']['tx']['total_pkts'],
            'rx_packets': stats['overall']['rx']['total_pkts'],
            'drop_packets': stats['overall']['rx']['dropped_pkts'],
            'drop_rate_percent': stats['overall']['drop_rate_percent']
        }
        LOG.info('TX: %(tx_packets)d; '
                 'RX: %(rx_packets)d; '
                 'Dropped: %(drop_packets)d; '
                 'Drop rate: %(drop_rate_percent).4f%%',
                 report)

    def run_traffic(self):
        stats = self.runner.run()
        while self.runner.is_running:
            self.log_stats(stats)
            yield stats
            stats = self.runner.poll_stats()
            if stats is None:
                return
        self.log_stats(stats)
        LOG.info('Drop rate: {}'.format(stats['overall']['drop_rate_percent']))
        yield stats

    def cancel_traffic(self):
        self.runner.stop()

    def get_interface(self, port_index):
        port = self.gen.port_handle[port_index]
        tx, rx = 0, 0
        if not self.config.no_traffic:
            stats = self.get_stats()
            if port in stats:
                tx, rx = int(stats[port]['tx']['total_pkts']), int(stats[port]['rx']['total_pkts'])
        return Interface('traffic-generator', self.tool.lower(), tx, rx)

    def get_traffic_config(self):
        config = {}
        load_total = 0.0
        bps_total = 0.0
        pps_total = 0.0
        for idx, rate in enumerate(self.run_config['rates']):
            key = 'direction-forward' if idx == 0 else 'direction-reverse'
            config[key] = {
                'l2frame_size': self.run_config['l2frame_size'],
                'duration_sec': self.run_config['duration_sec']
            }
            config[key].update(rate)
            config[key].update(self.__convert_rates(rate))
            load_total += float(config[key]['rate_percent'])
            bps_total += float(config[key]['rate_bps'])
            pps_total += float(config[key]['rate_pps'])
        config['direction-total'] = dict(config['direction-forward'])
        config['direction-total'].update({
            'rate_percent': load_total,
            'rate_pps': pps_total,
            'rate_bps': bps_total
        })

        return config

    def get_run_config(self, results):
        """Returns configuration which was used for the last run."""
        r = {}
        for idx, key in enumerate(["direction-forward", "direction-reverse"]):
            tx_rate = results["stats"][idx]["tx"]["total_pkts"] / self.config.duration_sec
            rx_rate = results["stats"][idx]["rx"]["total_pkts"] / self.config.duration_sec
            r[key] = {
                "orig": self.__convert_rates(self.run_config['rates'][idx]),
                "tx": self.__convert_rates({'rate_pps': tx_rate}),
                "rx": self.__convert_rates({'rate_pps': rx_rate})
            }

        total = {}
        for direction in ['orig', 'tx', 'rx']:
            total[direction] = {}
            for unit in ['rate_percent', 'rate_bps', 'rate_pps']:
                total[direction][unit] = sum(map(lambda x: float(x[direction][unit]), r.values()))

        r['direction-total'] = total
        return r

    @staticmethod
    def compare_tx_rates(required, actual):
        threshold = 0.9
        are_different = False
        try:
            if float(actual) / required < threshold:
                are_different = True
        except ZeroDivisionError:
            are_different = True

        if are_different:
            msg = "WARNING: There is a significant difference between requested TX rate ({r}) " \
                  "and actual TX rate ({a}). The traffic generator may not have sufficient CPU " \
                  "to achieve the requested TX rate.".format(r=required, a=actual)
            LOG.info(msg)
            return msg

        return None

    def get_per_direction_rate(self):
        divisor = 2 if self.run_config['bidirectional'] else 1
        if 'rate_percent' in self.current_total_rate:
            # don't split rate if it's percentage
            divisor = 1

        return utils.divide_rate(self.current_total_rate, divisor)

    def close(self):
        try:
            self.gen.stop_traffic()
        except Exception:
            pass
        self.gen.clear_stats()
        self.gen.cleanup()
