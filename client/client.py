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

import requests
import time


class TimeOutException(Exception):
    pass


class NfvbenchException(Exception):
    pass


class NfvbenchClient(object):
    """Python client class to control a nfvbench server

    The nfvbench server must run in background using the --server option.
    """
    def __init__(self, nfvbench_url):
        """Client class to send requests to the nfvbench server

        Args:
            nfvbench_url: the URL of the nfvbench server (e.g. 'http://127.0.0.1:7555')
        """
        self.url = nfvbench_url

    def http_get(self, command, config):
        url = self.url + '/' + command
        res = requests.get(url, json=config)
        if res.ok:
            return res.json()
        res.raise_for_status()

    def http_post(self, command, config):
        url = self.url + '/' + command
        res = requests.post(url, json=config)
        if res.ok:
            return res.json()
        res.raise_for_status()

    def echo_config(self, config, timeout=100):
        """Send an echo event to the nfvbench server with some dummy config and expect the
        config to be sent back right away.

        Args:
            config: some dummy configuration - must be a valid dict
            timeout: how long to wait in seconds or 0 to return immediately,
                     defaults to 100 seconds

        Returns:
            The config as passed as a dict or None if timeout passed is 0

        Raises:
            NfvbenchException: the execution of the passed configuration failed,
                               the body of the exception
                               containes the description of the failure.
            TimeOutException: the request timed out (and might still being executed
                              by the server)
        """
        return self.http_get('echo', config)

    def run_config(self, config, timeout=300, poll_interval=5):
        """Request an nfvbench configuration to be executed by the nfvbench server.

        This function will block the caller until the request completes or the request times out.
        It can return immediately if timeout is set to 0.
        Note that running a configuration may take a while depending on the amount of work
        requested - so set the timeout value to an appropriate value.

        Args:
            config: the nfvbench configuration to execute - must be a valid dict with
                    valid nfvbench attributes
            timeout: how long to wait in seconds or 0 to return immediately,
                     defaults to 300 seconds
            poll_interval: seconds between polling (http only) - defaults to every 5 seconds

        Returns:
            The result of the nfvbench execution
            or None if timeout passed is 0
            The function will return as soon as the request is completed or when the
            timeout occurs (whichever is first).

        Raises:
            NfvbenchException: the execution of the passed configuration failed, the body of
                               the exception contains the description of the failure.
            TimeOutException: the request timed out but will still be executed by the server.
        """
        res = self.http_post('start_run', config)
        if res['status'] != 'PENDING':
            raise NfvbenchException(res['error_message'])

        # poll until request completes
        elapsed = 0
        while True:
            time.sleep(poll_interval)
            result = self.http_get('status', config)
            if result['status'] != 'PENDING':
                return result
            elapsed += poll_interval
            if elapsed >= timeout:
                raise TimeOutException()
