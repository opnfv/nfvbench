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

"""Define classes required to run any Behave test suites."""

from __future__ import division

import json
import logging
import os

from xtesting.core.behaveframework import BehaveFramework

__author__ = "François-Régis Menguy <francoisregis.menguy@orange.com>"


class BehaveDriver(BehaveFramework):
    """NFVbench custom BehaveDriver for Xtesting."""
    # pylint: disable=too-many-instance-attributes

    __logger = logging.getLogger('xtesting.core.behavedriver')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.campaign_json_file = os.path.join(self.res_dir, 'campaign_result.json')

    def extract_nfvbench_results(self):
        with open(self.campaign_json_file) as stream_:
            self.details['results'] = json.load(stream_)

    def run(self, **kwargs):

        """Override existing Xtesting BehaveFramework core script run method
         to extract NFVbench result and push them to DB

        Here are the steps:
           * run Xtesting behave method:
            * create the output directories if required,
            * run behave features with parameters
            * get the behave results in output.json,
            * get the nfvbench results in campaign_result.json

        Args:
            kwargs: Arbitrary keyword arguments.

        Returns:
            EX_OK if all suites ran well.
            EX_RUN_ERROR otherwise.
        """
        try:
            super().run(**kwargs)
            self.extract_nfvbench_results()
            self.__logger.info("NFVbench results were successfully parsed")
        except Exception:  # pylint: disable=broad-except
            self.__logger.exception("Cannot parse NFVbench results")
            return self.EX_RUN_ERROR
        return self.EX_OK
