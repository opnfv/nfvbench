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
Utility functions for unit tests.
"""

import json
import logging
import pathlib
import unittest
from unittest.mock import Mock


# -----------------------------------------------------------------------------------------
# Logging helpers
# -----------------------------------------------------------------------------------------

def setup_logging(log_filename=None):
    """Setup logging for unit tests.

    Principles:
    - use a test-specific logger
    - log messages up to INFO level to the console
    - if `log_filename` is provided, log messages up to DEBUG level to the log file
    """
    logger = logging.getLogger("unit_tests_logger")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s:%(filename)s:%(lineno)s: %(message)s")

    # Configure logging to the console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Configure logging to the log file
    if log_filename is not None:
        fh = logging.FileHandler(filename=log_filename, mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


def get_logger():
    """Get unit test logger."""
    return logging.getLogger("unit_tests_logger")


# -----------------------------------------------------------------------------------------
# Test data helpers
# -----------------------------------------------------------------------------------------

def get_test_data_dir() -> pathlib.Path:
    """Get absolute path of the test_data/ dir.

    We need this because the unit tests can be run from different locations
    depending on the context (tox, development, ...)
    """
    return pathlib.Path(__file__).parent / 'test_data'


def stub_requests_get(testapi_url):
    """Mock a request to TestAPI results database.

    Instead of doing a real request, build a filename from the URL suffix, find
        the file in the `test_data` directory and return the contents of the file.

    Args:
        testapi_url: a URL starting with `http://127.0.0.1:8000/api/v1/results?`
            and followed by the results file name without extension.

    Returns:
        A mock of a `requests.Response` object with the attributes `text` and
            `status_code` and the method `json()`.
    """
    response = Mock()
    filename_prefix = testapi_url.replace('http://127.0.0.1:8000/api/v1/results?', '')
    if filename_prefix == testapi_url:
        raise ValueError("For unit tests, TestAPI URL must start with "
                         "http://127.0.0.1:8000/api/v1/results?")
    page_filename = get_test_data_dir() / (filename_prefix + ".json")
    try:
        with open(page_filename, 'r', encoding='utf-8') as results:
            response.text = results.read()
        response.json = lambda: json.loads(response.text)
        response.status_code = 200
        return response
    except FileNotFoundError as e:
        get_logger().exception(e)
        raise ValueError(f"No test data available for TestAPI URL: {testapi_url}") from e


class TestStubRequestsGet(unittest.TestCase):
    def test_valid_url(self):
        response = stub_requests_get("http://127.0.0.1:8000/api/v1/results?"
                                     "project=nfvbench&case=characterization&criteria=PASS&page=1")
        self.assertEqual(200, response.status_code)
        self.assertEqual("nfvbench", response.json()["results"][0]["project_name"])

    def test_bad_prefix(self):
        with self.assertRaises(ValueError):
            stub_requests_get("http://no.way/api/v1/results?" "dummy_suffix")

    def test_file_not_found(self):
        with self.assertRaises(ValueError):
            stub_requests_get("http://127.0.0.1:8000/api/v1/results?" "dummy_suffix")
