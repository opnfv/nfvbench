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

from log import LOG
from service_chain import ServiceChain
import traceback
from traffic_client import TrafficClient


class ChainRunner(object):
    """Run selected chain, collect results and analyse them."""

    def __init__(self, config, clients, cred, specs, factory, notifier=None):
        self.config = config
        self.clients = clients
        self.specs = specs
        self.factory = factory
        self.chain_name = self.config.service_chain

        try:
            TORClass = factory.get_tor_class(self.config.tor.type, self.config.no_tor_access)
        except AttributeError:
            raise Exception("Requested TOR class '{}' was not found.".format(self.config.tor.type))

        self.clients['tor'] = TORClass(self.config.tor.switches)
        self.clients['traffic'] = TrafficClient(config, notifier)
        self.chain = ServiceChain(config, clients, cred, specs, factory, notifier)

        LOG.info('ChainRunner initialized.')

    def run(self):
        """
        Run a chain, collect and analyse results.

        :return: dictionary
        """
        self.clients['traffic'].start_traffic_generator()
        self.clients['traffic'].set_macs()

        return self.chain.run()

    def close(self):
        try:
            if not self.config.no_cleanup:
                LOG.info('Cleaning up...')
            else:
                LOG.info('Clean up skipped.')

            for client in ['traffic', 'tor']:
                try:
                    self.clients[client].close()
                except Exception as e:
                    traceback.print_exc()
                    LOG.error(e)

            self.chain.close()
        except Exception:
            traceback.print_exc()
            LOG.error('Cleanup not finished.')

    def get_version(self):
        versions = {
            'Traffic Generator': self.clients['traffic'].get_version(),
            'TOR': self.clients['tor'].get_version(),
        }

        versions.update(self.chain.get_version())

        return versions
