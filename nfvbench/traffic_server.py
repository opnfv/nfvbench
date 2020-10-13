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

import os
import subprocess
import yaml

from .log import LOG


class TrafficServerException(Exception):
    pass

class TrafficServer(object):
    """Base class for traffic servers."""

class TRexTrafficServer(TrafficServer):
    """Creates configuration file for TRex and runs server."""

    def __init__(self, trex_base_dir='/opt/trex'):
        contents = os.listdir(trex_base_dir)
        # only one version of TRex should be supported in container
        assert len(contents) == 1
        self.trex_dir = os.path.join(trex_base_dir, contents[0])

    def __apply_trex_patches(self):
        parent_dir = os.path.dirname(os.path.realpath(__file__))
        patches_dir = os.path.join(parent_dir, "trex_patches")
        patches = os.listdir(patches_dir)
        for patch in patches:
            patch = os.path.join(patches_dir, patch)
            command = (
                "patch --directory=" + self.trex_dir + " --strip=0"
                " --forward --no-backup-if-mismatch --reject-file=-"
                " --force --input=" + patch + " >&-")
            os.system(command)

    def run_server(self, generator_config, filename='/etc/trex_cfg.yaml'):
        """Run TRex server for specified traffic profile.

        :param traffic_profile: traffic profile object based on config file
        :param filename: path where to save TRex config file
        """
        # in order to allow for customized behaviors, let's apply some patches
        # this scheme keeps acceptable since we have only simple modifications
        self.__apply_trex_patches()
        cfg = self.__save_config(generator_config, filename)
        cores = generator_config.cores
        vtep_vlan = generator_config.gen_config.get('vtep_vlan')
        sw_mode = "--software" if generator_config.software_mode else ""
        vlan_opt = "--vlan" if (generator_config.vlan_tagging or vtep_vlan) else ""
        if generator_config.mbuf_factor:
            mbuf_opt = "--mbuf-factor " + str(generator_config.mbuf_factor)
        else:
            mbuf_opt = ""
        hdrh_opt = "--hdrh" if generator_config.hdrh else ""
        # --unbind-unused-ports: for NIC that have more than 2 ports such as Intel X710
        # this will instruct trex to unbind all ports that are unused instead of
        # erroring out with an exception (i40e only)
        # Try: --ignore-528-issue
        # -> neither unbind nor exit with error just proceed, cause it might work!
        # Note that force unbinding is probably a bad choice:
        # we can't assume that other ports are "unused".
        # The default behaviour - exit - is indeed a safer option
        # that tells then which ports should be unbound.
        i40e_opt = (
            "--ignore-528-issue" if generator_config.config.i40e_mixed == 'ignore' else
            "--unbind-unused-ports" if generator_config.config.i40e_mixed == 'unbind' else "")
        cmd = ['nohup', '/bin/bash', '-c',
               './t-rex-64 -i -c {} --iom 0 --no-scapy-server '
               '--close-at-end {} {} {} '
               '{} {} --cfg {} &> /tmp/trex.log & disown'.format(cores, sw_mode,
                                                                 i40e_opt,
                                                                 vlan_opt,
                                                                 hdrh_opt,
                                                                 mbuf_opt, cfg)]
        LOG.info(' '.join(cmd))
        subprocess.Popen(cmd, cwd=self.trex_dir)
        LOG.info('TRex server is running...')

    def __load_config(self, filename):
        result = {}
        if os.path.exists(filename):
            with open(filename, 'r') as stream:
                try:
                    result = yaml.safe_load(stream)
                except yaml.YAMLError as exc:
                    print(exc)
        return result

    def __save_config(self, generator_config, filename):
        result = self.__prepare_config(generator_config)
        yaml.safe_load(result)
        if os.path.exists(filename):
            os.remove(filename)
        with open(filename, 'w') as f:
            f.write(result)
        return filename

    def __prepare_config(self, generator_config):
        ifs = ",".join([repr(pci) for pci in generator_config.pcis])

        # For consistency and stability reasons, the T-Rex server
        # should be forciby restarted each time the value of a
        # parameter, specified as one of the starting command line
        # arguments, has been modified since the last launch.
        # Hence we add some extra fields to the config file (nb_cores,
        # use_vlan) which will serve as a memory between runs -
        # while being actually ignored by the T-Rex server.

        result = """# Config generated by NFVbench
        - port_limit : 2
          version    : 2
          zmq_pub_port : {zmq_pub_port}
          zmq_rpc_port : {zmq_rpc_port}
          prefix       : {prefix}
          limit_memory : {limit_memory}
          nb_cores : {nb_cores}
          use_vlan : {use_vlan}
          interfaces : [{ifs}]""".format(zmq_pub_port=generator_config.zmq_pub_port,
                                         zmq_rpc_port=generator_config.zmq_rpc_port,
                                         prefix=generator_config.name,
                                         limit_memory=generator_config.limit_memory,
                                         nb_cores=generator_config.cores,
                                         use_vlan=generator_config.gen_config.get('vtep_vlan')
                                         or generator_config.vlan_tagging,
                                         ifs=ifs)

        if hasattr(generator_config, 'mbuf_64') and generator_config.mbuf_64:
            result += """
          memory       :
            mbuf_64           : {mbuf_64}""".format(mbuf_64=generator_config.mbuf_64)

        if self.__check_platform_config(generator_config):
            try:
                platform = """
          platform     :
            master_thread_id  : {master_thread_id}
            latency_thread_id : {latency_thread_id}
            dual_if:""".format(master_thread_id=generator_config.gen_config.platform.
                               master_thread_id,
                               latency_thread_id=generator_config.gen_config.platform.
                               latency_thread_id)
                result += platform

                for core in generator_config.gen_config.platform.dual_if:
                    threads = ""
                    try:
                        threads = ",".join([repr(thread) for thread in core.threads])
                    except TypeError:
                        LOG.warning("No threads defined for socket %s", core.socket)
                    core_result = """
                  - socket : {socket}
                    threads : [{threads}]""".format(socket=core.socket, threads=threads)
                    result += core_result
            except (KeyError, AttributeError):
                pass
        return result + "\n"

    def __check_platform_config(self, generator_config):
        return hasattr(generator_config.gen_config, 'platform') \
            and hasattr(generator_config.gen_config.platform, "master_thread_id") \
            and generator_config.gen_config.platform.master_thread_id is not None \
            and hasattr(generator_config.gen_config.platform, "latency_thread_id") \
            and generator_config.gen_config.platform.latency_thread_id is not None

    def check_config_updated(self, generator_config):
        existing_config = self.__load_config(filename='/etc/trex_cfg.yaml')
        new_config = yaml.safe_load(self.__prepare_config(generator_config))
        LOG.debug("Existing config: %s", existing_config)
        LOG.debug("New config: %s", new_config)
        if existing_config == new_config:
            return False
        return True
