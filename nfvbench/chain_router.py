#!/usr/bin/env python
# Copyright 2018 Cisco Systems, Inc.  All rights reserved.
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

# This module takes care of chaining routers
#
"""NFVBENCH CHAIN DISCOVERY/STAGING.

This module takes care of staging/discovering resources that are participating in a
L3 benchmarking session: routers, networks, ports, routes.
If a resource is discovered with the same name, it will be reused.
Otherwise it will be created.

Once created/discovered, instances are checked to be in the active state (ready to pass traffic)
Configuration parameters that will influence how these resources are staged/related:
- openstack or no openstack
- chain type
- number of chains
- number of VNF in each chain (PVP, PVVP)
- SRIOV and middle port SRIOV for port types
- whether networks are shared across chains or not

There is not traffic generation involved in this module.
"""
import time

from netaddr import IPAddress
from netaddr import IPNetwork

from .log import LOG


class ChainException(Exception):
    """Exception while operating the chains."""

class ChainRouter(object):
    """Could be a shared router across all chains or a chain private router."""

    def __init__(self, manager, name, subnets, routes):
        """Create a router for given chain."""
        self.manager = manager
        self.subnets = subnets
        self.routes = routes
        self.name = name
        self.ports = [None, None]
        self.reuse = False
        self.router = None
        try:
            self._setup()
        except Exception:
            LOG.error("Error creating router %s", self.name)
            self.delete()
            raise

    def _setup(self):
        # Lookup if there is a matching router with same name
        routers = self.manager.neutron_client.list_routers(name=self.name)

        if routers['routers']:
            router = routers['routers'][0]
            # a router of same name already exists, we need to verify it has the same
            # characteristics
            if self.subnets:
                for subnet in self.subnets:
                    if not self.get_router_interface(router['id'], subnet.network['subnets'][0]):
                        raise ChainException("Mismatch of 'subnet_id' for reused "
                                             "router '{router}'.Router has no subnet id '{sub_id}'."
                                             .format(router=self.name,
                                                     sub_id=subnet.network['subnets'][0]))
                interfaces = self.manager.neutron_client.list_ports(device_id=router['id'])['ports']
                for interface in interfaces:
                    if self.is_ip_in_network(
                            interface['fixed_ips'][0]['ip_address'],
                            self.manager.config.traffic_generator.tg_gateway_ip_cidrs[0]) \
                        or self.is_ip_in_network(
                            interface['fixed_ips'][0]['ip_address'],
                            self.manager.config.traffic_generator.tg_gateway_ip_cidrs[1]):
                        self.ports[0] = interface
                    else:
                        self.ports[1] = interface
            if self.routes:
                for route in self.routes:
                    if route not in router['routes']:
                        LOG.info("Mismatch of 'router' for reused router '%s'."
                                 "Router has no existing route destination '%s', "
                                 "and nexthop '%s'.", self.name,
                                 route['destination'],
                                 route['nexthop'])
                        LOG.info("New route added to router %s for reused ", self.name)
                        body = {
                            'router': {
                                'routes': self.routes
                            }
                        }
                        self.manager.neutron_client.update_router(router['id'], body)

            LOG.info('Reusing existing router: %s', self.name)
            self.reuse = True
            self.router = router
            return

        body = {
            'router': {
                'name': self.name,
                'admin_state_up': True
            }
        }
        router = self.manager.neutron_client.create_router(body)['router']
        router_id = router['id']

        if self.subnets:
            for subnet in self.subnets:
                router_interface = {'subnet_id': subnet.network['subnets'][0]}
                self.manager.neutron_client.add_interface_router(router_id, router_interface)
            interfaces = self.manager.neutron_client.list_ports(device_id=router_id)['ports']
            for interface in interfaces:
                itf = interface['fixed_ips'][0]['ip_address']
                cidr0 = self.manager.config.traffic_generator.tg_gateway_ip_cidrs[0]
                cidr1 = self.manager.config.traffic_generator.tg_gateway_ip_cidrs[1]
                if self.is_ip_in_network(itf, cidr0) or self.is_ip_in_network(itf, cidr1):
                    self.ports[0] = interface
                else:
                    self.ports[1] = interface

        if self.routes:
            body = {
                'router': {
                    'routes': self.routes
                }
            }
            self.manager.neutron_client.update_router(router_id, body)

        LOG.info('Created router: %s.', self.name)
        self.router = self.manager.neutron_client.show_router(router_id)

    def get_uuid(self):
        """
        Extract UUID of this router.

        :return: UUID of this router
        """
        return self.router['id']

    def get_router_interface(self, router_id, subnet_id):
        interfaces = self.manager.neutron_client.list_ports(device_id=router_id)['ports']
        matching_interface = None
        for interface in interfaces:
            if interface['fixed_ips'][0]['subnet_id'] == subnet_id:
                matching_interface = interface
        return matching_interface

    def is_ip_in_network(self, interface_ip, cidr):
        return IPAddress(interface_ip) in IPNetwork(cidr)

    def delete(self):
        """Delete this router."""
        if not self.reuse and self.router:
            retry = 0
            while retry < self.manager.config.generic_retry_count:
                try:
                    self.manager.neutron_client.delete_router(self.router['id'])
                    LOG.info("Deleted router: %s", self.name)
                    return
                except Exception:
                    retry += 1
                    LOG.info('Error deleting router %s (retry %d/%d)...',
                             self.name,
                             retry,
                             self.manager.config.generic_retry_count)
                    time.sleep(self.manager.config.generic_poll_sec)
            LOG.error('Unable to delete router: %s', self.name)
