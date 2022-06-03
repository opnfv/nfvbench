#!/usr/bin/env python
# Copyright 2022 Orange
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

"""
Unit tests for the testapi module found in behave_tests/features/steps.
"""

import unittest
from unittest.mock import call, patch

from behave_tests.features.steps.testapi import TestapiClient
from .test_utils import setup_logging, stub_requests_get


def setUpModule():
    setup_logging(log_filename="ut_behave_tests_testapi.log")


class TestTestapiClient(unittest.TestCase):
    def setUp(self):
        patcher = patch('behave_tests.features.steps.testapi.requests')
        self.mock_requests = patcher.start()
        self.mock_requests.get.side_effect = stub_requests_get
        self.addCleanup(patcher.stop)

    def test_find_characterization_throughput_on_page_1(self):
        client = TestapiClient("http://127.0.0.1:8000/api/v1/results")
        testapi_params = {"project_name": "nfvbench", "case_name": "characterization"}
        nfvbench_test_input = {"frame_sizes": ['64'],
                               "flow_count": "100k",
                               "duration_sec": '10',
                               "rate": "ndr",
                               "user_label": "amical_tc18_loopback"}
        last_result = client.find_last_result(testapi_params,
                                              scenario_tag="throughput",
                                              nfvbench_test_input=nfvbench_test_input)
        self.assertIsNotNone(last_result)
        self.assertEqual(16765582, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(25, round(last_result["synthesis"]["avg_delay_usec"]))

        self.mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8000/api/v1/results?"
            "project=nfvbench&case=characterization&criteria=PASS&page=1")

    def test_find_characterization_latency_on_page_2(self):
        client = TestapiClient("http://127.0.0.1:8000/api/v1/results")
        testapi_params = {"project_name": "nfvbench", "case_name": "characterization"}
        nfvbench_test_input = {"frame_sizes": ['768'],
                               "flow_count": "100k",
                               "duration_sec": '10',
                               "rate": "90%",
                               "user_label": "amical_tc6_intensive"}
        last_result = client.find_last_result(testapi_params,
                                              scenario_tag="latency",
                                              nfvbench_test_input=nfvbench_test_input)
        self.assertIsNotNone(last_result)
        self.assertEqual(262275, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(353, round(last_result["synthesis"]["avg_delay_usec"]))

        self.mock_requests.get.assert_has_calls([
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=1"),
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=2")])

    def test_no_result_found(self):
        client = TestapiClient("http://127.0.0.1:8000/api/v1/results")
        testapi_params = {"project_name": "nfvbench", "case_name": "characterization"}
        nfvbench_test_input = {"frame_sizes": ['768'],
                               "flow_count": "100k",
                               "duration_sec": '10',
                               "rate": "90%",
                               "user_label": "toto_titi_tata"}  # User label not in test data
        last_result = client.find_last_result(testapi_params,
                                              scenario_tag="throughput",
                                              nfvbench_test_input=nfvbench_test_input)
        self.assertIsNone(last_result)

        self.mock_requests.get.assert_has_calls([
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=1"),
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=2")])

    def test_requests_errors(self):
        """Check that an exception is raised in case of problem with requests."""
        client = TestapiClient("http://127.0.0.1:8000/api/v1/results")
        testapi_params = {"project_name": "foo",  # non-existent project
                          "case_name": "characterization"}
        nfvbench_test_input = {"frame_sizes": ['768'],
                               "flow_count": "100k",
                               "duration_sec": '10',
                               "rate": "90%",
                               "user_label": "amical_tc6_intensive"}

        with self.assertRaises(ValueError):
            client.find_last_result(testapi_params, scenario_tag="throughput",
                                    nfvbench_test_input=nfvbench_test_input)

    def test_flavor_is_ignored(self):
        """Check that lookup in TestAPI does not filter on the flavor_type."""
        client = TestapiClient("http://127.0.0.1:8000/api/v1/results", get_logger())
        testapi_params = {"project_name": "nfvbench", "case_name": "characterization"}
        nfvbench_test_input = {"frame_sizes": ['64'],
                               "flow_count": "100k",
                               "duration_sec": '10',
                               "rate": "ndr",
                               "user_label": "amical_tc18_loopback",
                               "flavor_type": "no_such_flavor"}
        last_result = client.find_last_result(testapi_params,
                                              scenario_tag="throughput",
                                              nfvbench_test_input=nfvbench_test_input)
        self.assertIsNotNone(last_result)
        self.assertEqual(16765582, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(25, round(last_result["synthesis"]["avg_delay_usec"]))

        self.mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8000/api/v1/results?"
            "project=nfvbench&case=characterization&criteria=PASS&page=1")
