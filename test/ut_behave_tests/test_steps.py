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
Unit tests for some of the functions found in behave_tests/features/steps/steps.py
"""

import logging
import unittest
from unittest.mock import call, Mock, patch

from behave_tests.features.steps.steps import get_last_result
from .test_utils import setup_logging, stub_requests_get


def setUpModule():
    setup_logging()


class TestGetLastResult(unittest.TestCase):
    def setUp(self):
        # Mock requests.get() so that TestAPI results come from JSON files
        # found in test_data/ directory.
        patcher = patch('behave_tests.features.steps.testapi.requests')
        self._mock_requests = patcher.start()
        self._mock_requests.get.side_effect = stub_requests_get
        self.addCleanup(patcher.stop)

        # Setup a mock for behave context
        self._context = Mock()
        self._context.data = {
            'PROJECT_NAME': "nfvbench",
            'TEST_DB_URL': "http://127.0.0.1:8000/api/v1/results"
        }
        self._context.logger = logging.getLogger("behave_tests")

    def test_get_last_result_throughput_characterization(self):
        self._context.json = {
            "frame_sizes": ['64'],
            "flow_count": "100k",
            "duration_sec": '10',
            "rate": "ndr",
            "user_label": "amical_tc18_loopback"
        }
        self._context.tag = "throughput"

        last_result = get_last_result(self._context, reference=True)

        self.assertIsNotNone(last_result)
        self.assertEqual(16765582, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(25, round(last_result["synthesis"]["avg_delay_usec"]))

        self._mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8000/api/v1/results?"
            "project=nfvbench&case=characterization&criteria=PASS&page=1")

    def test_get_last_result_latency_characterization(self):
        self._context.json = {
            "frame_sizes": ['768'],
            "flow_count": "100k",
            "duration_sec": '10',
            "rate": "90%",
            "user_label": "amical_tc6_intensive"
        }
        self._context.tag = "latency"

        last_result = get_last_result(self._context, reference=True)

        self.assertIsNotNone(last_result)
        self.assertEqual(262275, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(353, round(last_result["synthesis"]["avg_delay_usec"]))

        self._mock_requests.get.assert_has_calls([
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=1"),
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=2")])

    def test_last_result_not_found(self):
        self._context.json = {
            "frame_sizes": ['64'],
            "flow_count": "100k",
            "duration_sec": '10',
            "rate": "ndr",
            "user_label": "toto_titi_tata"  # User label not in test data
        }
        self._context.tag = "throughput"

        with self.assertRaises(AssertionError):
            get_last_result(self._context, reference=True)

        self._mock_requests.get.assert_has_calls([
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=1"),
            call("http://127.0.0.1:8000/api/v1/results?"
                 "project=nfvbench&case=characterization&criteria=PASS&page=2")])

    def test_get_last_result_throughput_non_regression(self):
        self._context.CASE_NAME = "non-regression"
        self._context.json = {
            "frame_sizes": ['1518'],
            "flow_count": "100k",
            "duration_sec": '10',
            "rate": "ndr",
            "user_label": "amical_tc12_basic"
        }
        self._context.tag = "throughput"

        last_result = get_last_result(self._context)

        self.assertIsNotNone(last_result)
        self.assertEqual(512701, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(148, round(last_result["synthesis"]["avg_delay_usec"]))

        self._mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8000/api/v1/results?"
            "project=nfvbench&case=non-regression&criteria=PASS&page=1")

    def test_get_last_result_latency_non_regression(self):
        self._context.CASE_NAME = "non-regression"
        self._context.json = {
            "frame_sizes": ['1518'],
            "flow_count": "100k",
            "duration_sec": '10',
            "rate": "70%",
            "user_label": "amical_tc12_basic"
        }
        self._context.tag = "latency"

        last_result = get_last_result(self._context)

        self.assertIsNotNone(last_result)
        self.assertEqual(352040, last_result["synthesis"]["total_tx_rate"])
        self.assertEqual(114, round(last_result["synthesis"]["avg_delay_usec"]))

        self._mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8000/api/v1/results?"
            "project=nfvbench&case=non-regression&criteria=PASS&page=1")
