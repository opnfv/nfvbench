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

from __init__ import __version__
import argparse
from attrdict import AttrDict
from chain_runner import ChainRunner
from collections import defaultdict
from config import config_load
from config import config_loads
import credentials
import datetime
from factory import BasicFactory
import importlib
import json
import log
from log import LOG
from nfvbenchd import WebSocketIoServer
import os
import pbr.version
from pkg_resources import resource_string
from specs import Specs
from summarizer import NFVBenchSummarizer
import sys
import traceback
from traffic_client import TrafficGeneratorFactory
import utils


class NFVBench(object):
    """Main class of NFV benchmarking tool."""
    STATUS_OK = 'OK'
    STATUS_ERROR = 'ERROR'

    def __init__(self, config, openstack_spec, config_plugin, factory, notifier=None):
        self.base_config = config
        self.config = None
        self.config_plugin = config_plugin
        self.factory = factory
        self.notifier = notifier
        self.cred = credentials.Credentials(config.openrc_file, None, False)
        self.chain_runner = None
        self.specs = Specs()
        self.specs.set_openstack_spec(openstack_spec)
        self.clients = defaultdict(lambda: None)
        self.vni_ports = []
        sys.stdout.flush()

    def setup(self):
        self.specs.set_run_spec(self.config_plugin.get_run_spec(self.specs.openstack))
        self.chain_runner = ChainRunner(self.config,
                                        self.clients,
                                        self.cred,
                                        self.specs,
                                        self.factory,
                                        self.notifier)

    def set_notifier(self, notifier):
        self.notifier = notifier

    def run(self, opts):
        status = NFVBench.STATUS_OK
        result = None
        message = ''
        try:
            self.update_config(opts)
            self.setup()

            result = {
                "date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "nfvbench_version": __version__,
                "openstack_spec": {
                    "vswitch": self.specs.openstack.vswitch,
                    "encaps": self.specs.openstack.encaps
                },
                "config": self.config_plugin.prepare_results_config(dict(self.config)),
                "benchmarks": {
                    "network": {
                        "service_chain": self.chain_runner.run(),
                        "versions": self.chain_runner.get_version(),
                    }
                }
            }
            result['benchmarks']['network']['versions'].update(self.config_plugin.get_version())
        except Exception:
            status = NFVBench.STATUS_ERROR
            message = traceback.format_exc()
        except KeyboardInterrupt:
            status = NFVBench.STATUS_ERROR
            message = traceback.format_exc()
        finally:
            if self.chain_runner:
                self.chain_runner.close()

            if status == NFVBench.STATUS_OK:
                result = utils.dict_to_json_dict(result)
                return {
                    'status': status,
                    'result': result
                }
            else:
                return {
                    'status': status,
                    'error_message': message
                }

    def print_summary(self, result):
        """Print summary of the result"""
        print NFVBenchSummarizer(result)
        sys.stdout.flush()

    def save(self, result):
        """Save results in json format file."""
        utils.save_json_result(result,
                               self.config.json_file,
                               self.config.std_json_path,
                               self.config.service_chain,
                               self.config.service_chain_count,
                               self.config.flow_count,
                               self.config.frame_sizes)

    def update_config(self, opts):
        self.config = AttrDict(dict(self.base_config))
        self.config.update(opts)

        self.config.service_chain = self.config.service_chain.upper()
        self.config.service_chain_count = int(self.config.service_chain_count)
        self.config.flow_count = utils.parse_flow_count(self.config.flow_count)
        required_flow_count = self.config.service_chain_count * 2
        if self.config.flow_count < required_flow_count:
            LOG.info("Flow count '{}' has been set to minimum value of '{}' "
                     "for current configuration".format(self.config.flow_count,
                                                        required_flow_count))
            self.config.flow_count = required_flow_count

        if self.config.flow_count % 2 != 0:
            self.config.flow_count += 1

        self.config.duration_sec = float(self.config.duration_sec)
        self.config.interval_sec = float(self.config.interval_sec)

        # Get traffic generator profile config
        if not self.config.generator_profile:
            self.config.generator_profile = self.config.traffic_generator.default_profile

        generator_factory = TrafficGeneratorFactory(self.config)
        self.config.generator_config = \
            generator_factory.get_generator_config(self.config.generator_profile)

        if not any(self.config.generator_config.pcis):
            raise Exception("PCI addresses configuration for selected traffic generator profile "
                            "({tg_profile}) are missing. Please specify them in configuration file."
                            .format(tg_profile=self.config.generator_profile))

        if self.config.traffic is None or len(self.config.traffic) == 0:
            raise Exception("No traffic profile found in traffic configuration, "
                            "please fill 'traffic' section in configuration file.")

        if isinstance(self.config.traffic, tuple):
            self.config.traffic = self.config.traffic[0]

        self.config.frame_sizes = generator_factory.get_frame_sizes(self.config.traffic.profile)

        self.config.ipv6_mode = False
        self.config.no_dhcp = True
        self.config.same_network_only = True
        if self.config.openrc_file:
            self.config.openrc_file = os.path.expanduser(self.config.openrc_file)

        self.config.ndr_run = (not self.config.no_traffic
                               and 'ndr' in self.config.rate.strip().lower().split('_'))
        self.config.pdr_run = (not self.config.no_traffic
                               and 'pdr' in self.config.rate.strip().lower().split('_'))
        self.config.single_run = (not self.config.no_traffic
                                  and not (self.config.ndr_run or self.config.pdr_run))

        if self.config.vlans and len(self.config.vlans) != 2:
            raise Exception('Number of configured VLAN IDs for VLAN tagging must be exactly 2.')

        self.config.json_file = self.config.json if self.config.json else None
        if self.config.json_file:
            (path, filename) = os.path.split(self.config.json)
            if not os.path.exists(path):
                raise Exception('Please provide existing path for storing results in JSON file. '
                                'Path used: {path}'.format(path=path))

        self.config.std_json_path = self.config.std_json if self.config.std_json else None
        if self.config.std_json_path:
            if not os.path.exists(self.config.std_json):
                raise Exception('Please provide existing path for storing results in JSON file. '
                                'Path used: {path}'.format(path=self.config.std_json_path))

        self.config_plugin.validate_config(self.config)


def parse_opts_from_cli():
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', dest='config',
                        action='store',
                        help='Override default values with a config file or '
                             'a yaml/json config string',
                        metavar='<file_name_or_yaml>')

    parser.add_argument('--server', dest='server',
                        default=None,
                        action='store',
                        metavar='<http_root_pathname>',
                        help='Run nfvbench in server mode and pass'
                             ' the HTTP root folder full pathname')

    parser.add_argument('--host', dest='host',
                        action='store',
                        default='0.0.0.0',
                        help='Host IP address on which server will be listening (default 0.0.0.0)')

    parser.add_argument('-p', '--port', dest='port',
                        action='store',
                        default=7555,
                        help='Port on which server will be listening (default 7555)')

    parser.add_argument('-sc', '--service-chain', dest='service_chain',
                        choices=BasicFactory.chain_classes,
                        action='store',
                        help='Service chain to run')

    parser.add_argument('-scc', '--service-chain-count', dest='service_chain_count',
                        action='store',
                        help='Set number of service chains to run',
                        metavar='<service_chain_count>')

    parser.add_argument('-fc', '--flow-count', dest='flow_count',
                        action='store',
                        help='Set number of total flows for all chains and all directions',
                        metavar='<flow_count>')

    parser.add_argument('--rate', dest='rate',
                        action='store',
                        help='Specify rate in pps, bps or %% as total for all directions',
                        metavar='<rate>')

    parser.add_argument('--duration', dest='duration_sec',
                        action='store',
                        help='Set duration to run traffic generator (in seconds)',
                        metavar='<duration_sec>')

    parser.add_argument('--interval', dest='interval_sec',
                        action='store',
                        help='Set interval to record traffic generator stats (in seconds)',
                        metavar='<interval_sec>')

    parser.add_argument('--inter-node', dest='inter_node',
                        default=None,
                        action='store_true',
                        help='run VMs in different compute nodes (PVVP only)')

    parser.add_argument('--sriov', dest='sriov',
                        default=None,
                        action='store_true',
                        help='Use SRIOV (no vswitch - requires SRIOV support in compute nodes)')

    parser.add_argument('-d', '--debug', dest='debug',
                        action='store_true',
                        default=None,
                        help='print debug messages (verbose)')

    parser.add_argument('-g', '--traffic-gen', dest='generator_profile',
                        action='store',
                        help='Traffic generator profile to use')

    parser.add_argument('-i', '--image', dest='image_name',
                        action='store',
                        help='VM image name to use')

    parser.add_argument('-0', '--no-traffic', dest='no_traffic',
                        default=None,
                        action='store_true',
                        help='Check config and connectivity only - do not generate traffic')

    parser.add_argument('--no-arp', dest='no_arp',
                        default=None,
                        action='store_true',
                        help='Do not use ARP to find MAC addresses, '
                             'instead use values in config file')

    parser.add_argument('--no-reset', dest='no_reset',
                        default=None,
                        action='store_true',
                        help='Do not reset counters prior to running')

    parser.add_argument('--no-int-config', dest='no_int_config',
                        default=None,
                        action='store_true',
                        help='Skip interfaces config on EXT service chain')

    parser.add_argument('--no-tor-access', dest='no_tor_access',
                        default=None,
                        action='store_true',
                        help='Skip TOR switch configuration and retrieving of stats')

    parser.add_argument('--no-vswitch-access', dest='no_vswitch_access',
                        default=None,
                        action='store_true',
                        help='Skip vswitch configuration and retrieving of stats')

    parser.add_argument('--no-cleanup', dest='no_cleanup',
                        default=None,
                        action='store_true',
                        help='no cleanup after run')

    parser.add_argument('--json', dest='json',
                        action='store',
                        help='store results in json format file',
                        metavar='<path>/<filename>')

    parser.add_argument('--std-json', dest='std_json',
                        action='store',
                        help='store results in json format file with nfvbench standard filename: '
                             '<service-chain-type>-<service-chain-count>-<flow-count>'
                             '-<packet-sizes>.json',
                        metavar='<path>')

    parser.add_argument('--show-default-config', dest='show_default_config',
                        default=None,
                        action='store_true',
                        help='print the default config in yaml format (unedited)')

    parser.add_argument('--show-config', dest='show_config',
                        default=None,
                        action='store_true',
                        help='print the running config in json format')

    parser.add_argument('-ss', '--show-summary', dest='summary',
                        action='store',
                        help='Show summary from nfvbench json file',
                        metavar='<json>')

    parser.add_argument('-v', '--version', dest='version',
                        default=None,
                        action='store_true',
                        help='Show version')

    parser.add_argument('-fs', '--frame-size', dest='frame_sizes',
                        action='append',
                        help='Override traffic profile frame sizes',
                        metavar='<frame_size_bytes or IMIX>')

    parser.add_argument('--unidir', dest='unidir',
                        action='store_true',
                        default=None,
                        help='Override traffic profile direction (requires -fs)')

    opts, unknown_opts = parser.parse_known_args()
    return opts, unknown_opts


def load_default_config():
    default_cfg = resource_string(__name__, "cfg.default.yaml")
    config = config_loads(default_cfg)
    config.name = '(built-in default config)'
    return config, default_cfg


def override_custom_traffic(config, frame_sizes, unidir):
    """Override the traffic profiles with a custom one
    """
    if frame_sizes is not None:
        traffic_profile_name = "custom_traffic_profile"
        config.traffic_profile = [
            {
                "l2frame_size": frame_sizes,
                "name": traffic_profile_name
            }
        ]
    else:
        traffic_profile_name = config.traffic["profile"]

    bidirectional = config.traffic['bidirectional'] if unidir is None else not unidir
    config.traffic = {
        "bidirectional": bidirectional,
        "profile": traffic_profile_name
    }


def main():
    try:
        log.setup('nfvbench')
        # load default config file
        config, default_cfg = load_default_config()
        # create factory for platform specific classes
        try:
            factory_module = importlib.import_module(config['factory_module'])
            factory = getattr(factory_module, config['factory_class'])()
        except AttributeError:
            raise Exception("Requested factory module '{m}' or class '{c}' was not found."
                            .format(m=config['factory_module'], c=config['factory_class']))
        # create config plugin for this platform
        config_plugin = factory.get_config_plugin_class()(config)
        config = config_plugin.get_config()
        openstack_spec = config_plugin.get_openstack_spec()

        opts, unknown_opts = parse_opts_from_cli()
        log.set_level('nfvbench', debug=opts.debug)

        if opts.version:
            print pbr.version.VersionInfo('nfvbench').version_string_with_vcs()
            sys.exit(0)

        if opts.summary:
            with open(opts.summary) as json_data:
                print NFVBenchSummarizer(json.load(json_data))
            sys.exit(0)

        # show default config in text/yaml format
        if opts.show_default_config:
            print default_cfg
            sys.exit(0)

        config.name = ''
        if opts.config:
            # override default config options with start config at path parsed from CLI
            # check if it is an inline yaml/json config or a file name
            if os.path.isfile(opts.config):
                print opts.config
                config = config_load(opts.config, config)
                config.name = os.path.basename(opts.config)
            else:
                config = config_loads(opts.config, config)

        # traffic profile override options
        override_custom_traffic(config, opts.frame_sizes, opts.unidir)

        # copy over cli options that are used in config
        config.generator_profile = opts.generator_profile

        # show running config in json format
        if opts.show_config:
            print json.dumps(config, sort_keys=True, indent=4)
            sys.exit(0)

        nfvbench = NFVBench(config, openstack_spec, config_plugin, factory)

        if opts.server:
            if os.path.isdir(opts.server):
                server = WebSocketIoServer(opts.server, nfvbench)
                nfvbench.set_notifier(server)
                try:
                    port = int(opts.port)
                except ValueError:
                    server.run(host=opts.host)
                else:
                    server.run(host=opts.host, port=port)
            else:
                print 'Invalid HTTP root directory: ' + opts.server
                sys.exit(1)
        else:
            with utils.RunLock():
                if unknown_opts:
                    LOG.warning('Unknown options: ' + ' '.join(unknown_opts))

                # remove unfilled values
                opts = {k: v for k, v in vars(opts).iteritems() if v is not None}
                result = nfvbench.run(opts)
                if 'error_message' in result:
                    raise Exception(result['error_message'])

                if 'result' in result and result['status']:
                    nfvbench.save(result['result'])
                    nfvbench.print_summary(result['result'])
    except Exception:
        LOG.error({
            'status': NFVBench.STATUS_ERROR,
            'error_message': traceback.format_exc()
        })
        sys.exit(1)

if __name__ == '__main__':
    main()
