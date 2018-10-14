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
"""This module takes care of coordinating a benchmark run between various modules.

The ChainRunner class is in charge of coordinating:
- the chain manager which takes care of staging resources
- traffic generator client which drives the traffic generator
- the stats manager which collects and aggregates stats
"""

from collections import OrderedDict

from chaining import ChainManager
from log import LOG
from specs import ChainType
from stats_manager import StatsManager
from traffic_client import TrafficClient


class ChainRunner(object):
    """Run selected chain, collect results and analyse them."""

    def __init__(self, config, cred, specs, factory, notifier=None):
        """Create a new instance of chain runner.

        Create dependent components
        A new instance is created everytime the nfvbench config may have changed.

        config: the new nfvbench config to use for this run
        cred: openstack credentials (or None if no openstack)
        specs: TBD
        factory:
        notifier:
        """
        self.config = config
        self.cred = cred
        self.specs = specs
        self.factory = factory
        self.notifier = notifier
        self.chain_name = self.config.service_chain

        # get an instance of traffic client
        self.traffic_client = TrafficClient(config, notifier)

        if self.config.no_traffic:
            LOG.info('Dry run: traffic generation is disabled')
        else:
            # Start the traffic generator server
            self.traffic_client.start_traffic_generator()

        # get an instance of a chain manager
        self.chain_manager = ChainManager(self)

        # at this point all resources are setup/discovered
        # we need to program the traffic dest MAC and VLANs
        gen_config = self.traffic_client.generator_config
        if config.vlan_tagging:
            # VLAN is discovered from the networks
            gen_config.set_vlans(0, self.chain_manager.get_chain_vlans(0))
            gen_config.set_vlans(1, self.chain_manager.get_chain_vlans(1))

        # the only case we do not need to set the dest MAC is in the case of
        # l2-loopback (because the traffic gen will default to use the peer MAC)
        # or EXT+ARP (because dest MAC will be discovered by TRex ARP)
        if not config.l2_loopback and (config.service_chain != ChainType.EXT or config.no_arp):
            gen_config.set_dest_macs(0, self.chain_manager.get_dest_macs(0))
            gen_config.set_dest_macs(1, self.chain_manager.get_dest_macs(1))

        # get an instance of the stats manager
        self.stats_manager = StatsManager(self)
        LOG.info('ChainRunner initialized')

    def __setup_traffic(self):
        self.traffic_client.setup()
        if not self.config.no_traffic:
            if self.config.service_chain == ChainType.EXT and not self.config.no_arp:
                self.traffic_client.ensure_arp_successful()
            self.traffic_client.ensure_end_to_end()

    def __get_result_per_frame_size(self, frame_size, actual_frame_size, bidirectional):
        traffic_result = {
            frame_size: {}
        }
        result = {}
        if not self.config.no_traffic:
            self.traffic_client.set_traffic(actual_frame_size, bidirectional)

            if self.config.single_run:
                result = self.stats_manager.run_fixed_rate()
            else:
                results = self.traffic_client.get_ndr_and_pdr()

                for dr in ['pdr', 'ndr']:
                    if dr in results:
                        if frame_size != actual_frame_size:
                            results[dr]['l2frame_size'] = frame_size
                            results[dr]['actual_l2frame_size'] = actual_frame_size
                        traffic_result[frame_size][dr] = results[dr]
                        if 'warning' in results[dr]['stats'] and results[dr]['stats']['warning']:
                            traffic_result['warning'] = results[dr]['stats']['warning']
                traffic_result[frame_size]['iteration_stats'] = results['iteration_stats']

            if self.config.single_run:
                result['run_config'] = self.traffic_client.get_run_config(result)
                required = result['run_config']['direction-total']['orig']['rate_pps']
                actual = result['stats']['total_tx_rate']
                if frame_size != actual_frame_size:
                    result['actual_l2frame_size'] = actual_frame_size
                warning = self.traffic_client.compare_tx_rates(required, actual)
                if warning is not None:
                    result['run_config']['warning'] = warning

        traffic_result[frame_size].update(result)
        return traffic_result

    def __get_chain_result(self):
        result = OrderedDict()
        for fs, actual_fs in zip(self.config.frame_sizes, self.config.actual_frame_sizes):
            result.update(self.__get_result_per_frame_size(fs,
                                                           actual_fs,
                                                           self.config.traffic.bidirectional))
        chain_result = {
            'flow_count': self.config.flow_count,
            'service_chain_count': self.config.service_chain_count,
            'bidirectional': self.config.traffic.bidirectional,
            'profile': self.config.traffic.profile,
            'compute_nodes': self.stats_manager.get_compute_nodes_bios(),
            'result': result
        }
        return chain_result

    def run(self):
        """Run the requested benchmark.

        return: the results of the benchmark as a dict
        """
        results = {}
        if self.config.no_traffic:
            return results

        LOG.info('Starting %dx%s benchmark...', self.config.service_chain_count, self.chain_name)
        self.__setup_traffic()
        # now that the dest MAC for all VNFs is known in all cases, it is time to create
        # workers as they might be needed to extract stats prior to sending traffic
        self.stats_manager.create_worker()

        results[self.chain_name] = {'result': self.__get_chain_result()}

        LOG.info("Service chain '%s' run completed.", self.chain_name)
        return results

    def close(self):
        """Close this instance of chain runner and delete resources if applicable."""
        try:
            if not self.config.no_cleanup:
                LOG.info('Cleaning up...')
                if self.chain_manager:
                    self.chain_manager.delete()
            else:
                LOG.info('Clean up skipped.')
            try:
                self.traffic_client.close()
            except Exception:
                LOG.exception()
            if self.stats_manager:
                self.stats_manager.close()
        except Exception:
            LOG.exception('Cleanup not finished')

    def get_version(self):
        """Retrieve the version of dependent components."""
        versions = {}
        if self.traffic_client:
            versions['Traffic_Generator'] = self.traffic_client.get_version()
        versions.update(self.stats_manager.get_version())
        return versions
