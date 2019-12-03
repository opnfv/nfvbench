#!/usr/bin/env python
# Copyright 2017 Cisco Systems, Inc.  All rights reserved.
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


class BasicWorker(object):

    def __init__(self, stats_manager):
        self.stats_manager = stats_manager
        self.chain_manager = stats_manager.chain_runner.chain_manager
        self.config = stats_manager.config
        self.specs = stats_manager.specs

    def get_compute_nodes_bios(self):
        return {}

    def get_version(self):
        return {}

    def config_interfaces(self):
        return {}

    def close(self):
        pass

    def insert_interface_stats(self, pps_list):
        """Insert interface stats to a list of packet path stats.

        pps_list: a list of packet path stats instances indexed by chain index

        Specialized workers can insert their own interface stats inside each existing packet path
        stats for every chain.
        """

    def update_interface_stats(self, diff=False):
        """Update all interface stats.

        diff: if False, simply refresh the interface stats values with latest values
              if True, diff the interface stats with the latest values
        Make sure that the interface stats inserted in insert_interface_stats() are updated
        with proper values
        """
