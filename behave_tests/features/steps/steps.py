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

from behave import given
from behave import when
from behave import then
from copy import deepcopy
from requests import RequestException
from retry import retry
import json
import requests
import subprocess
from subprocess import DEVNULL
from typing import Optional

from nfvbench.summarizer import Formatter
from nfvbench.traffic_gen.traffic_utils import parse_rate_str

from behave_tests.features.steps.testapi import TestapiClient, nfvbench_input_to_str


STATUS_ERROR = "ERROR"

STATUS_OK = "OK"


"""Given steps."""


@given('PROJECT_NAME: {project_name}')
def override_xtesting_project_name(context, project_name):
    context.data['PROJECT_NAME'] = project_name


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
    context.logger.info(f"add_percentage_rate: {percentage_rate} => rate={rate}")


@given('packet rate equal to {percentage} of max throughput of last characterization')
def add_packet_rate(context, percentage: str):
    """Update nfvbench run config with packet rate based on reference value.

    For the already configured frame size and flow count, retrieve the max
    throughput obtained during the latest successful characterization run.  Then
    retain `percentage` of this value for the packet rate and update `context`.

    Args:
        context: The context data of the current scenario run.  It includes the
            testapi endpoints to retrieve the reference values.

        percentage: String representation of the percentage of the reference max
            throughput.  Example: "70%"

    Updates context:
        context.percentage_rate: percentage of reference max throughput
            using a string representation. Example: "70%"

        context.json['rate']: packet rate in packets per second using a string
            representation.  Example: "2000pps"

    Raises:
        ValueError: invalid percentage string

        AssertionError: cannot find reference throughput value

    """
    # Validate percentage
    if not percentage.endswith('%'):
        raise ValueError('Invalid percentage string: "{0}"'.format(percentage))
    percentage_float = convert_percentage_str_to_float(percentage)

    # Retrieve nfvbench results report from testapi for:
    # - the latest throughput scenario inside a characterization feature that passed
    # - the test duration, frame size and flow count given in context.json
    # - (optionally) the user_label and flavor_type given in context.json
    # - the 'ndr' rate
    testapi_params = {"project_name": context.data['PROJECT_NAME'],
                      "case_name": "characterization"}
    nfvbench_test_conditions = deepcopy(context.json)
    nfvbench_test_conditions['rate'] = 'ndr'
    testapi_client = TestapiClient(testapi_url=context.data['TEST_DB_URL'])
    last_result = testapi_client.find_last_result(testapi_params,
                                                  scenario_tag="throughput",
                                                  nfvbench_test_input=nfvbench_test_conditions)
    if last_result is None:
        error_msg = "No characterization result found for scenario_tag=throughput"
        error_msg += " and nfvbench test conditions "
        error_msg += nfvbench_input_to_str(nfvbench_test_conditions)
        context.logger.error(error_msg)
        raise AssertionError(error_msg)

    # From the results report, extract the max throughput in packets per second
    total_tx_rate = extract_value(last_result["output"], "total_tx_rate")
    context.logger.info("add_packet_rate: max throughput of last characterization (pps): "
                        f"{total_tx_rate:,}")

    # Compute the desired packet rate
    rate = round(total_tx_rate * percentage_float)
    context.logger.info(f"add_packet_rate: percentage={percentage} rate(pps)={rate:,}")

    # Build rate string using a representation understood by nfvbench
    rate_str = str(rate) + "pps"

    # Update context
    context.percentage_rate = percentage
    context.json['rate'] = rate_str


"""When steps."""


@when('NFVbench API is ready')
@when('NFVbench API is ready on host {host_ip}')
@when('NFVbench API is ready on host {host_ip} and port {port:d}')
def start_server(context, host_ip: Optional[str]=None, port: Optional[int]=None):
    """Start nfvbench server if needed and wait until it is ready.

    Quickly check whether nfvbench HTTP server is ready by reading the "/status"
    page.  If not, start the server locally.  Then wait until nfvbench API is
    ready by polling the "/status" page.

    This code is useful when behave and nfvbench run on the same machine.  In
    particular, it is needed to run behave tests with nfvbench Docker container.

    There is currently no way to prevent behave from starting automatically
    nfvbench server when this is not desirable, for instance when behave is
    started using ansible-role-nfvbench.  The user or the orchestration layer
    should make sure nfvbench API is ready before starting behave tests.

    """
    # NFVbench server host IP and port number have been setup from environment variables (see
    # environment.py:before_all()).   Here we allow to override them from feature files:
    if host_ip is not None:
        context.host_ip = host_ip
    if port is not None:
        context.port = port

    nfvbench_test_url = "http://{ip}:{port}/status".format(ip=context.host_ip, port=context.port)
    context.logger.info("start_server: test nfvbench API on URL: " + nfvbench_test_url)

    try:
        # check if API is already available
        requests.get(nfvbench_test_url)
    except RequestException:
        context.logger.info("nfvbench server not running")

        cmd = ["nfvbench", "-c", context.data['config'], "--server"]
        if context.host_ip != "127.0.0.1":
            cmd.append("--host")
            cmd.append(context.host_ip)
        if context.port != 7555:
            cmd.append("--port")
            cmd.append(str(context.port))

        context.logger.info("Start nfvbench server with command: " + " ".join(cmd))

        subprocess.Popen(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

    # Wait until nfvbench API is ready
    test_nfvbench_api(nfvbench_test_url)


"""Then steps."""


@then('run is started and waiting for result')
@then('{repeat:d} runs are started and waiting for maximum result')
def run_nfvbench_traffic(context, repeat=1):
    context.logger.info(f"run_nfvbench_traffic: fs={context.json['frame_sizes'][0]} "
                        f"fc={context.json['flow_count']} "
                        f"rate={context.json['rate']} repeat={repeat}")

    if 'json' not in context.json:
        # Build filename for nfvbench results in JSON format
        context.json['json'] = '/var/lib/xtesting/results/' + context.CASE_NAME + \
                               '/nfvbench-' + context.tag + \
                               '-fs_' + context.json['frame_sizes'][0] + \
                               '-fc_' + context.json['flow_count']
        if context.percentage_rate is not None:
            # Add rate as a percentage, eg '-rate_70%'
            context.json['json'] += '-rate_' + context.percentage_rate
        else:
            # Add rate in bits or packets per second, eg '-rate_15Gbps' or '-rate_10kpps'
            context.json['json'] += '-rate_' + context.json['rate']
        context.json['json'] += '.json'

    json_base_name = context.json['json']

    max_total_tx_rate = None
    # rem: don't init with 0 in case nfvbench gets crazy and returns a negative packet rate

    for i in range(repeat):
        if repeat > 1:
            context.json['json'] = json_base_name.strip('.json') + '-' + str(i) + '.json'

        # Start nfvbench traffic and wait result:
        url = "http://{ip}:{port}/start_run".format(ip=context.host_ip, port=context.port)
        payload = json.dumps(context.json)
        r = requests.post(url, data=payload, headers={'Content-Type': 'application/json'})
        context.request_id = json.loads(r.text)["request_id"]
        assert r.status_code == 200
        result = wait_result(context)
        assert result["status"] == STATUS_OK

        # Extract useful metrics from result:
        total_tx_rate = extract_value(result, "total_tx_rate")
        overall = extract_value(result, "overall")
        avg_delay_usec = extract_value(overall, "avg_delay_usec")

        # Log latest result:
        context.logger.info(f"run_nfvbench_traffic: result #{i+1}: "
                            f"total_tx_rate(pps)={total_tx_rate:,} "  # Add ',' thousand separator
                            f"avg_latency_usec={round(avg_delay_usec)}")

        # Keep only the result with the highest packet rate:
        if max_total_tx_rate is None or total_tx_rate > max_total_tx_rate:
            max_total_tx_rate = total_tx_rate
            context.result = result
            context.synthesis['total_tx_rate'] = total_tx_rate
            context.synthesis['avg_delay_usec'] = avg_delay_usec

    # Log max result only when we did two nfvbench runs or more:
    if repeat > 1:
        context.logger.info(f"run_nfvbench_traffic: max result: "
                            f"total_tx_rate(pps)={context.synthesis['total_tx_rate']:,} "
                            f"avg_latency_usec={round(context.synthesis['avg_delay_usec'])}")


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


@then('verify latency result is lower than {max_avg_latency_usec:g} microseconds')
def check_latency_result_against_fixed_threshold(context, max_avg_latency_usec: float):
    """Check latency result against a fixed threshold.

    Check that the average latency measured during the current scenario run is
    lower or equal to the provided fixed reference value.

    Args:
        context: The context data of the current scenario run.  It includes the
            test results for that run.

        max_avg_latency_usec: Reference value to be used as a threshold.  This
            is a maximum average latency expressed in microseconds.

    Raises:
        AssertionError: The latency result is strictly greater than the reference value.

    """
    # Get the just measured average latency (a float):
    new_avg_latency_usec = context.synthesis['avg_delay_usec']

    # Log what we test:
    context.logger.info("check_latency_result_against_fixed_threshold(usec): "
                        "{value}<={ref}?".format(
                            value=round(new_avg_latency_usec),
                            ref=round(max_avg_latency_usec)))

    # Compare measured value to reference:
    if new_avg_latency_usec > max_avg_latency_usec:
        raise AssertionError("Average latency higher than max threshold: "
                             "{value} usec > {ref} usec".format(
                                 value=round(new_avg_latency_usec),
                                 ref=round(max_avg_latency_usec)))


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


@retry(AssertionError, tries=24, delay=5.0, logger=None)
def test_nfvbench_api(nfvbench_test_url: str):
    try:
        r = requests.get(nfvbench_test_url)
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
                " of previous value ({old_throughput_pps})".format(
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


def get_last_result(context, reference: bool = False):
    """Look for a previous result in TestAPI database.

    Search TestAPI results from newest to oldest and return the first result
    record matching the context constraints.  Log an overview of the results
    found (max rate pps, avg delay usec, test conditions, date of measurement).

    The result record test case must match the current test case
    ('characterization' or 'non-regression') unless `reference` is set to True.

    The result record scenario tag must match the current scenario tag
    ('throughput' or 'latency').

    Args:
        context: behave context including project name, test case name, traffic
            configuration (frame size, flow count, test duration), type of the
            compute node under test (via loop VM flavor_type) and platform (via
            user_label).

        reference: when True, look for results with the 'characterization' test
            case name instead of the current test case name.

    Returns:
        a JSON dictionary with the results, ie a dict with the keys "input",
            "output" and "synthesis" when the scenario tag is 'throughput' or
            'latency'
    """
    if reference:
        case_name = 'characterization'
    else:
        case_name = context.CASE_NAME
    testapi_params = {"project_name": context.data['PROJECT_NAME'],
                      "case_name": case_name}
    testapi_client = TestapiClient(testapi_url=context.data['TEST_DB_URL'])
    last_result = testapi_client.find_last_result(testapi_params,
                                                  scenario_tag=context.tag,
                                                  nfvbench_test_input=context.json)
    if last_result is None:
        error_msg = "get_last_result: No result found in TestAPI database:"
        error_msg += f" case_name={case_name} scenario_tag={context.tag} "
        error_msg += nfvbench_input_to_str(context.json)
        context.logger.error(error_msg)
        raise AssertionError(error_msg)

    # Log an overview of the last result (latency and max throughput)
    measurement_date = last_result["output"]["result"]["date"]
    total_tx_rate = extract_value(last_result["output"], "total_tx_rate")
    avg_delay_usec = extract_value(extract_value(last_result["output"], "overall"),
                                   "avg_delay_usec")
    context.logger.info(f"get_last_result: case_name={case_name} scenario_tag={context.tag}"
                        f' measurement_date="{measurement_date}"'
                        f" total_tx_rate(pps)={total_tx_rate:,}"
                        f" avg_latency_usec={round(avg_delay_usec)}")

    return last_result
