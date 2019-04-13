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

#
# This is an example of python application controling a nfvbench server
# using the nfvbench client API.
# The nfvbench server must run in background using the --server option.
# Since HTML pages are not required, the path to pass to --server can be any directory on the host.
#
import argparse
import json
import sys

from client import NfvbenchClient


#
# At the CLI, the user can either:
# - pass an nfvbench configuration as a string (-c <config>)
# - pass an nfvbench configuration as a file name containing the
#   configuration (-f <config_file_path>)
# - or pass a test config (-e <config>) that will be echoed back by the server as is
#
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-f', '--file', dest='file',
                        action='store',
                        help='NFVbench config file to execute (json format)',
                        metavar='<config_file_path>')
    parser.add_argument('-c', '--config', dest='config',
                        action='store',
                        help='NFVbench config to execute (json format)',
                        metavar='<config>')
    parser.add_argument('-e', '--echo', dest='echo',
                        action='store',
                        help='NFVbench config to echo (json format)',
                        metavar='<config>')
    parser.add_argument('-t', '--timeout', dest='timeout',
                        default=900,
                        action='store',
                        help='time (seconds) to wait for NFVbench result',
                        metavar='<config>')
    parser.add_argument('url', help='nfvbench server url (e.g. http://10.0.0.1:5000)')
    opts = parser.parse_args()

    if not opts.file and not opts.config and not opts.echo:
        print('at least one of -f or -c or -e required')
        sys.exit(-1)

    nfvbench = NfvbenchClient(opts.url)
    # convert JSON into a dict
    try:
        timeout = int(opts.timeout)
        if opts.file:
            with open(opts.file) as fd:
                config = json.loads(fd.read())
                result = nfvbench.run_config(config, timeout=timeout)
        elif opts.config:
            config = json.loads(opts.config)
            result = nfvbench.run_config(config, timeout=timeout)
        elif opts.echo:
            config = json.loads(opts.echo)
            result = nfvbench.echo_config(config, timeout=timeout)
        print('Result:', result)
    except ValueError as ex:
        print('Input configuration is invalid: ' + str(ex))
        print()


if __name__ == "__main__":
    main()
