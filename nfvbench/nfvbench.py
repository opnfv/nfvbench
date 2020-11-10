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

import argparse
import copy
import datetime
import importlib
import json
import os
import sys
import traceback

from attrdict import AttrDict
from logging import FileHandler
import pbr.version
from pkg_resources import resource_string

from .__init__ import __version__
from .chain_runner import ChainRunner
from .cleanup import Cleaner
from .config import config_load
from .config import config_loads
from . import credentials
from .fluentd import FluentLogHandler
from . import log
from .log import LOG
from .nfvbenchd import WebServer
from .specs import ChainType
from .specs import Specs
from .summarizer import NFVBenchSummarizer
from . import utils

fluent_logger = None


class NFVBench(object):
    """Main class of NFV benchmarking tool."""

    STATUS_OK = 'OK'
    STATUS_ERROR = 'ERROR'

    def __init__(self, config, openstack_spec, config_plugin, factory, notifier=None):
        # the base config never changes for a given NFVbench instance
        self.base_config = config
        # this is the running config, updated at every run()
        self.config = None
        self.config_plugin = config_plugin
        self.factory = factory
        self.notifier = notifier
        self.cred = credentials.Credentials(config.openrc_file, None, False) \
            if config.openrc_file else None
        self.chain_runner = None
        self.specs = Specs()
        self.specs.set_openstack_spec(openstack_spec)
        self.vni_ports = []
        sys.stdout.flush()

    def set_notifier(self, notifier):
        self.notifier = notifier

    def run(self, opts, args, dry_run=False):
        """This run() method is called for every NFVbench benchmark request.

        In CLI mode, this method is called only once per invocation.
        In REST server mode, this is called once per REST POST request
        On dry_run, show the running config in json format then exit
        """
        status = NFVBench.STATUS_OK
        result = None
        message = ''
        if fluent_logger:
            # take a snapshot of the current time for this new run
            # so that all subsequent logs can relate to this run
            fluent_logger.start_new_run()
        LOG.info(args)
        try:
            # recalc the running config based on the base config and options for this run
            self._update_config(opts)

            if dry_run:
                print((json.dumps(self.config, sort_keys=True, indent=4)))
                sys.exit(0)

            # check that an empty openrc file (no OpenStack) is only allowed
            # with EXT chain
            if not self.config.openrc_file and self.config.service_chain != ChainType.EXT:
                raise Exception("openrc_file in the configuration is required for PVP/PVVP chains")

            self.specs.set_run_spec(self.config_plugin.get_run_spec(self.config,
                                                                    self.specs.openstack))
            self.chain_runner = ChainRunner(self.config,
                                            self.cred,
                                            self.specs,
                                            self.factory,
                                            self.notifier)
            new_frame_sizes = []
            # make sure that the min frame size is 64
            min_packet_size = 64
            for frame_size in self.config.frame_sizes:
                try:
                    if int(frame_size) < min_packet_size:
                        frame_size = str(min_packet_size)
                        LOG.info("Adjusting frame size %s bytes to minimum size %s bytes",
                                 frame_size, min_packet_size)
                    if frame_size not in new_frame_sizes:
                        new_frame_sizes.append(frame_size)
                except ValueError:
                    new_frame_sizes.append(frame_size.upper())
            self.config.frame_sizes = new_frame_sizes
            result = {
                "date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "nfvbench_version": __version__,
                "config": self.config_plugin.prepare_results_config(copy.deepcopy(self.config)),
                "benchmarks": {
                    "network": {
                        "service_chain": self.chain_runner.run(),
                        "versions": self.chain_runner.get_version(),
                    }
                }
            }
            if self.specs.openstack:
                result['openstack_spec'] = {"vswitch": self.specs.openstack.vswitch,
                                            "encaps": self.specs.openstack.encaps}
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
            # result2 = utils.dict_to_json_dict(result)
            return {
                'status': status,
                'result': result
            }
        return {
            'status': status,
            'error_message': message
        }

    def prepare_summary(self, result):
        """Prepare summary of the result to print and send it to logger (eg: fluentd)."""
        global fluent_logger
        summary = NFVBenchSummarizer(result, fluent_logger)
        LOG.info(str(summary))

    def save(self, result):
        """Save results in json format file."""
        utils.save_json_result(result,
                               self.config.json_file,
                               self.config.std_json_path,
                               self.config.service_chain,
                               self.config.service_chain_count,
                               self.config.flow_count,
                               self.config.frame_sizes,
                               self.config.user_id,
                               self.config.group_id)

    def _update_config(self, opts):
        """Recalculate the running config based on the base config and opts.

        Sanity check on the config is done here as well.
        """
        self.config = AttrDict(dict(self.base_config))
        # Update log file handler if needed after a config update (REST mode)
        if 'log_file' in opts:
            if opts['log_file']:
                (path, _filename) = os.path.split(opts['log_file'])
                if not os.path.exists(path):
                    LOG.warning(
                        'Path %s does not exist. Please verify root path is shared with host. Path '
                        'will be created.', path)
                    os.makedirs(path)
                    LOG.info('%s is created.', path)
                if not any(isinstance(h, FileHandler) for h in log.getLogger().handlers):
                    log.add_file_logger(opts['log_file'])
                else:
                    for h in log.getLogger().handlers:
                        if isinstance(h, FileHandler) and h.baseFilename != opts['log_file']:
                            # clean log file handler
                            log.getLogger().removeHandler(h)
                            log.add_file_logger(opts['log_file'])

        self.config.update(opts)
        config = self.config

        config.service_chain = config.service_chain.upper()
        config.service_chain_count = int(config.service_chain_count)
        if config.l2_loopback:
            # force the number of chains to be 1 in case of untagged l2 loopback
            # (on the other hand, multiple L2 vlan tagged service chains are allowed)
            if not config.vlan_tagging:
                config.service_chain_count = 1
            config.service_chain = ChainType.EXT
            config.no_arp = True
            LOG.info('Running L2 loopback: using EXT chain/no ARP')

        # allow oversized vlan lists, just clip them
        try:
            vlans = [list(v) for v in config.vlans]
            for v in vlans:
                del v[config.service_chain_count:]
            config.vlans = vlans
        except Exception:
            pass

        # traffic profile override options
        if 'frame_sizes' in opts:
            unidir = False
            if 'unidir' in opts:
                unidir = opts['unidir']
            override_custom_traffic(config, opts['frame_sizes'], unidir)
            LOG.info("Frame size has been set to %s for current configuration", opts['frame_sizes'])

        config.flow_count = utils.parse_flow_count(config.flow_count)
        required_flow_count = config.service_chain_count * 2
        if config.flow_count < required_flow_count:
            LOG.info("Flow count %d has been set to minimum value of '%d' "
                     "for current configuration", config.flow_count,
                     required_flow_count)
            config.flow_count = required_flow_count

        if config.flow_count % 2:
            config.flow_count += 1

        # Possibly adjust the cache size
        if config.cache_size < 0:
            config.cache_size = config.flow_count

        # The size must be capped to 10000 (where does this limit come from?)
        if config.cache_size > 10000:
            config.cache_size = 10000

        config.duration_sec = float(config.duration_sec)
        config.interval_sec = float(config.interval_sec)
        config.pause_sec = float(config.pause_sec)

        if config.traffic is None or not config.traffic:
            raise Exception("Missing traffic property in configuration")

        if config.openrc_file:
            config.openrc_file = os.path.expanduser(config.openrc_file)
            if config.flavor.vcpus < 2:
                raise Exception("Flavor vcpus must be >= 2")

        config.ndr_run = (not config.no_traffic and
                          'ndr' in config.rate.strip().lower().split('_'))
        config.pdr_run = (not config.no_traffic and
                          'pdr' in config.rate.strip().lower().split('_'))
        config.single_run = (not config.no_traffic and
                             not (config.ndr_run or config.pdr_run))

        config.json_file = config.json if config.json else None
        if config.json_file:
            (path, _filename) = os.path.split(config.json)
            if not os.path.exists(path):
                raise Exception('Please provide existing path for storing results in JSON file. '
                                'Path used: {path}'.format(path=path))

        config.std_json_path = config.std_json if config.std_json else None
        if config.std_json_path:
            if not os.path.exists(config.std_json):
                raise Exception('Please provide existing path for storing results in JSON file. '
                                'Path used: {path}'.format(path=config.std_json_path))

        # Check that multiqueue is between 1 and 8 (8 is the max allowed by libvirt/qemu)
        if config.vif_multiqueue_size < 1 or config.vif_multiqueue_size > 8:
            raise Exception('vif_multiqueue_size (%d) must be in [1..8]' %
                            config.vif_multiqueue_size)

        # VxLAN and MPLS sanity checks
        if config.vxlan or config.mpls:
            if config.vlan_tagging:
                config.vlan_tagging = False
                config.no_latency_streams = True
                config.no_latency_stats = True
                config.no_flow_stats = True
                LOG.info('VxLAN or MPLS: vlan_tagging forced to False '
                         '(inner VLAN tagging must be disabled)')

        self.config_plugin.validate_config(config, self.specs.openstack)


def bool_arg(x):
    """Argument type to be used in parser.add_argument()
    When a boolean like value is expected to be given
    """
    return (str(x).lower() != 'false') \
        and (str(x).lower() != 'no') \
        and (str(x).lower() != '0')


def int_arg(x):
    """Argument type to be used in parser.add_argument()
    When an integer type value is expected to be given
    (returns 0 if argument is invalid, hexa accepted)
    """
    return int(x, 0)


def _parse_opts_from_cli():
    parser = argparse.ArgumentParser()

    parser.add_argument('--status', dest='status',
                        action='store_true',
                        default=None,
                        help='Provide NFVbench status')

    parser.add_argument('-c', '--config', dest='config',
                        action='store',
                        help='Override default values with a config file or '
                             'a yaml/json config string',
                        metavar='<file_name_or_yaml>')

    parser.add_argument('--server', dest='server',
                        default=None,
                        action='store_true',
                        help='Run nfvbench in server mode')

    parser.add_argument('--host', dest='host',
                        action='store',
                        default='0.0.0.0',
                        help='Host IP address on which server will be listening (default 0.0.0.0)')

    parser.add_argument('-p', '--port', dest='port',
                        action='store',
                        default=7555,
                        help='Port on which server will be listening (default 7555)')

    parser.add_argument('-sc', '--service-chain', dest='service_chain',
                        choices=ChainType.names,
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
                        help='(deprecated)')

    parser.add_argument('--sriov', dest='sriov',
                        default=None,
                        action='store_true',
                        help='Use SRIOV (no vswitch - requires SRIOV support in compute nodes)')

    parser.add_argument('--use-sriov-middle-net', dest='use_sriov_middle_net',
                        default=None,
                        action='store_true',
                        help='Use SRIOV to handle the middle network traffic '
                             '(PVVP with SRIOV only)')

    parser.add_argument('-d', '--debug', dest='debug',
                        action='store_true',
                        default=None,
                        help='print debug messages (verbose)')

    parser.add_argument('-g', '--traffic-gen', dest='generator_profile',
                        action='store',
                        help='Traffic generator profile to use')

    parser.add_argument('-l3', '--l3-router', dest='l3_router',
                        default=None,
                        action='store_true',
                        help='Use L3 neutron routers to handle traffic')

    parser.add_argument('-0', '--no-traffic', dest='no_traffic',
                        default=None,
                        action='store_true',
                        help='Check config and connectivity only - do not generate traffic')

    parser.add_argument('--no-arp', dest='no_arp',
                        default=None,
                        action='store_true',
                        help='Do not use ARP to find MAC addresses, '
                             'instead use values in config file')

    parser.add_argument('--loop-vm-arp', dest='loop_vm_arp',
                        default=None,
                        action='store_true',
                        help='Use ARP to find MAC addresses '
                             'instead of using values from TRex ports (VPP forwarder only)')

    parser.add_argument('--no-vswitch-access', dest='no_vswitch_access',
                        default=None,
                        action='store_true',
                        help='Skip vswitch configuration and retrieving of stats')

    parser.add_argument('--vxlan', dest='vxlan',
                        default=None,
                        action='store_true',
                        help='Enable VxLan encapsulation')

    parser.add_argument('--mpls', dest='mpls',
                        default=None,
                        action='store_true',
                        help='Enable MPLS encapsulation')

    parser.add_argument('--no-cleanup', dest='no_cleanup',
                        default=None,
                        action='store_true',
                        help='no cleanup after run')

    parser.add_argument('--cleanup', dest='cleanup',
                        default=None,
                        action='store_true',
                        help='Cleanup NFVbench resources (prompt to confirm)')

    parser.add_argument('--force-cleanup', dest='force_cleanup',
                        default=None,
                        action='store_true',
                        help='Cleanup NFVbench resources (do not prompt)')

    parser.add_argument('--restart', dest='restart',
                        default=None,
                        action='store_true',
                        help='Restart TRex server')

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

    parser.add_argument('--show-pre-config', dest='show_pre_config',
                        default=None,
                        action='store_true',
                        help='print the config in json format (cfg file applied)')

    parser.add_argument('--show-config', dest='show_config',
                        default=None,
                        action='store_true',
                        help='print the running config in json format (final)')

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

    parser.add_argument('--log-file', '--logfile', dest='log_file',
                        action='store',
                        help='Filename for saving logs',
                        metavar='<log_file>')

    parser.add_argument('--user-label', '--userlabel', dest='user_label',
                        action='store',
                        help='Custom label for performance records')

    parser.add_argument('--hypervisor', dest='hypervisor',
                        action='store',
                        metavar='<hypervisor name>',
                        help='Where chains must run ("compute", "az:", "az:compute")')

    parser.add_argument('--l2-loopback', '--l2loopback', dest='l2_loopback',
                        action='store',
                        metavar='<vlan(s)|no-tag|true|false>',
                        help='Port to port or port to switch to port L2 loopback '
                             'tagged with given VLAN id(s) or not (given \'no-tag\') '
                             '\'true\': use current vlans; \'false\': disable this mode.')

    parser.add_argument('--user-info', dest='user_info',
                        action='append',
                        metavar='<data>',
                        help='Custom data to be included as is '
                             'in the json report config branch - '
                             ' example, pay attention! no space: '
                             '--user-info=\'{"status":"explore","description":'
                             '{"target":"lab","ok":true,"version":2020}}\' - '
                             'this option may be repeated; given data will be merged.')

    parser.add_argument('--vlan-tagging', dest='vlan_tagging',
                        type=bool_arg,
                        metavar='<boolean>',
                        action='store',
                        default=None,
                        help='Override the NFVbench \'vlan_tagging\' parameter')

    parser.add_argument('--intf-speed', dest='intf_speed',
                        metavar='<speed>',
                        action='store',
                        default=None,
                        help='Override the NFVbench \'intf_speed\' '
                             'parameter (e.g. 10Gbps, auto, 16.72Gbps)')

    parser.add_argument('--cores', dest='cores',
                        type=int_arg,
                        metavar='<number>',
                        action='store',
                        default=None,
                        help='Override the T-Rex \'cores\' parameter')

    parser.add_argument('--cache-size', dest='cache_size',
                        type=int_arg,
                        metavar='<size>',
                        action='store',
                        default=None,
                        help='Specify the FE cache size (default: 0, flow-count if < 0)')

    parser.add_argument('--service-mode', dest='service_mode',
                        action='store_true',
                        default=None,
                        help='Enable T-Rex service mode (for debugging purpose)')

    parser.add_argument('--no-e2e-check', dest='no_e2e_check',
                        action='store_true',
                        default=None,
                        help='Skip "end to end" connectivity check (on test purpose)')

    parser.add_argument('--no-flow-stats', dest='no_flow_stats',
                        action='store_true',
                        default=None,
                        help='Disable additional flow stats (on high load traffic)')

    parser.add_argument('--no-latency-stats', dest='no_latency_stats',
                        action='store_true',
                        default=None,
                        help='Disable flow stats for latency traffic')

    parser.add_argument('--no-latency-streams', dest='no_latency_streams',
                        action='store_true',
                        default=None,
                        help='Disable latency measurements (no streams)')

    parser.add_argument('--user-id', dest='user_id',
                        type=int_arg,
                        metavar='<uid>',
                        action='store',
                        default=None,
                        help='Change json/log files ownership with this user (int)')

    parser.add_argument('--group-id', dest='group_id',
                        type=int_arg,
                        metavar='<gid>',
                        action='store',
                        default=None,
                        help='Change json/log files ownership with this group (int)')

    parser.add_argument('--show-trex-log', dest='show_trex_log',
                        default=None,
                        action='store_true',
                        help='Show the current TRex local server log file contents'
                             ' => diagnostic/help in case of configuration problems')

    parser.add_argument('--debug-mask', dest='debug_mask',
                        type=int_arg,
                        metavar='<mask>',
                        action='store',
                        default=None,
                        help='General purpose register (debugging flags), '
                             'the hexadecimal notation (0x...) is accepted.'
                             'Designed for development needs (default: 0).')

    opts, unknown_opts = parser.parse_known_args()
    return opts, unknown_opts


def load_default_config():
    default_cfg = resource_string(__name__, "cfg.default.yaml")
    config = config_loads(default_cfg)
    config.name = '(built-in default config)'
    return config, default_cfg


def override_custom_traffic(config, frame_sizes, unidir):
    """Override the traffic profiles with a custom one."""
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


def check_physnet(name, netattrs):
    if not netattrs.physical_network:
        raise Exception("SRIOV requires physical_network to be specified for the {n} network"
                        .format(n=name))
    if not netattrs.segmentation_id:
        raise Exception("SRIOV requires segmentation_id to be specified for the {n} network"
                        .format(n=name))

def status_cleanup(config, cleanup, force_cleanup):
    LOG.info('Version: %s', pbr.version.VersionInfo('nfvbench').version_string_with_vcs())
    # check if another run is pending
    ret_code = 0
    try:
        with utils.RunLock():
            LOG.info('Status: idle')
    except Exception:
        LOG.info('Status: busy (run pending)')
        ret_code = 1
    # check nfvbench resources
    if config.openrc_file and config.service_chain != ChainType.EXT:
        cleaner = Cleaner(config)
        count = cleaner.show_resources()
        if count and (cleanup or force_cleanup):
            cleaner.clean(not force_cleanup)
    sys.exit(ret_code)

def main():
    global fluent_logger
    run_summary_required = False
    try:
        log.setup()
        # load default config file
        config, default_cfg = load_default_config()
        # possibly override the default user_id & group_id values
        if 'USER_ID' in os.environ:
            config.user_id = int(os.environ['USER_ID'])
        if 'GROUP_ID' in os.environ:
            config.group_id = int(os.environ['GROUP_ID'])

        # create factory for platform specific classes
        try:
            factory_module = importlib.import_module(config['factory_module'])
            factory = getattr(factory_module, config['factory_class'])()
        except AttributeError:
            raise Exception("Requested factory module '{m}' or class '{c}' was not found."
                            .format(m=config['factory_module'],
                                    c=config['factory_class'])) from AttributeError
        # create config plugin for this platform
        config_plugin = factory.get_config_plugin_class()(config)
        config = config_plugin.get_config()

        opts, unknown_opts = _parse_opts_from_cli()
        log.set_level(debug=opts.debug)

        if opts.version:
            print((pbr.version.VersionInfo('nfvbench').version_string_with_vcs()))
            sys.exit(0)

        if opts.summary:
            with open(opts.summary) as json_data:
                result = json.load(json_data)
                if opts.user_label:
                    result['config']['user_label'] = opts.user_label
                print((NFVBenchSummarizer(result, fluent_logger)))
            sys.exit(0)

        # show default config in text/yaml format
        if opts.show_default_config:
            print((default_cfg.decode("utf-8")))
            sys.exit(0)

        # dump the contents of the trex log file
        if opts.show_trex_log:
            try:
                print(open('/tmp/trex.log').read(), end="")
            except FileNotFoundError:
                print("No TRex log file found!")
            sys.exit(0)

        # mask info logging in case of further config dump
        if opts.show_config or opts.show_pre_config:
            LOG.setLevel(log.logging.WARNING)

        config.name = ''
        if opts.config:
            # do not check extra_specs in flavor as it can contain any key/value pairs
            # the same principle applies also to the optional user_info open property
            whitelist_keys = ['extra_specs', 'user_info']
            # override default config options with start config at path parsed from CLI
            # check if it is an inline yaml/json config or a file name
            if os.path.isfile(opts.config):
                LOG.info('Loading configuration file: %s', opts.config)
                config = config_load(opts.config, config, whitelist_keys)
                config.name = os.path.basename(opts.config)
            else:
                LOG.info('Loading configuration string: %s', opts.config)
                config = config_loads(opts.config, config, whitelist_keys)

        # show current config in json format (before CLI overriding)
        if opts.show_pre_config:
            print((json.dumps(config, sort_keys=True, indent=4)))
            sys.exit(0)

        # setup the fluent logger as soon as possible right after the config plugin is called,
        # if there is any logging or result tag is set then initialize the fluent logger
        for fluentd in config.fluentd:
            if fluentd.logging_tag or fluentd.result_tag:
                fluent_logger = FluentLogHandler(config.fluentd)
                LOG.addHandler(fluent_logger)
                break

        # traffic profile override options
        override_custom_traffic(config, opts.frame_sizes, opts.unidir)

        # Copy over some of the cli options that are used in config.
        # This explicit copy is sometimes necessary
        # because some early evaluation depends on them
        # and cannot wait for _update_config() coming further.
        # It is good practice then to set them to None (<=> done)
        # and even required if a specific conversion is performed here
        # that would be corrupted by a default update (simple copy).
        # On the other hand, some excessive assignments have been removed
        # from here, since the _update_config() procedure does them well.

        config.generator_profile = opts.generator_profile
        if opts.sriov is not None:
            config.sriov = True
            opts.sriov = None
        if opts.log_file is not None:
            config.log_file = opts.log_file
            opts.log_file = None
        if opts.user_id is not None:
            config.user_id = opts.user_id
            opts.user_id = None
        if opts.group_id is not None:
            config.group_id = opts.group_id
            opts.group_id = None
        if opts.service_chain is not None:
            config.service_chain = opts.service_chain
            opts.service_chain = None
        if opts.hypervisor is not None:
            # can be any of 'comp1', 'nova:', 'nova:comp1'
            config.compute_nodes = opts.hypervisor
            opts.hypervisor = None
        if opts.debug_mask is not None:
            config.debug_mask = opts.debug_mask
            opts.debug_mask = None

        # convert 'user_info' opt from json string to dictionnary
        # and merge the result with the current config dictionnary
        if opts.user_info is not None:
            for user_info_json in opts.user_info:
                user_info_dict = json.loads(user_info_json)
                if config.user_info:
                    config.user_info = config.user_info + user_info_dict
                else:
                    config.user_info = user_info_dict
            opts.user_info = None

        # port to port loopback (direct or through switch)
        # we accept the following syntaxes for the CLI argument
        #   'false'   : mode not enabled
        #   'true'    : mode enabled with currently defined vlan IDs
        #   'no-tag'  : mode enabled with no vlan tagging
        #   <vlan IDs>: mode enabled using the given (pair of) vlan ID lists
        #     - If present, a '_' char will separate left an right ports lists
        #         e.g. 'a_x'         => vlans: [[a],[x]]
        #              'a,b,c_x,y,z' =>        [[a,b,c],[x,y,z]]
        #     - Otherwise the given vlan ID list applies to both sides
        #         e.g. 'a'           => vlans: [[a],[a]]
        #              'a,b'         =>        [[a,b],[a,b]]
        #     - Vlan lists size needs to be at least the actual SCC value
        #     - Unless overriden in CLI opts, config.service_chain_count
        #       is adjusted to the size of the VLAN ID lists given here.

        if opts.l2_loopback is not None:
            arg_pair = opts.l2_loopback.lower().split('_')
            if arg_pair[0] == 'false':
                config.l2_loopback = False
            else:
                config.l2_loopback = True
                if config.service_chain != ChainType.EXT:
                    LOG.info('Changing service chain type to EXT')
                    config.service_chain = ChainType.EXT
                if not config.no_arp:
                    LOG.info('Disabling ARP')
                    config.no_arp = True
                if arg_pair[0] == 'true':
                    pass
                else:
                    # here explicit (not)tagging is not CLI overridable
                    opts.vlan_tagging = None
                    if arg_pair[0] == 'no-tag':
                        config.vlan_tagging = False
                    else:
                        config.vlan_tagging = True
                        if len(arg_pair) == 1 or not arg_pair[1]:
                            arg_pair = [arg_pair[0], arg_pair[0]]
                        vlans = [[], []]

                        def append_vlan(port, vlan_id):
                            # a vlan tag value must be in [0..4095]
                            if vlan_id not in range(0, 4096):
                                raise ValueError
                            vlans[port].append(vlan_id)
                        try:
                            for port in [0, 1]:
                                vlan_ids = arg_pair[port].split(',')
                                for vlan_id in vlan_ids:
                                    append_vlan(port, int(vlan_id))
                            if len(vlans[0]) != len(vlans[1]):
                                raise ValueError
                        except ValueError:
                            # at least one invalid tag => no tagging
                            config.vlan_tagging = False
                        if config.vlan_tagging:
                            config.vlans = vlans
                            # force service chain count if not CLI overriden
                            if opts.service_chain_count is None:
                                config.service_chain_count = len(vlans[0])
            opts.l2_loopback = None

        if config.use_sriov_middle_net is None:
            config.use_sriov_middle_net = False
        if opts.use_sriov_middle_net is not None:
            config.use_sriov_middle_net = opts.use_sriov_middle_net
            opts.use_sriov_middle_net = None
        if (config.use_sriov_middle_net and (
                (not config.sriov) or (config.service_chain != ChainType.PVVP))):
            raise Exception("--use-sriov-middle-net is only valid for PVVP with SRIOV")

        if config.sriov and config.service_chain != ChainType.EXT:
            # if sriov is requested (does not apply to ext chains)
            # make sure the physnet names are specified
            check_physnet("left", config.internal_networks.left)
            check_physnet("right", config.internal_networks.right)
            if config.service_chain == ChainType.PVVP and config.use_sriov_middle_net:
                check_physnet("middle", config.internal_networks.middle)

        # update the config in the config plugin as it might have changed
        # in a copy of the dict (config plugin still holds the original dict)
        config_plugin.set_config(config)

        if opts.status or opts.cleanup or opts.force_cleanup:
            status_cleanup(config, opts.cleanup, opts.force_cleanup)

        # add file log if requested
        if config.log_file:
            log.add_file_logger(config.log_file)
            # possibly change file ownership
            uid = config.user_id
            gid = config.group_id
            if gid is None:
                gid = uid
            if uid is not None:
                os.chown(config.log_file, uid, gid)

        openstack_spec = config_plugin.get_openstack_spec() if config.openrc_file \
            else None

        nfvbench_instance = NFVBench(config, openstack_spec, config_plugin, factory)

        if opts.server:
            server = WebServer(nfvbench_instance, fluent_logger)
            try:
                port = int(opts.port)
            except ValueError:
                server.run(host=opts.host)
            else:
                server.run(host=opts.host, port=port)
            # server.run() should never return
        else:
            dry_run = opts.show_config
            with utils.RunLock():
                run_summary_required = True
                if unknown_opts:
                    err_msg = 'Unknown options: ' + ' '.join(unknown_opts)
                    LOG.error(err_msg)
                    raise Exception(err_msg)

                # remove unfilled values
                opts = {k: v for k, v in list(vars(opts).items()) if v is not None}
                # get CLI args
                params = ' '.join(str(e) for e in sys.argv[1:])
                result = nfvbench_instance.run(opts, params, dry_run=dry_run)
                if 'error_message' in result:
                    raise Exception(result['error_message'])

                if 'result' in result and result['status']:
                    nfvbench_instance.save(result['result'])
                    nfvbench_instance.prepare_summary(result['result'])
    except Exception as exc:
        run_summary_required = True
        LOG.error({
            'status': NFVBench.STATUS_ERROR,
            'error_message': traceback.format_exc()
        })
        print((str(exc)))
    finally:
        if fluent_logger:
            # only send a summary record if there was an actual nfvbench run or
            # if an error/exception was logged.
            fluent_logger.send_run_summary(run_summary_required)


if __name__ == '__main__':
    main()
