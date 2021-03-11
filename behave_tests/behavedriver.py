#!/usr/bin/env python

# Copyright (c) 2019 Orange and others.
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0

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
