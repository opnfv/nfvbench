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

from log import LOG
from network import Network
from packet_analyzer import PacketAnalyzer
from specs import ChainType
from stats_collector import IntervalCollector


class StageManager(object):
    """A class to stage resources in the systenm under test."""

    def __init__(self, config, cred, factory):
        self.config = config
        self.client = None
        # conditions due to EXT chain special cases
        if (config.vlan_tagging and not config.vlans) or not config.no_int_config:
            VM_CLASS = factory.get_stage_class(config.service_chain)
            self.client = VM_CLASS(config, cred)
            self.client.setup()

    def get_vlans(self):
        return self.client.get_vlans() if self.client else []

    def get_host_ips(self):
        return self.client.get_host_ips()

    def get_networks_uuids(self):
        return self.client.get_networks_uuids()

    def disable_port_security(self):
        self.client.disable_port_security()

    def get_vms(self):
        return self.client.vms

    def get_nets(self):
        return self.client.nets

    def get_ports(self):
        return self.client.ports

    def get_compute_nodes(self):
        return self.client.compute_nodes if self.client else {}

    def set_vm_macs(self):
        if self.client and self.config.service_chain != ChainType.EXT:
            self.config.generator_config.set_vm_mac_list(self.client.get_end_port_macs())

    def close(self):
        if not self.config.no_cleanup and self.client:
            self.client.dispose()


class PVPStatsManager(object):
    """A class to generate traffic and extract results for PVP chains."""

    def __init__(self, config, clients, specs, factory, vlans, notifier=None):
        self.config = config
        self.clients = clients
        self.specs = specs
        self.notifier = notifier
        self.interval_collector = None
        self.vlans = vlans
        self.factory = factory
        self._setup()

    def set_vlan_tag(self, device, vlan):
        if self.worker:
            self.worker.set_vlan_tag(device, vlan)

    def _setup(self):
        WORKER_CLASS = self.factory.get_chain_worker(self.specs.openstack.encaps,
                                                     self.config.service_chain)
        self.worker = WORKER_CLASS(self.config, self.clients, self.specs)
        try:
            self.worker.set_vlans(self.vlans)
            self._config_interfaces()
        except Exception:
            # since the wrorker is up and running, we need to close it
            # in case of exception
            self.close()
            raise

    def _get_data(self):
        return self.worker.get_data() if self.worker else {}

    def _get_network(self, traffic_port, stats, reverse=False):
        """Get the Network object corresponding to a given TG port.

        :param traffic_port: must be either 0 or 1
        :param stats: TG stats for given traffic port
        :param reverse: specifies if the interface list for this network
        should go from TG to loopback point (reverse=false) or
        from loopback point to TG (reverse=true)
        """
        # build the interface list in fwd direction (TG To loopback point)
        interfaces = [self.clients['traffic'].get_interface(traffic_port, stats)]
        if self.worker:
            # if available,
            # interfaces for workers must be aligned on the TG port number
            interfaces.extend(self.worker.get_network_interfaces(traffic_port))
        # let Network reverse the interface order if needed
        return Network(interfaces, reverse)

    def _config_interfaces(self):
        if self.config.service_chain != ChainType.EXT:
            self.clients['vm'].disable_port_security()

        self.worker.config_interfaces()

    def _generate_traffic(self):
        if self.config.no_traffic:
            return {}

        self.interval_collector = IntervalCollector(time.time())
        self.interval_collector.attach_notifier(self.notifier)
        LOG.info('Starting to generate traffic...')
        stats = {}
        for stats in self.clients['traffic'].run_traffic():
            self.interval_collector.add(stats)

        LOG.info('...traffic generating ended.')
        return stats

    def get_stats(self):
        return self.interval_collector.get() if self.interval_collector else []

    def get_version(self):
        return self.worker.get_version() if self.worker else {}

    def run(self):
        """Run analysis in both direction and return the analysis."""
        if self.worker:
            self.worker.run()

        stats = self._generate_traffic()
        result = {
            'raw_data': self._get_data(),
            'packet_analysis': {},
            'stats': stats
        }

        # fetch latest stats from traffic gen
        stats = self.clients['traffic'].get_stats()
        LOG.info('Requesting packet analysis on the forward direction...')
        result['packet_analysis']['direction-forward'] = \
            self.get_analysis([self._get_network(0, stats),
                               self._get_network(1, stats, reverse=True)])
        LOG.info('Packet analysis on the forward direction completed')

        LOG.info('Requesting packet analysis on the reverse direction...')
        result['packet_analysis']['direction-reverse'] = \
            self.get_analysis([self._get_network(1, stats),
                               self._get_network(0, stats, reverse=True)])

        LOG.info('Packet analysis on the reverse direction completed')
        return result

    def get_compute_nodes_bios(self):
        return self.worker.get_compute_nodes_bios() if self.worker else {}

    @staticmethod
    def get_analysis(nets):
        LOG.info('Starting traffic analysis...')

        packet_analyzer = PacketAnalyzer()
        # Traffic types are assumed to always alternate in every chain. Add a no stats interface in
        # between if that is not the case.
        tx = True
        for network in nets:
            for interface in network.get_interfaces():
                packet_analyzer.record(interface, 'tx' if tx else 'rx')
                tx = not tx

        LOG.info('...traffic analysis completed')
        return packet_analyzer.get_analysis()

    def close(self):
        if self.worker:
            self.worker.close()


class PVVPStatsManager(PVPStatsManager):
    """A Class to generate traffic and extract results for PVVP chains."""

    def __init__(self, config, clients, specs, factory, vlans, notifier=None):
        PVPStatsManager.__init__(self, config, clients, specs, factory, vlans, notifier)

    def run(self):
        """Run analysis in both direction and return the analysis."""
        fwd_v2v_net, rev_v2v_net = self.worker.run()

        stats = self._generate_traffic()
        result = {
            'raw_data': self._get_data(),
            'packet_analysis': {},
            'stats': stats
        }
        # fetch latest stats from traffic gen
        stats = self.clients['traffic'].get_stats()
        fwd_nets = [self._get_network(0, stats)]
        if fwd_v2v_net:
            fwd_nets.append(fwd_v2v_net)
        fwd_nets.append(self._get_network(1, stats, reverse=True))

        rev_nets = [self._get_network(1, stats)]
        if rev_v2v_net:
            rev_nets.append(rev_v2v_net)
        rev_nets.append(self._get_network(0, stats, reverse=True))

        LOG.info('Requesting packet analysis on the forward direction...')
        result['packet_analysis']['direction-forward'] = self.get_analysis(fwd_nets)
        LOG.info('Packet analysis on the forward direction completed')

        LOG.info('Requesting packet analysis on the reverse direction...')
        result['packet_analysis']['direction-reverse'] = self.get_analysis(rev_nets)

        LOG.info('Packet analysis on the reverse direction completed')
        return result


class EXTStatsManager(PVPStatsManager):
    """A Class to generate traffic and extract results for EXT chains."""

    def __init__(self, config, clients, specs, factory, vlans, notifier=None):
        PVPStatsManager.__init__(self, config, clients, specs, factory, vlans, notifier)

    def _setup(self):
        if self.specs.openstack:
            WORKER_CLASS = self.factory.get_chain_worker(self.specs.openstack.encaps,
                                                         self.config.service_chain)
            self.worker = WORKER_CLASS(self.config, self.clients, self.specs)
            self.worker.set_vlans(self.vlans)

            if not self.config.no_int_config:
                self._config_interfaces()
        else:
            self.worker = None
