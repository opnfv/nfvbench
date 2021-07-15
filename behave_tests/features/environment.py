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


import json
import os
import pathlib
import time


def before_all(context):
    context.data = {'config': os.getenv('NFVBENCH_CONFIG_PATH', '/etc/nfvbench/nfvbench.cfg')}

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

    # NFVbench server host and port
    context.host_ip = os.getenv('NFVBENCH_SERVER_HOST', '127.0.0.1')
    context.port = int(os.getenv('NFVBENCH_SERVER_PORT', '7555'))


def before_feature(context, feature):
    context.rates = {}
    context.results = {}
    context.start_time = time.time()
    context.CASE_NAME = feature.name


def before_scenario(context, scenario):
    context.tag = scenario.tags[0]
    context.json = {'log_file': '/var/lib/xtesting/results/' + context.CASE_NAME + '/nfvbench.log'}
    user_label = os.getenv('NFVBENCH_USER_LABEL', None)
    if user_label:
        context.json['user_label'] = user_label
    loopvm_flavor = os.getenv('NFVBENCH_LOOPVM_FLAVOR_NAME', None)
    if loopvm_flavor:
        context.json['flavor_type'] = loopvm_flavor
    context.synthesis = {}


def after_feature(context, feature):
    if len(context.results) == 0:
        # No result to dump
        return

    results_dir = pathlib.Path('/var/lib/xtesting/results/' + context.CASE_NAME)
    if not results_dir.exists():
        results_dir.mkdir()

    results_file = results_dir / pathlib.Path('campaign_result.json')
    results_file.write_text(json.dumps(context.results, indent=4))
