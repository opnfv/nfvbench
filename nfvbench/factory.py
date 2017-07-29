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

from chain_clients import EXTStageClient
from chain_clients import PVPStageClient
from chain_clients import PVVPStageClient
from chain_managers import EXTStatsManager
from chain_managers import PVPStatsManager
from chain_managers import PVVPStatsManager
import chain_workers as workers
from config_plugin import ConfigPlugin
from specs import ChainType
import tor_client


class BasicFactory(object):

    chain_classes = [ChainType.EXT, ChainType.PVP, ChainType.PVVP]

    chain_stats_classes = {
        ChainType.EXT: EXTStatsManager,
        ChainType.PVP: PVPStatsManager,
        ChainType.PVVP: PVVPStatsManager,
    }

    stage_clients_classes = {
        ChainType.EXT: EXTStageClient,
        ChainType.PVP: PVPStageClient,
        ChainType.PVVP: PVVPStageClient,
    }

    def get_stats_class(self, service_chain):
        CLASS = self.chain_stats_classes.get(service_chain, None)
        if CLASS is None:
            raise Exception("Service chain '{}' not supported.".format(service_chain))

        return CLASS

    def get_stage_class(self, service_chain):
        CLASS = self.stage_clients_classes.get(service_chain, None)
        if CLASS is None:
            raise Exception("VM Client for chain '{}' not supported.".format(service_chain))

        return CLASS

    def get_chain_worker(self, encaps, service_chain):
        return workers.BasicWorker

    def get_tor_class(self, tor_type, no_tor_access):
        if no_tor_access or not tor_type:
            # if no TOR access is required, use basic no-op client
            tor_type = 'BasicTORClient'

        return getattr(tor_client, tor_type)

    def get_config_plugin_class(self):
        return ConfigPlugin
