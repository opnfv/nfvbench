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

from .chaining import ChainManager
from .log import LOG
from .specs import ChainType
from .stats_manager import StatsManager
from .traffic_client import TrafficClient


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
        # or EXT+ARP+VLAN (because dest MAC will be discovered by TRex ARP)
        # Note that in the case of EXT+ARP+VxLAN, the dest MACs need to be loaded
        # because ARP only operates on the dest VTEP IP not on the VM dest MAC
        if not config.l2_loopback and \
                (config.service_chain != ChainType.EXT or config.no_arp or config.vxlan):
            gen_config.set_dest_macs(0, self.chain_manager.get_dest_macs(0))
            gen_config.set_dest_macs(1, self.chain_manager.get_dest_macs(1))

        if config.vxlan:
            # VXLAN is discovered from the networks
            vtep_vlan = gen_config.gen_config.vtep_vlan
            src_vteps = gen_config.gen_config.src_vteps
            dst_vtep = gen_config.gen_config.dst_vtep
            gen_config.set_vxlans(0, self.chain_manager.get_chain_vxlans(0))
            gen_config.set_vxlans(1, self.chain_manager.get_chain_vxlans(1))
            gen_config.set_vtep_vlan(0, vtep_vlan)
            gen_config.set_vtep_vlan(1, vtep_vlan)
            # Configuring source an remote VTEPs on TREx interfaces
            gen_config.set_vxlan_endpoints(0, src_vteps[0], dst_vtep)
            gen_config.set_vxlan_endpoints(1, src_vteps[1], dst_vtep)
            self.config['vxlan_gen_config'] = gen_config

        # get an instance of the stats manager
        self.stats_manager = StatsManager(self)
        LOG.info('ChainRunner initialized')

    def __setup_traffic(self):
        self.traffic_client.setup()
        if not self.config.no_traffic:
            # ARP is needed for EXT chain or VxLAN overlay unless disabled explicitly
            if (self.config.service_chain == ChainType.EXT or
                    self.config.vxlan or self.config.l3_router) and not self.config.no_arp:
                self.traffic_client.ensure_arp_successful()
            self.traffic_client.ensure_end_to_end()

    def __get_result_per_frame_size(self, frame_size, bidirectional):
        traffic_result = {
            frame_size: {}
        }
        result = {}
        if not self.config.no_traffic:
            self.traffic_client.set_traffic(frame_size, bidirectional)

            if self.config.single_run:
                result = self.stats_manager.run_fixed_rate()
            else:
                results = self.traffic_client.get_ndr_and_pdr()

                for dr in ['pdr', 'ndr']:
                    if dr in results:
                        traffic_result[frame_size][dr] = results[dr]
                        if 'warning' in results[dr]['stats'] and results[dr]['stats']['warning']:
                            traffic_result['warning'] = results[dr]['stats']['warning']
                traffic_result[frame_size]['iteration_stats'] = results['iteration_stats']

            if self.config.single_run:
                result['run_config'] = self.traffic_client.get_run_config(result)
                required = result['run_config']['direction-total']['orig']['rate_pps']
                actual = result['stats']['total_tx_rate']
                warning = self.traffic_client.compare_tx_rates(required, actual)
                if warning is not None:
                    result['run_config']['warning'] = warning

        traffic_result[frame_size].update(result)
        return traffic_result

    def __get_chain_result(self):
        result = OrderedDict()
        for fs in self.config.frame_sizes:
            result.update(self.__get_result_per_frame_size(fs,
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
        self.stats_manager.create_worker()
        if self.config.vxlan:
            # Configure vxlan tunnels
            self.stats_manager.worker.config_interfaces()

        self.__setup_traffic()

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
