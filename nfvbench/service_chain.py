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

from chain_managers import StageManager
from collections import OrderedDict
from log import LOG
from specs import ChainType
import time


class ServiceChain(object):

    def __init__(self, config, clients, cred, specs, factory, notifier=None):
        self.config = config
        self.clients = clients
        self.cred = cred
        self.specs = specs
        self.factory = factory
        self.notifier = notifier
        self.chain_name = self.config.service_chain
        self.vlans = None
        self.stage_manager = None
        self.stats_manager = None
        LOG.info('ServiceChain initialized.')

    def __set_helpers(self):
        self.stage_manager = StageManager(self.config, self.cred, self.factory)
        self.clients['vm'] = self.stage_manager
        self.vlans = self.stage_manager.get_vlans()

        STATS_CLASS = self.factory.get_stats_class(self.config.service_chain)
        self.stats_manager = STATS_CLASS(self.config,
                                         self.clients,
                                         self.specs,
                                         self.factory,
                                         self.vlans,
                                         self.notifier)

    def __set_vlan_tags(self):
        if self.config.vlan_tagging:
            # override with user-specified vlans if configured
            vlans = self.config.vlans if self.config.vlans else self.vlans[:2]
            for vlan, device in zip(vlans, self.config.generator_config.devices):
                self.stats_manager.set_vlan_tag(device, vlan)

    def __get_result_per_frame_size(self, frame_size, bidirectional):
        start_time = time.time()
        traffic_result = {
            frame_size: {}
        }
        result = {}
        if not self.config.no_traffic:
            self.clients['traffic'].set_traffic(frame_size, bidirectional)

            if self.config.single_run:
                result = self.stats_manager.run()
            else:
                results = self.clients['traffic'].get_ndr_and_pdr()

                for dr in ['pdr', 'ndr']:
                    if dr in results:
                        traffic_result[frame_size][dr] = results[dr]
                        if 'warning' in results[dr]['stats'] and results[dr]['stats']['warning']:
                            traffic_result['warning'] = results[dr]['stats']['warning']
                traffic_result[frame_size]['iteration_stats'] = results['iteration_stats']

            result['analysis_duration_sec'] = time.time() - start_time
            if self.config.single_run:
                result['run_config'] = self.clients['traffic'].get_run_config(result)
                required = result['run_config']['direction-total']['orig']['rate_pps']
                actual = result['stats']['total_tx_rate']
                warning = self.clients['traffic'].compare_tx_rates(required, actual)
                if warning is not None:
                    result['run_config']['warning'] = warning

        traffic_result[frame_size].update(result)
        return traffic_result

    def __get_chain_result(self):
        result = OrderedDict()
        for fs in self.config.frame_sizes:
            result.update(self.__get_result_per_frame_size(fs, self.config.traffic.bidirectional))

        chain_result = {
            'flow_count': self.config.flow_count,
            'service_chain_count': self.config.service_chain_count,
            'bidirectional': self.config.traffic.bidirectional,
            'profile': self.config.traffic.profile,
            'compute_nodes': self.stats_manager.get_compute_nodes_bios(),
            'result': result
        }

        return chain_result

    def __setup_traffic(self):
        self.clients['traffic'].setup()
        if not self.config.no_traffic:
            if self.config.service_chain == ChainType.EXT and not self.config.no_arp:
                self.clients['traffic'].ensure_arp_successful()
            self.clients['traffic'].ensure_end_to_end()

    def run(self):
        LOG.info('Starting {} chain...'.format(self.chain_name))
        LOG.info('Dry run: {}'.format(self.config.no_traffic))
        results = {}

        self.__set_helpers()
        self.__set_vlan_tags()
        self.stage_manager.set_vm_macs()
        self.__setup_traffic()
        results[self.chain_name] = {'result': self.__get_chain_result()}

        if self.config.service_chain == ChainType.PVVP:
            results[self.chain_name]['mode'] = 'inter-node' \
                if self.config.inter_node else 'intra-node'

        LOG.info("Service chain '{}' run completed.".format(self.chain_name))
        return results

    def get_version(self):
        return self.stats_manager.get_version()

    def close(self):
        self.stage_manager.close()
        self.stats_manager.close()
