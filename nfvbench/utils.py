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

import glob
from math import isnan
import os
import re
import signal
import subprocess

import errno
import fcntl
from functools import wraps
import json
from .log import LOG


class TimeoutError(Exception):
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(_signum, _frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator


def save_json_result(result, json_file, std_json_path, service_chain, service_chain_count,
                     flow_count, frame_sizes):
    """Save results in json format file."""
    filepaths = []
    if json_file:
        filepaths.append(json_file)
    if std_json_path:
        name_parts = [service_chain, str(service_chain_count), str(flow_count)] + list(frame_sizes)
        filename = '-'.join(name_parts) + '.json'
        filepaths.append(os.path.join(std_json_path, filename))

    if filepaths:
        for file_path in filepaths:
            LOG.info('Saving results in json file: %s...', file_path)
            with open(file_path, 'w') as jfp:
                json.dump(result,
                          jfp,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '),
                          default=lambda obj: obj.to_json())


def byteify(data, ignore_dicts=False):
    # if this is a unicode string, return its string representation
    if isinstance(data, str):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [byteify(item, ignore_dicts=ignore_dicts) for item in data]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {byteify(key, ignore_dicts=ignore_dicts): byteify(value, ignore_dicts=ignore_dicts)
                for key, value in list(data.items())}
    # if it's anything else, return it in its original form
    return data


def dict_to_json_dict(record):
    return json.loads(json.dumps(record, default=lambda obj: obj.to_json()))


def get_intel_pci(nic_slot=None, nic_ports=None):
    """Returns two PCI address that will be used for NFVbench

    @param nic_slot: The physical PCIe slot number in motherboard
    @param nic_ports: Array of two integers indicating the ports to use on the NIC

    When nic_slot and nic_ports are both supplied, the function will just return
    the PCI addresses for them. The logic used is:
        (1) Run "dmidecode -t slot"
        (2) Grep for "SlotID:" with given nic_slot, and derive the bus address;
        (3) Based on given nic_ports, generate the pci addresses based on above
        base address;

    When either nic_slot or nic_ports is not supplied, the function will
    traverse all Intel NICs which use i40e or ixgbe driver, sorted by PCI
    address, and return first two available ports which are not bonded
    (802.11ad).
    """

    if nic_slot and nic_ports:
        dmidecode = subprocess.check_output(['dmidecode', '-t', 'slot'])
        regex = r"(?<=SlotID:%s).*?(....:..:..\..)" % nic_slot
        match = re.search(regex, dmidecode, flags=re.DOTALL)
        if not match:
            return None

        pcis = []
        # On some servers, the "Bus Address" returned by dmidecode is not the
        # base pci address of the NIC. So only keeping the bus part of the
        # address for better compability.
        bus = match.group(1)[:match.group(1).rindex(':') + 1] + "00."
        for port in nic_ports:
            pcis.append(bus + str(port))

        return pcis

    hx = r'[0-9a-fA-F]'
    regex = r'({hx}{{4}}:({hx}{{2}}:{hx}{{2}}\.{hx}{{1}})).*(drv={driver}|.*unused=.*{driver})'
    pcis = []
    try:
        trex_base_dir = '/opt/trex'
        contents = os.listdir(trex_base_dir)
        trex_dir = os.path.join(trex_base_dir, contents[0])
        process = subprocess.Popen(['python', 'dpdk_setup_ports.py', '-s'],
                                   cwd=trex_dir,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        devices, _ = process.communicate()
    except Exception:
        devices = ''

    for driver in ['i40e', 'ixgbe']:
        matches = re.findall(regex.format(hx=hx, driver=driver), devices)
        if not matches:
            continue

        matches.sort()
        for port in matches:
            intf_name = glob.glob("/sys/bus/pci/devices/%s/net/*" % port[0])
            if not intf_name:
                # Interface is not bind to kernel driver, so take it
                pcis.append(port[1])
            else:
                intf_name = intf_name[0][intf_name[0].rfind('/') + 1:]
                process = subprocess.Popen(['ip', '-o', '-d', 'link', 'show', intf_name],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                intf_info, _ = process.communicate()
                if not re.search('team_slave|bond_slave', intf_info):
                    pcis.append(port[1])

            if len(pcis) == 2:
                break

    return pcis


multiplier_map = {
    'K': 1000,
    'M': 1000000,
    'G': 1000000000
}


def parse_flow_count(flow_count):
    flow_count = str(flow_count)
    input_fc = flow_count
    multiplier = 1
    if flow_count[-1].upper() in multiplier_map:
        multiplier = multiplier_map[flow_count[-1].upper()]
        flow_count = flow_count[:-1]

    try:
        flow_count = int(flow_count)
    except ValueError:
        raise Exception("Unknown flow count format '{}'".format(input_fc))

    return flow_count * multiplier


def cast_integer(value):
    return int(value) if not isnan(value) else value


class RunLock(object):
    """
    Attempts to lock file and run current instance of NFVbench as the first,
    otherwise raises exception.
    """

    def __init__(self, path='/tmp/nfvbench.lock'):
        self._path = path
        self._fd = None

    def __enter__(self):
        try:
            self._fd = os.open(self._path, os.O_CREAT)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            raise Exception('Other NFVbench process is running. Please wait')

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

        # Try to remove the lock file, but don't try too hard because it is unnecessary.
        try:
            os.unlink(self._path)
        except (OSError, IOError):
            pass
