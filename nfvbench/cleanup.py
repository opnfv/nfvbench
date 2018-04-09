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

import sys
import time

from neutronclient.neutron import client as nclient
from novaclient.client import Client
from novaclient.exceptions import NotFound
from tabulate import tabulate

import credentials as credentials
from log import LOG

class ComputeCleaner(object):
    """A cleaner for compute resources."""

    def __init__(self, nova_client, instance_prefix):
        self.nova_client = nova_client
        LOG.info('Discovering instances %s...', instance_prefix)
        all_servers = self.nova_client.servers.list()
        self.servers = [server for server in all_servers
                        if server.name.startswith(instance_prefix)]

    def instance_exists(self, server):
        try:
            self.nova_client.servers.get(server.id)
        except NotFound:
            return False
        return True

    def get_resource_list(self):
        return [["Instance", server.name, server.id] for server in self.servers]

    def clean(self):
        if self.servers:
            for server in self.servers:
                try:
                    LOG.info('Deleting instance %s...', server.name)
                    self.nova_client.servers.delete(server.id)
                except Exception:
                    LOG.exception("Instance %s deletion failed", server.name)
            LOG.info('    Waiting for %d instances to be fully deleted...', len(self.servers))
            retry_count = 5 + len(self.servers) * 2
            while True:
                retry_count -= 1
                self.servers = [server for server in self.servers if self.instance_exists(server)]
                if not self.servers:
                    break

                if retry_count:
                    LOG.info('    %d yet to be deleted by Nova, retries left=%d...',
                             len(self.servers), retry_count)
                    time.sleep(2)
                else:
                    LOG.warning('    instance deletion verification timed out: %d not removed',
                                len(self.servers))
                    break


class NetworkCleaner(object):
    """A cleaner for network resources."""

    def __init__(self, neutron_client, network_names):
        self.neutron_client = neutron_client
        LOG.info('Discovering networks...')
        all_networks = self.neutron_client.list_networks()['networks']
        self.networks = []
        for net in all_networks:
            try:
                network_names.remove(net['name'])
                self.networks.append(net)
            except ValueError:
                pass
            if not network_names:
                break
        net_ids = [net['id'] for net in self.networks]
        if net_ids:
            LOG.info('Discovering ports...')
            all_ports = self.neutron_client.list_ports()['ports']
            self.ports = [port for port in all_ports if port['network_id'] in net_ids]
        else:
            self.ports = []

    def get_resource_list(self):
        res_list = [["Network", net['name'], net['id']] for net in self.networks]
        res_list.extend([["Port", port['name'], port['id']] for port in self.ports])
        return res_list

    def clean(self):
        for port in self.ports:
            LOG.info("Deleting port %s...", port['id'])
            try:
                self.neutron_client.delete_port(port['id'])
            except Exception:
                LOG.exception("Port deletion failed")

        for net in self.networks:
            LOG.info("Deleting network %s...", net['name'])
            try:
                self.neutron_client.delete_network(net['id'])
            except Exception:
                LOG.exception("Network deletion failed")

class FlavorCleaner(object):
    """Cleaner for NFVbench flavor."""

    def __init__(self, nova_client, name):
        self.name = name
        LOG.info('Discovering flavor %s...', name)
        try:
            self.flavor = nova_client.flavors.find(name=name)
        except NotFound:
            self.flavor = None

    def get_resource_list(self):
        if self.flavor:
            return [['Flavor', self.name, self.flavor.id]]
        return None

    def clean(self):
        if self.flavor:
            LOG.info("Deleting flavor %s...", self.flavor.name)
            try:
                self.flavor.delete()
            except Exception:
                LOG.exception("Flavor deletion failed")

class Cleaner(object):
    """Cleaner for all NFVbench resources."""

    def __init__(self, config):
        cred = credentials.Credentials(config.openrc_file, None, False)
        session = cred.get_session()
        self.neutron_client = nclient.Client('2.0', session=session)
        self.nova_client = Client(2, session=session)
        network_names = [inet['name'] for inet in config.internal_networks.values()]
        self.cleaners = [ComputeCleaner(self.nova_client, config.loop_vm_name),
                         FlavorCleaner(self.nova_client, config.flavor_type),
                         NetworkCleaner(self.neutron_client, network_names)]

    def show_resources(self):
        """Show all NFVbench resources."""
        table = [["Type", "Name", "UUID"]]
        for cleaner in self.cleaners:
            res_list = cleaner.get_resource_list()
            if res_list:
                table.extend(res_list)
        count = len(table) - 1
        if count:
            LOG.info('Discovered %d NFVbench resources:', count)
            print tabulate(table, headers="firstrow", tablefmt="psql")
        else:
            LOG.info('No matching NFVbench resources found')
        return count

    def clean(self, prompt):
        """Clean all resources."""
        LOG.info("NFVbench will delete all resources shown...")
        if prompt:
            answer = raw_input("Are you sure? (y/n) ")
            if answer.lower() != 'y':
                LOG.info("Exiting without deleting any resource")
                sys.exit(0)
        for cleaner in self.cleaners:
            cleaner.clean()
