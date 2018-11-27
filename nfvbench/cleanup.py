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

    def get_cleaner_code(self):
        return "instances"

    def clean_needed(self, clean_options):
        if clean_options is None:
            return True
        code = self.get_cleaner_code()
        return code[0] in clean_options

    def clean(self, clean_options):
        if self.clean_needed(clean_options):
            if self.servers:
                for server in self.servers:
                    try:
                        LOG.info('Deleting instance %s...', server.name)
                        self.nova_client.servers.delete(server.id)
                    except Exception:
                        LOG.exception("Instance %s deletion failed", server.name)
                LOG.info('    Waiting for %d instances to be fully deleted...', len(self.servers))
                retry_count = 15 + len(self.servers) * 5
                while True:
                    retry_count -= 1
                    self.servers = [server for server in self.servers if
                                    self.instance_exists(server)]
                    if not self.servers:
                        break

                    if retry_count:
                        LOG.info('    %d yet to be deleted by Nova, retries left=%d...',
                                 len(self.servers), retry_count)
                        time.sleep(2)
                    else:
                        LOG.warning(
                            '    instance deletion verification time-out: %d still not deleted',
                            len(self.servers))
                        break


class NetworkCleaner(object):
    """A cleaner for network resources."""

    def __init__(self, neutron_client, network_name_prefixes):
        self.neutron_client = neutron_client
        LOG.info('Discovering networks...')
        all_networks = self.neutron_client.list_networks()['networks']
        self.networks = []
        net_ids = []
        for net in all_networks:
            netname = net['name']
            for prefix in network_name_prefixes:
                if netname.startswith(prefix):
                    self.networks.append(net)
                    net_ids.append(net['id'])
                    break
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

    def get_cleaner_code(self):
        return "networks and ports"

    def clean_needed(self, clean_options):
        if clean_options is None:
            return True
        code = self.get_cleaner_code()
        return code[0] in clean_options

    def clean(self, clean_options):
        if self.clean_needed(clean_options):
            for port in self.ports:
                LOG.info("Deleting port %s...", port['id'])
                try:
                    self.neutron_client.delete_port(port['id'])
                except Exception:
                    LOG.exception("Port deletion failed")

            # associated subnets are automatically deleted by neutron
            for net in self.networks:
                LOG.info("Deleting network %s...", net['name'])
                try:
                    self.neutron_client.delete_network(net['id'])
                except Exception:
                    LOG.exception("Network deletion failed")


class RouterCleaner(object):
    """A cleaner for router resources."""

    def __init__(self, neutron_client, router_names):
        self.neutron_client = neutron_client
        LOG.info('Discovering routers...')
        all_routers = self.neutron_client.list_routers()['routers']
        self.routers = []
        self.ports = []
        self.routes = []
        rtr_ids = []
        for rtr in all_routers:
            rtrname = rtr['name']
            for name in router_names:
                if rtrname == name:
                    self.routers.append(rtr)
                    rtr_ids.append(rtr['id'])

                    LOG.info('Discovering router routes for router %s...', rtr['name'])
                    all_routes = rtr['routes']
                    for route in all_routes:
                        LOG.info("destination: %s, nexthop: %s", route['destination'],
                                 route['nexthop'])

                    LOG.info('Discovering router ports for router %s...', rtr['name'])
                    self.ports.extend(self.neutron_client.list_ports(device_id=rtr['id'])['ports'])
                    break

    def get_resource_list(self):
        res_list = [["Router", rtr['name'], rtr['id']] for rtr in self.routers]
        return res_list

    def get_cleaner_code(self):
        return "router"

    def clean_needed(self, clean_options):
        if clean_options is None:
            return True
        code = self.get_cleaner_code()
        return code[0] in clean_options

    def clean(self, clean_options):
        if self.clean_needed(clean_options):
            # associated routes needs to be deleted before deleting routers
            for rtr in self.routers:
                LOG.info("Deleting routes for %s...", rtr['name'])
                try:
                    body = {
                        'router': {
                            'routes': []
                        }
                    }
                    self.neutron_client.update_router(rtr['id'], body)
                except Exception:
                    LOG.exception("Router routes deletion failed")
                LOG.info("Deleting ports for %s...", rtr['name'])
                try:
                    for port in self.ports:
                        body = {
                            'port_id': port['id']
                        }
                        self.neutron_client.remove_interface_router(rtr['id'], body)
                except Exception:
                    LOG.exception("Router ports deletion failed")
                LOG.info("Deleting router %s...", rtr['name'])
                try:
                    self.neutron_client.delete_router(rtr['id'])
                except Exception:
                    LOG.exception("Router deletion failed")


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

    def get_cleaner_code(self):
        return "flavor"

    def clean_needed(self, clean_options):
        if clean_options is None:
            return True
        code = self.get_cleaner_code()
        return code[0] in clean_options

    def clean(self, clean_options):
        if self.clean_needed(clean_options):
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
        network_names.extend([inet['name'] for inet in config.edge_networks.values()])
        router_names = [rtr['router_name'] for rtr in config.edge_networks.values()]
        # add idle networks as well
        if config.idle_networks.name:
            network_names.append(config.idle_networks.name)
        self.cleaners = [ComputeCleaner(self.nova_client, config.loop_vm_name),
                         FlavorCleaner(self.nova_client, config.flavor_type),
                         NetworkCleaner(self.neutron_client, network_names),
                         RouterCleaner(self.neutron_client, router_names)]

    def show_resources(self):
        """Show all NFVbench resources."""
        table = [["Type", "Name", "UUID"]]
        for cleaner in self.cleaners:
            res_list = cleaner.get_resource_list()
            if res_list:
                table.extend(res_list)
        count = len(table) - 1
        if count:
            LOG.info('Discovered %d NFVbench resources:\n%s', count,
                     tabulate(table, headers="firstrow", tablefmt="psql"))
        else:
            LOG.info('No matching NFVbench resources found')
        return count

    def clean(self, prompt):
        """Clean all resources."""
        LOG.info("NFVbench will delete resources shown...")
        clean_options = None
        if prompt:
            answer = raw_input("Do you want to delete all ressources? (y/n) ")
            if answer.lower() != 'y':
                print "What kind of resources do you want to delete?"
                all_option = ""
                all_option_codes = []
                for cleaner in self.cleaners:
                    code = cleaner.get_cleaner_code()
                    print "%s: %s" % (code[0], code)
                    all_option += code[0]
                    all_option_codes.append(code)
                print "a: all resources - a shortcut for '%s'" % all_option
                all_option_codes.append("all resources")
                print "q: quit"
                answer_res = raw_input(":").lower()
                # Check only first character because answer_res can be "flavor" and it is != all
                if answer_res[0] == "a":
                    clean_options = all_option
                elif answer_res[0] != 'q':
                    # if user write complete code instead of shortcuts
                    # Get only first character of clean code to avoid false clean request
                    # i.e "networks and ports" and "router" have 1 letter in common and router clean
                    # will be called even if user ask for networks and ports
                    if answer_res in all_option_codes:
                        clean_options = answer_res[0]
                    else:
                        clean_options = answer_res
                else:
                    LOG.info("Exiting without deleting any resource")
                    sys.exit(0)
        for cleaner in self.cleaners:
            cleaner.clean(clean_options)
