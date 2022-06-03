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

import logging
import requests


class TestapiClient:
    __test__ = False  # Hint for pytest: TestapiClient is not a test class.

    def __init__(self, testapi_url: str):
        """
        Args:
            testapi_url: testapi URL as a string, for instance
                "http://172.20.73.203:8000/api/v1/results"
        """
        self._base_url = testapi_url
        self._logger = logging.getLogger("behave_tests")

    def find_last_result(self, testapi_params, scenario_tag: str, nfvbench_test_input):
        """Search testapi database and return latest result matching filters.

        Look for the most recent testapi result matching testapi params, behave
        scenario tag and nfvbench test input params, and return that result as a
        dictionary.

        Args:
            testapi_params: dict holding the parameters of the testapi request.  See
                `build_testapi_url()` for the list of supported keys.

            scenario_tag: Behave scenario tag to filter results.  One of
                "throughput" or "latency".

            nfvbench_test_input: dict holding nfvbench test parameters and used
                to filter the testapi results.  The following keys are currently
                supported:
                - mandatory keys: 'duration_sec', 'frame_sizes', 'flow_count', 'rate'
                - optional keys: 'user_label'

        Returns:
            None if no result matching the filters can be found, else a dictionary
            built from testapi JSON test result.

        """
        self._logger.info(f"find_last_result: filter on scenario tag: {scenario_tag}")
        nfvbench_input_str = nfvbench_input_to_str(nfvbench_test_input)
        self._logger.info(f"find_last_result: filter on test conditions: {nfvbench_input_str}")

        page = 1
        while True:  # While there are results pages to read
            url = self._build_testapi_url(testapi_params, page)
            self._logger.info("find_last_result: GET " + url)
            last_results = self._do_testapi_request(url)

            for result in last_results["results"]:
                for tagged_result in result["details"]["results"][scenario_tag]:
                    if tagged_result["output"]["status"] != "OK":
                        # Drop result if nfvbench status is not OK
                        # (such result should not have been put in database by behave_tests,
                        # but let's be cautious)
                        continue
                    if equal_test_conditions(tagged_result["input"], nfvbench_test_input):
                        return tagged_result

            if page >= last_results["pagination"]["total_pages"]:
                break
            page += 1

        return None

    def _build_testapi_url(self, testapi_params, page=1):
        """Build URL for testapi request.

        Build a URL for a testapi HTTP GET request using the provided parameters and
        limiting the results to the tests whose criteria equals "PASS".

        Args:
            testapi_params: dictionary holding the parameters of the testapi
                request:
                - mandatory keys: "project_name", "case_name"
                - optional keys: "installer", "pod_name"
                - ignored keys: "build_tag", "scenario", "version", "criteria".

            page: (Optional) number of the results page to get.

        """
        url = self._base_url
        url += f"?project={testapi_params['project_name']}"
        url += f"&case={testapi_params['case_name']}"

        if "installer" in testapi_params.keys():
            url += f"&installer={testapi_params['installer']}"
        if "pod_name" in testapi_params.keys():
            url += f"&pod={testapi_params['pod_name']}"

        url += '&criteria=PASS'
        url += f"&page={page}"

        return url

    def _do_testapi_request(self, testapi_url):
        """Perform HTTP GET request on testapi.

        Perform an HTTP GET request on testapi, check status code and return JSON
        results as dictionary.

        Args:
            testapi_url: a complete URL to request testapi results (with base
                endpoint and parameters)

        Returns:
            The JSON document from testapi as a Python dictionary

        Raises:
            * requests.exceptions.ConnectionError in case of network problem
              when trying to establish a connection with the TestAPI database
              (DNS failure, refused connection, ...)

            * requests.exceptions.ConnectTimeout in case of timeout during the
              request.

            * requests.exception.HTTPError if the HTTP request returned an
              unsuccessful status code.

            * another exception derived from requests.exceptions.RequestException
              in case of problem during the HTTP request.
        """
        response = requests.get(testapi_url)
        # raise an HTTPError if the HTTP request returned an unsuccessful status code:
        response.raise_for_status()
        return response.json()


def equal_test_conditions(testapi_input, nfvbench_input):
    """Check test conditions in behave scenario results record.

    Check whether a behave scenario results record from testapi matches a given
    nfvbench input, ie whether the record comes from a test done under the same
    conditions (frame size, flow count, ...)

    Args:
        testapi_input: dict holding the test conditions of a behave scenario
            results record from testapi

        nfvbench_input: dict of nfvbench test parameters (reference)

    The following dict keys are currently supported:
        - mandatory keys: 'duration_sec', 'frame_sizes', 'flow_count', 'rate'
        - optional keys: 'user_label'

    Optional keys are taken into account only when they can be found in
    `nfvbench_input`, else they are ignored.

    Returns:
        True if test conditions match, else False.

    """
    # Select required keys (other keys can be not set or unconsistent between scenarios)
    required_keys = ['duration_sec', 'frame_sizes', 'flow_count', 'rate']
    if 'user_label' in nfvbench_input:
        required_keys.append('user_label')

    try:
        testapi_subset = {k: testapi_input[k] for k in required_keys}
        nfvbench_subset = {k: nfvbench_input[k] for k in required_keys}
        return testapi_subset == nfvbench_subset
    except KeyError:
        # Fail the comparison if a required key is missing from one of the dicts
        return False


def nfvbench_input_to_str(nfvbench_input: dict) -> str:
    """Build string showing nfvbench input parameters used for results search

    Args:
        nfvbench_input: dict of nfvbench test parameters
    """
    string = ""
    for key in ['user_label', 'frame_sizes', 'flow_count', 'rate', 'duration_sec']:
        if key in nfvbench_input:
            string += f"{key}={nfvbench_input[key]} "
    return string
