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


import bitmath
from traffic_base import AbstractTrafficGenerator


def convert_rates(l2frame_size, rate, intf_speed):
    avg_packet_size = get_average_packet_size(l2frame_size)
    if 'rate_pps' in rate:
        initial_rate_type = 'rate_pps'
        pps = rate['rate_pps']
        bps = pps_to_bps(pps, avg_packet_size)
        load = bps_to_load(bps, intf_speed)
    elif 'rate_bps' in rate:
        initial_rate_type = 'rate_bps'
        bps = rate['rate_bps']
        load = bps_to_load(bps, intf_speed)
        pps = bps_to_pps(bps, avg_packet_size)
    elif 'rate_percent' in rate:
        initial_rate_type = 'rate_percent'
        load = rate['rate_percent']
        bps = load_to_bps(load, intf_speed)
        pps = bps_to_pps(bps, avg_packet_size)
    else:
        raise Exception('Traffic config needs to have a rate type key')

    return {
        'initial_rate_type': initial_rate_type,
        'rate_pps': pps,
        'rate_percent': load,
        'rate_bps': bps
    }


def get_average_packet_size(l2frame_size):
    if l2frame_size.upper() == 'IMIX':
        return AbstractTrafficGenerator.imix_avg_l2_size
    else:
        return float(l2frame_size)


def load_to_bps(load_percentage, intf_speed):
    return float(load_percentage) / 100.0 * intf_speed


def bps_to_load(bps, intf_speed):
    return float(bps) / intf_speed * 100.0


def bps_to_pps(bps, avg_packet_size):
    return float(bps) / (avg_packet_size + 20.0) / 8


def pps_to_bps(pps, avg_packet_size):
    return float(pps) * (avg_packet_size + 20.0) * 8


def weighted_avg(weight, count):
    if sum(weight):
        return sum(map(lambda x: x[0] * x[1], zip(weight, count))) / sum(weight)
    else:
        return float('nan')

multiplier_map = {
    'K': 1000,
    'M': 1000000,
    'G': 1000000000
}

def parse_rate_str(rate_str):
    if rate_str.endswith('pps'):
        rate_pps = rate_str[:-3]
        if not rate_pps:
            raise Exception('%s is missing a numeric value' % rate_str)
        try:
            multiplier = multiplier_map[rate_pps[-1].upper()]
            rate_pps = rate_pps[:-1]
        except KeyError:
            multiplier = 1
        rate_pps = int(rate_pps.strip()) * multiplier
        if rate_pps <= 0:
            raise Exception('%s is out of valid range' % rate_str)
        return {'rate_pps': str(rate_pps)}
    elif rate_str.endswith('ps'):
        rate = rate_str.replace('ps', '').strip()
        bit_rate = bitmath.parse_string(rate).bits
        if bit_rate <= 0:
            raise Exception('%s is out of valid range' % rate_str)
        return {'rate_bps': str(int(bit_rate))}
    elif rate_str.endswith('%'):
        rate_percent = float(rate_str.replace('%', '').strip())
        if rate_percent <= 0 or rate_percent > 100.0:
            raise Exception('%s is out of valid range (must be 1-100%%)' % rate_str)
        return {'rate_percent': str(rate_percent)}
    else:
        raise Exception('Unknown rate string format %s' % rate_str)


def divide_rate(rate, divisor):
    if 'rate_pps' in rate:
        key = 'rate_pps'
        value = int(rate[key])
    elif 'rate_bps' in rate:
        key = 'rate_bps'
        value = int(rate[key])
    else:
        key = 'rate_percent'
        value = float(rate[key])
    value /= divisor
    rate = dict(rate)
    rate[key] = str(value) if value else str(1)
    return rate


def to_rate_str(rate):
    if 'rate_pps' in rate:
        pps = rate['rate_pps']
        return '{}pps'.format(pps)
    elif 'rate_bps' in rate:
        bps = rate['rate_bps']
        return '{}bps'.format(bps)
    elif 'rate_percent' in rate:
        load = rate['rate_percent']
        return '{}%'.format(load)
    else:
        assert False


def nan_replace(d):
    """Replaces every occurence of 'N/A' with float nan."""
    for k, v in d.iteritems():
        if isinstance(v, dict):
            nan_replace(v)
        elif v == 'N/A':
            d[k] = float('nan')


def mac_to_int(mac):
    """Converts MAC address to integer representation."""
    return int(mac.translate(None, ":.- "), 16)


def int_to_mac(i):
    """Converts integer representation of MAC address to hex string."""
    mac = format(i, 'x').zfill(12)
    blocks = [mac[x:x + 2] for x in xrange(0, len(mac), 2)]
    return ':'.join(blocks)
