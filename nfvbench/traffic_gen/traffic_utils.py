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
from nfvbench.utils import multiplier_map

# IMIX frame size including the 4-byte FCS field
IMIX_L2_SIZES = [64, 594, 1518]
IMIX_RATIOS = [7, 4, 1]
# weighted average l2 frame size includng the 4-byte FCS
IMIX_AVG_L2_FRAME_SIZE = sum(
    [1.0 * imix[0] * imix[1] for imix in zip(IMIX_L2_SIZES, IMIX_RATIOS)]) / sum(IMIX_RATIOS)


def convert_rates(l2frame_size, rate, intf_speed):
    """Convert a given rate unit into the other rate units.

    l2frame_size: size of the L2 frame in bytes (includes 32-bit FCS) or 'IMIX'
    rate: a dict that has at least one of the following key:
          'rate_pps', 'rate_bps', 'rate_percent'
          with the corresponding input value
    intf_speed: the line rate speed in bits per second
    """
    avg_packet_size = get_average_packet_size(l2frame_size)
    if 'rate_pps' in rate:
        # input = packets/sec
        initial_rate_type = 'rate_pps'
        pps = rate['rate_pps']
        bps = pps_to_bps(pps, avg_packet_size)
        load = bps_to_load(bps, intf_speed)
    elif 'rate_bps' in rate:
        # input = bits per second
        initial_rate_type = 'rate_bps'
        bps = rate['rate_bps']
        load = bps_to_load(bps, intf_speed)
        pps = bps_to_pps(bps, avg_packet_size)
    elif 'rate_percent' in rate:
        # input = percentage of the line rate (between 0.0 and 100.0)
        initial_rate_type = 'rate_percent'
        load = rate['rate_percent']
        bps = load_to_bps(load, intf_speed)
        pps = bps_to_pps(bps, avg_packet_size)
    else:
        raise Exception('Traffic config needs to have a rate type key')
    return {
        'initial_rate_type': initial_rate_type,
        'rate_pps': int(float(pps)),
        'rate_percent': load,
        'rate_bps': int(float(bps))
    }


def get_average_packet_size(l2frame_size):
    """Retrieve the average L2 frame size

    l2frame_size: an L2 frame size in bytes (including FCS) or 'IMIX'
    return: average l2 frame size inlcuding the 32-bit FCS
    """
    if l2frame_size.upper() == 'IMIX':
        return IMIX_AVG_L2_FRAME_SIZE
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

        return sum([x[0] * x[1] for x in zip(weight, count)]) / sum(weight)
    return float('nan')

def _get_bitmath_rate(rate_bps):
    rate = rate_bps.replace('ps', '').strip()
    bitmath_rate = bitmath.parse_string(rate)
    if bitmath_rate.bits <= 0:
        raise Exception('%s is out of valid range' % rate_bps)
    return bitmath_rate

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
        rate_pps = int(float(rate_pps.strip()) * multiplier)
        if rate_pps <= 0:
            raise Exception('%s is out of valid range' % rate_str)
        return {'rate_pps': str(rate_pps)}
    if rate_str.endswith('ps'):
        rate = rate_str.replace('ps', '').strip()
        bit_rate = bitmath.parse_string(rate).bits
        if bit_rate <= 0:
            raise Exception('%s is out of valid range' % rate_str)
        return {'rate_bps': str(int(bit_rate))}
    if rate_str.endswith('%'):
        rate_percent = float(rate_str.replace('%', '').strip())
        if rate_percent <= 0 or rate_percent > 100.0:
            raise Exception('%s is out of valid range (must be 1-100%%)' % rate_str)
        return {'rate_percent': str(rate_percent)}
    raise Exception('Unknown rate string format %s' % rate_str)

def get_load_from_rate(rate_str, avg_frame_size=64, line_rate='10Gbps'):
    '''From any rate string (with unit) return the corresponding load (in % unit)

    :param str rate_str: the rate to convert - must end with a unit (e.g. 1Mpps, 30%, 1Gbps)
    :param int avg_frame_size: average frame size in bytes (needed only if pps is given)
    :param str line_rate: line rate ending with bps unit (e.g. 1Mbps, 10Gbps) is the rate that
                      corresponds to 100% rate
    :return float: the corresponding rate in % of line rate
    '''
    rate_dict = parse_rate_str(rate_str)
    if 'rate_percent' in rate_dict:
        return float(rate_dict['rate_percent'])
    lr_bps = _get_bitmath_rate(line_rate).bits
    if 'rate_bps' in rate_dict:
        bps = int(rate_dict['rate_bps'])
    else:
        # must be rate_pps
        pps = rate_dict['rate_pps']
        bps = pps_to_bps(pps, avg_frame_size)
    return bps_to_load(bps, lr_bps)

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
    if 'rate_bps' in rate:
        bps = rate['rate_bps']
        return '{}bps'.format(bps)
    if 'rate_percent' in rate:
        load = rate['rate_percent']
        return '{}%'.format(load)
    assert False
    # avert pylint warning
    return None


def nan_replace(d):
    """Replaces every occurence of 'N/A' with float nan."""
    for k, v in d.items():
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
    blocks = [mac[x:x + 2] for x in range(0, len(mac), 2)]
    return ':'.join(blocks)
