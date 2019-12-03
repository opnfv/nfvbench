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
import time

from .log import LOG
from .packet_stats import PacketPathStatsManager
from .stats_collector import IntervalCollector


class StatsManager(object):
    """A class to collect detailed stats and handle fixed rate runs for all chain types."""

    def __init__(self, chain_runner):
        self.chain_runner = chain_runner
        self.config = chain_runner.config
        self.traffic_client = chain_runner.traffic_client
        self.specs = chain_runner.specs
        self.notifier = chain_runner.notifier
        self.interval_collector = None
        self.factory = chain_runner.factory
        # create a packet path stats manager for fixed rate runs only
        if self.config.single_run:
            pps_list = []
            self.traffic_client.insert_interface_stats(pps_list)
            self.pps_mgr = PacketPathStatsManager(pps_list)
        else:
            self.pps_mgr = None
        self.worker = None

    def create_worker(self):
        """Create a worker to fetch custom data.

        This is done late as we need to know the dest MAC for all VNFs, which can happen
        as late as after ARP discovery.
        """
        if not self.worker and self.specs.openstack:
            WORKER_CLASS = self.factory.get_chain_worker(self.specs.openstack.encaps,
                                                         self.config.service_chain)
            self.worker = WORKER_CLASS(self)

    def _generate_traffic(self):
        if self.config.no_traffic:
            return {}

        self.interval_collector = IntervalCollector(time.time())
        self.interval_collector.attach_notifier(self.notifier)
        LOG.info('Starting to generate traffic...')
        stats = {}
        for stats in self.traffic_client.run_traffic():
            self.interval_collector.add(stats)

        LOG.info('...traffic generating ended.')
        return stats

    def get_stats(self):
        return self.interval_collector.get() if self.interval_collector else []

    def get_version(self):
        return self.worker.get_version() if self.worker else {}

    def _update_interface_stats(self, diff=False):
        """Update interface stats for both the traffic generator and the worker."""
        self.traffic_client.update_interface_stats(diff)
        if self.worker:
            self.worker.update_interface_stats(diff)

    def run_fixed_rate(self):
        """Run a fixed rate and analyze results."""
        # Baseline the packet path stats
        self._update_interface_stats()

        in_flight_stats = self._generate_traffic()
        result = {
            'stats': in_flight_stats
        }
        # New analysis code with packet path stats
        # Diff all interface stats and return packet path stats analysis
        # Diff the packet path stats
        self._update_interface_stats(diff=True)
        result['packet_path_stats'] = self.pps_mgr.get_results()
        return result

    def get_compute_nodes_bios(self):
        return self.worker.get_compute_nodes_bios() if self.worker else {}

    def close(self):
        if self.worker:
            self.worker.close()
