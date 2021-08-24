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
import time
from math import gcd
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
from nfvbench.traffic_gen.traffic_utils import multiplier_map
from novaclient.exceptions import NotFound

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
                     flow_count, frame_sizes, user_id=None, group_id=None):
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
            with open(file_path, 'w', encoding="utf-8") as jfp:
                json.dump(result,
                          jfp,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '),
                          default=lambda obj: obj.to_json())
                # possibly change file ownership
                if group_id is None:
                    group_id = user_id
                if user_id is not None:
                    os.chown(file_path, user_id, group_id)


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
        regex = r"(?<=SlotID:{}).*?(....:..:..\..)".format(nic_slot)
        match = re.search(regex, dmidecode.decode('utf-8'), flags=re.DOTALL)
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
        with subprocess.Popen(['python', 'dpdk_setup_ports.py', '-s'],
                              cwd=trex_dir,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            devices, _ = process.communicate()
    except Exception:
        devices = ''

    for driver in ['i40e', 'ixgbe']:
        matches = re.findall(regex.format(hx=hx, driver=driver), devices.decode("utf-8"))
        if not matches:
            continue

        matches.sort()
        device_list = list(x[0].split('.')[0] for x in matches)
        device_ports_list = {i: {'ports': device_list.count(i)} for i in device_list}
        for port in matches:
            intf_name = glob.glob("/sys/bus/pci/devices/%s/net/*" % port[0])
            if intf_name:
                intf_name = intf_name[0][intf_name[0].rfind('/') + 1:]
                with subprocess.Popen(['ip', '-o', '-d', 'link', 'show', intf_name],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) as process:
                    intf_info, _ = process.communicate()
                if re.search('team_slave|bond_slave', intf_info.decode("utf-8")):
                    device_ports_list[port[0].split('.')[0]]['busy'] = True
        for port in matches:
            if not device_ports_list[port[0].split('.')[0]].get('busy'):
                pcis.append(port[1])
            if len(pcis) == 2:
                break

    return pcis


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
        raise Exception("Unknown flow count format '{}'".format(input_fc)) from ValueError

    return flow_count * multiplier


def cast_integer(value):
    # force 0 value if NaN value from TRex to avoid error in JSON result parsing
    return int(value) if not isnan(value) else 0


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
        except (OSError, IOError) as e:
            raise Exception('Other NFVbench process is running. Please wait') from e

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

        # Try to remove the lock file, but don't try too hard because it is unnecessary.
        try:
            os.unlink(self._path)
        except (OSError, IOError):
            pass


def get_divisors(n):
    for i in range(1, int(n / 2) + 1):
        if n % i == 0:
            yield i
    yield n


def lcm(a, b):
    """
    Calculate the maximum possible value for both IP and ports,
    eventually for maximum possible flow.
    """
    if a != 0 and b != 0:
        lcm_value = a * b // gcd(a, b)
        return lcm_value
    raise TypeError(" IP size or port range can't be zero !")


def find_tuples_equal_to_lcm_value(a, b, lcm_value):
    """
    Find numbers from two list matching a LCM value.
    """
    for x in a:
        for y in b:
            if lcm(x, y) == lcm_value:
                yield (x, y)


def find_max_size(max_size, tuples, flow):
    if tuples:
        if max_size > tuples[-1][0]:
            max_size = tuples[-1][0]
            return int(max_size)
        if max_size > tuples[-1][1]:
            max_size = tuples[-1][1]
            return int(max_size)

    for i in range(max_size, 1, -1):
        if flow % i == 0:
            return int(i)
    return 1


def delete_server(nova_client, server):
    try:
        LOG.info('Deleting instance %s...', server.name)
        nova_client.servers.delete(server.id)
    except Exception:
        LOG.exception("Instance %s deletion failed", server.name)


def instance_exists(nova_client, server):
    try:
        nova_client.servers.get(server.id)
    except NotFound:
        return False
    return True


def waiting_servers_deletion(nova_client, servers):
    LOG.info('    Waiting for %d instances to be fully deleted...', len(servers))
    retry_count = 15 + len(servers) * 5
    while True:
        retry_count -= 1
        servers = [server for server in servers if instance_exists(nova_client, server)]
        if not servers:
            break

        if retry_count:
            LOG.info('    %d yet to be deleted by Nova, retries left=%d...',
                     len(servers), retry_count)
            time.sleep(2)
        else:
            LOG.warning(
                '    instance deletion verification time-out: %d still not deleted',
                len(servers))
            break
