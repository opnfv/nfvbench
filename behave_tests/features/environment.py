#!/usr/bin/env python

# Copyright (c) 2021 Orange and others.
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0


import json
import os
import time


def before_all(context):
    context.data = {'config': os.getenv('NFVBENCH_CONFIG_PATH', '/tmp/nfvbench/nfvbench.cfg')}

    context.data['PROJECT_NAME'] = os.getenv('PROJECT_NAME', 'nfvbench')
    context.data['TEST_DB_EXT_URL'] = os.getenv('TEST_DB_EXT_URL')
    context.data['TEST_DB_URL'] = os.getenv('TEST_DB_URL')
    context.data['BASE_TEST_DB_URL'] = ''
    if context.data['TEST_DB_URL']:
        context.data['BASE_TEST_DB_URL'] = context.data['TEST_DB_URL'].replace('results', '')
    context.data['INSTALLER_TYPE'] = os.getenv('INSTALLER_TYPE')
    context.data['DEPLOY_SCENARIO'] = os.getenv('DEPLOY_SCENARIO')
    context.data['NODE_NAME'] = os.getenv('NODE_NAME', 'nfvbench')
    context.data['BUILD_TAG'] = os.getenv('BUILD_TAG')


def before_feature(context, feature):
    context.rates = {}
    context.results = {}
    context.start_time = time.time()
    context.CASE_NAME = feature.name


def before_scenario(context, scenario):
    context.tag = scenario.tags[0]
    context.json = {'log_file': '/var/lib/xtesting/results/' + context.CASE_NAME + '/nfvbench.log'}
    context.synthesis = {}


def after_feature(context, feature):
    if context.results:
        with open(os.path.join(
                '/var/lib/xtesting/results/' + context.CASE_NAME + '/campaign_result.json'),
                  "w") as outfile:
            json.dump(context.results, outfile)
