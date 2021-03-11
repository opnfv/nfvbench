#!/usr/bin/env python
# Copyright 2021 Orange
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

from functools import reduce

from behave import given
from behave import when
from behave import then
from requests import RequestException
from retry import retry
import json
import requests
import subprocess
from subprocess import DEVNULL

from nfvbench.summarizer import Formatter
from nfvbench.traffic_gen.traffic_utils import parse_rate_str

STATUS_ERROR = "ERROR"

STATUS_OK = "OK"


"""Given steps."""


@given('PROJECT_NAME: {project_name}')
def override_xtesting_project_name(context, project_name):
    context.data['PROJECT_NAME'] = project_name


@given('TEST_DB_EXT_URL: {test_db_ext_url}')
def override_xtesting_test_db_ext_url(context, test_db_ext_url):
    context.data['TEST_DB_EXT_URL'] = test_db_ext_url


@given('TEST_DB_URL: {test_db_url}')
def override_xtesting_test_db_url(context, test_db_url):
    context.data['TEST_DB_URL'] = test_db_url
    context.data['BASE_TEST_DB_URL'] = context.data['TEST_DB_URL'].replace('results', '')


@given('INSTALLER_TYPE: {installer_type}')
def override_xtesting_installer_type(context, installer_type):
    context.data['INSTALLER_TYPE'] = installer_type


@given('DEPLOY_SCENARIO: {deploy_scenario}')
def override_xtesting_deploy_scenario(context, deploy_scenario):
    context.data['DEPLOY_SCENARIO'] = deploy_scenario


@given('NODE_NAME: {node_name}')
def override_xtesting_node_name(context, node_name):
    context.data['NODE_NAME'] = node_name


@given('BUILD_TAG: {build_tag}')
def override_xtesting_build_tag(context, build_tag):
    context.data['BUILD_TAG'] = build_tag


@given('NFVbench config from file: {config_path}')
def init_config(context, config_path):
    context.data['config'] = config_path


@given('a JSON NFVbench config')
def init_config_from_json(context):
    context.json.update(json.loads(context.text))


@given('log file: {log_file_path}')
def log_config(context, log_file_path):
    context.json['log_file'] = log_file_path


@given('json file: {json_file_path}')
def json_config(context, json_file_path):
    context.json['json'] = json_file_path


@given('no clean up')
def add_no_clean_up_flag(context):
    context.json['no_cleanup'] = 'true'


@given('TRex is restarted')
def add_restart(context):
    context.json['restart'] = 'true'


@given('{label} label')
def add_label(context, label):
    context.json['label'] = label


@given('{frame_size} frame size')
def add_frame_size(context, frame_size):
    context.json['frame_sizes'] = [frame_size]


@given('{flow_count} flow count')
def add_flow_count(context, flow_count):
    context.json['flow_count'] = flow_count


@given('{rate} rate')
def add_rate(context, rate):
    context.json['rate'] = rate


@given('{duration} sec run duration')
def add_duration(context, duration):
    context.json['duration_sec'] = duration


@given('{percentage_rate} rate of previous scenario')
def add_percentage_rate(context, percentage_rate):
    context.percentage_rate = percentage_rate
    rate = percentage_previous_rate(context, percentage_rate)
    context.json['rate'] = rate


"""When steps."""


@when('NFVbench API is ready')
@when('NFVbench API is ready on host {host_ip}')
@when('NFVbench API is ready on host {host_ip} and port {port:d}')
def start_server(context, host_ip="127.0.0.1", port=7555):
    context.host_ip = host_ip
    context.port = port
    try:
        # check if API is already available
        requests.get(
            "http://{host_ip}:{port}/status".format(host_ip=context.host_ip, port=context.port))
    except RequestException:
        cmd = ["nfvbench", "-c", context.data['config'], "--server"]
        if host_ip != "127.0.0.1":
            cmd.append("--host")
            cmd.append(host_ip)
        if port != 7555:
            cmd.append("--port")
            cmd.append(port)

        subprocess.Popen(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

    test_nfvbench_api(context)


"""Then steps."""


@then('run is started and waiting for result')
@then('{repeat:d} runs are started and waiting for maximum result')
def step_impl(context, repeat=1):
    results = []
    if 'json' not in context.json:
        context.json['json'] = '/var/lib/xtesting/results/' + context.CASE_NAME + \
                               '/nfvbench-' + context.tag + '-fs_' + \
                               context.json['frame_sizes'][0] + '-fc_' + \
                               context.json['flow_count'] + '-rate_' + \
                               context.json['rate'] + '.json'
    json_base_name = context.json['json']
    for i in range(repeat):
        if repeat > 1:
            context.json['json'] = json_base_name.strip('.json') + '-' + str(i) + '.json'

        url = "http://{ip}:{port}/start_run".format(ip=context.host_ip, port=context.port)
        payload = json.dumps(context.json)
        r = requests.post(url, data=payload, headers={'Content-Type': 'application/json'})
        context.request_id = json.loads(r.text)["request_id"]
        assert r.status_code == 200
        result = wait_result(context)
        results.append(result)
        assert result["status"] == STATUS_OK


    context.result = reduce(
        lambda x, y: x if extract_value(x, "total_tx_rate") > extract_value(y,
                                                                            "total_tx_rate") else y,
        results)

    total_tx_rate = extract_value(context.result, "total_tx_rate")
    context.rates[context.json['frame_sizes'][0] + '_' + context.json['flow_count']] = total_tx_rate
    overall = extract_value(context.result, "overall")
    avg_delay_usec = extract_value(overall, "avg_delay_usec")
    # create a synthesis with offered pps and latency values
    context.synthesis['total_tx_rate'] = total_tx_rate
    context.synthesis['avg_delay_usec'] = avg_delay_usec


@then('extract offered rate result')
def save_rate_result(context):
    total_tx_rate = extract_value(context.result, "total_tx_rate")
    context.rates[context.json['frame_sizes'][0] + '_' + context.json['flow_count']] = total_tx_rate


@then('verify throughput result is in same range as the previous result')
@then('verify throughput result is greater than {threshold} of the previous result')
def get_throughput_result_from_database(context, threshold='90%'):
    last_result = get_last_result(context)

    if last_result:
        compare_throughput_values(context, last_result, threshold)


@then('verify latency result is in same range as the previous result')
@then('verify latency result is greater than {threshold} of the previous result')
def get_latency_result_from_database(context, threshold='90%'):
    last_result = get_last_result(context)

    if last_result:
        compare_latency_values(context, last_result, threshold)

@then(
    'verify result is in [{min_reference_value}pps, {max_reference_value}pps] range for throughput')
def compare_throughput_pps_result_with_range_values(context, min_reference_value,
                                                    max_reference_value):
    context.unit = 'pps'
    reference_values = [min_reference_value + 'pps', max_reference_value + 'pps']
    throughput_comparison(context, reference_values=reference_values)


@then(
    'verify result is in [{min_reference_value}bps, {max_reference_value}bps] range for throughput')
def compare_throughput_bps_result_with_range_values(context, min_reference_value,
                                                    max_reference_value):
    context.unit = 'bps'
    reference_values = [min_reference_value + 'bps', max_reference_value + 'bps']
    throughput_comparison(context, reference_values=reference_values)


@then('verify result is in {reference_values} range for latency')
def compare_result_with_range_values(context, reference_values):
    latency_comparison(context, reference_values=reference_values)


@then('verify throughput result is in same range as the characterization result')
@then('verify throughput result is greater than {threshold} of the characterization result')
def get_characterization_throughput_result_from_database(context, threshold='90%'):
    last_result = get_last_result(context, True)
    if not last_result:
        raise AssertionError("No characterization result found.")
    compare_throughput_values(context, last_result, threshold)


@then('verify latency result is in same range as the characterization result')
@then('verify latency result is greater than {threshold} of the characterization result')
def get_characterization_latency_result_from_database(context, threshold='90%'):
    last_result = get_last_result(context, True)
    if not last_result:
        raise AssertionError("No characterization result found.")
    compare_latency_values(context, last_result, threshold)

@then('push result to database')
def push_result_database(context):
    if context.tag == "latency":
        # override input rate value with percentage one to avoid no match
        # if pps is not accurate with previous one
        context.json["rate"] = context.percentage_rate
    json_result = {"synthesis": context.synthesis, "input": context.json, "output": context.result}

    if context.tag not in context.results:
        context.results[context.tag] = [json_result]
    else:
        context.results[context.tag].append(json_result)


"""Utils methods."""


@retry(AssertionError, tries=10, delay=5.0, logger=None)
def test_nfvbench_api(context):
    try:
        r = requests.get("http://{ip}:{port}/status".format(ip=context.host_ip, port=context.port))
        assert r.status_code == 200
        assert json.loads(r.text)["error_message"] == "no pending NFVbench run"
    except RequestException as exc:
        raise AssertionError("Fail to access NFVbench API") from exc


@retry(AssertionError, tries=1000, delay=2.0, logger=None)
def wait_result(context):
    r = requests.get("http://{ip}:{port}/status".format(ip=context.host_ip, port=context.port))
    context.raw_result = r.text
    result = json.loads(context.raw_result)
    assert r.status_code == 200
    assert result["status"] == STATUS_OK or result["status"] == STATUS_ERROR
    return result


def percentage_previous_rate(context, rate):
    previous_rate = context.rates[context.json['frame_sizes'][0] + '_' + context.json['flow_count']]

    if rate.endswith('%'):
        rate_percent = convert_percentage_str_to_float(rate)
        return str(int(previous_rate * rate_percent)) + 'pps'
    raise Exception('Unknown rate string format %s' % rate)


def convert_percentage_str_to_float(percentage):
    float_percent = float(percentage.replace('%', '').strip())
    if float_percent <= 0 or float_percent > 100.0:
        raise Exception('%s is out of valid range (must be 1-100%%)' % percentage)
    return float_percent / 100


def compare_throughput_values(context, last_result, threshold):
    assert last_result["output"]["status"] == context.result["status"]
    if last_result["output"]["status"] == "OK":
        old_throughput = extract_value(last_result["output"], "total_tx_rate")
        throughput_comparison(context, old_throughput, threshold=threshold)


def compare_latency_values(context, last_result, threshold):
    assert last_result["output"]["status"] == context.result["status"]
    if last_result["output"]["status"] == "OK":
        old_latency = extract_value(extract_value(last_result["output"], "overall"),
                                    "avg_delay_usec")
        latency_comparison(context, old_latency, threshold=threshold)


def throughput_comparison(context, old_throughput_pps=None, threshold=None, reference_values=None):
    current_throughput_pps = extract_value(context.result, "total_tx_rate")

    if old_throughput_pps:
        if not current_throughput_pps >= convert_percentage_str_to_float(
                threshold) * old_throughput_pps:
            raise AssertionError(
                "Current run throughput {current_throughput_pps} is not over {threshold} "
                " of previous value ({old_throughput_pps}pps)".format(
                    current_throughput_pps=Formatter.suffix('pps')(
                        Formatter.standard(current_throughput_pps)),
                    threshold=threshold, old_throughput_pps=Formatter.suffix('pps')(
                        Formatter.standard(old_throughput_pps))))
    elif reference_values:
        if context.unit == 'bps':
            current_throughput = extract_value(context.result, "offered_tx_rate_bps")
            reference_values = [int(parse_rate_str(x)['rate_bps']) for x in reference_values]
            formatted_current_throughput = Formatter.bits(current_throughput)
            formatted_min_reference_value = Formatter.bits(reference_values[0])
            formatted_max_reference_value = Formatter.bits(reference_values[1])
        else:
            current_throughput = current_throughput_pps
            reference_values = [int(parse_rate_str(x)['rate_pps']) for x in reference_values]
            formatted_current_throughput = Formatter.suffix('pps')(
                Formatter.standard(current_throughput))
            formatted_min_reference_value = Formatter.suffix('pps')(
                Formatter.standard(reference_values[0]))
            formatted_max_reference_value = Formatter.suffix('pps')(
                Formatter.standard(reference_values[1]))
        if not reference_values[0] <= int(current_throughput) <= reference_values[1]:
            raise AssertionError(
                "Current run throughput {current_throughput} is not in reference values "
                "[{min_reference_value}, {max_reference_value}]".format(
                    current_throughput=formatted_current_throughput,
                    min_reference_value=formatted_min_reference_value,
                    max_reference_value=formatted_max_reference_value))


def latency_comparison(context, old_latency=None, threshold=None, reference_values=None):
    overall = extract_value(context.result, "overall")
    current_latency = extract_value(overall, "avg_delay_usec")

    if old_latency:
        if not current_latency <= (2 - convert_percentage_str_to_float(threshold)) * old_latency:
            threshold = str(200 - int(threshold.strip('%'))) + '%'
            raise AssertionError(
                "Current run latency {current_latency}usec is not less than {threshold} of "
                "previous value ({old_latency}usec)".format(
                    current_latency=Formatter.standard(current_latency), threshold=threshold,
                    old_latency=Formatter.standard(old_latency)))
    elif reference_values:
        if not reference_values[0] <= current_latency <= reference_values[1]:
            raise AssertionError(
                "Current run latency {current_latency}usec is not in reference values "
                "[{min_reference_value}, {max_reference_value}]".format(
                    current_latency=Formatter.standard(current_latency),
                    min_reference_value=Formatter.standard(reference_values[0]),
                    max_reference_value=Formatter.standard(reference_values[1])))


def get_result_from_input_values(input, result):
    # Select required keys (other keys can be not set or unconsistent between scenarios)
    required_keys = ['duration_sec', 'frame_sizes', 'flow_count', 'rate']
    if 'user_label' in result:
        required_keys.append('user_label')
    if 'flavor_type' in result:
        required_keys.append('flavor_type')
    subset_input = dict((k, input[k]) for k in required_keys if k in input)
    subset_result = dict((k, result[k]) for k in required_keys if k in result)
    return subset_input == subset_result


def extract_value(obj, key):
    """Pull all values of specified key from nested JSON."""
    arr = []

    def extract(obj, arr, key):
        """Recursively search for values of key in JSON tree."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == key:
                    arr.append(v)
                elif isinstance(v, (dict, list)):
                    extract(v, arr, key)
        elif isinstance(obj, list):
            for item in obj:
                extract(item, arr, key)
        return arr

    results = extract(obj, arr, key)
    return results[0]


def get_last_result(context, reference=None, page=None):
    if reference:
        case_name = 'characterization'
    else:
        case_name = context.CASE_NAME
    url = context.data['TEST_DB_URL'] + '?project={project_name}&case={case_name}'.format(
        project_name=context.data['PROJECT_NAME'], case_name=case_name)
    if context.data['INSTALLER_TYPE']:
        url += '&installer={installer_name}'.format(installer_name=context.data['INSTALLER_TYPE'])
    if context.data['NODE_NAME']:
        url += '&pod={pod_name}'.format(pod_name=context.data['NODE_NAME'])
    url += '&criteria=PASS'
    if page:
        url += '&page={page}'.format(page=page)
    last_results = requests.get(url)
    assert last_results.status_code == 200
    last_results = json.loads(last_results.text)
    for result in last_results["results"]:
        for tagged_result in result["details"]["results"][context.tag]:
            if get_result_from_input_values(tagged_result["input"], context.json):
                return tagged_result
    if last_results["pagination"]["current_page"] < last_results["pagination"]["total_pages"]:
        page = last_results["pagination"]["current_page"] + 1
        return get_last_result(context, page)
    return None
