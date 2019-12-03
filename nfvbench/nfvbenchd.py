#!/usr/bin/env python
# Copyright 2017 Cisco Systems, Inc.  All rights reserved.
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
import queue
from threading import Thread
import uuid

from flask import Flask
from flask import jsonify
from flask import request

from .summarizer import NFVBenchSummarizer

from .log import LOG
from .utils import byteify
from .utils import RunLock

from .__init__ import __version__

STATUS_OK = 'OK'
STATUS_ERROR = 'ERROR'
STATUS_PENDING = 'PENDING'
STATUS_NOT_FOUND = 'NOT_FOUND'

def result_json(status, message, request_id=None):
    body = {
        'status': status,
        'error_message': message
    }
    if request_id is not None:
        body['request_id'] = request_id

    return body


def load_json(data):
    return json.loads(json.dumps(data), object_hook=byteify)


def get_uuid():
    return uuid.uuid4().hex


class Ctx(object):
    MAXLEN = 5
    run_queue = queue.Queue()
    busy = False
    result = None
    results = {}
    ids = []
    current_id = None

    @staticmethod
    def enqueue(config, request_id):
        Ctx.busy = True
        config['request_id'] = request_id
        Ctx.run_queue.put(config)

        if len(Ctx.ids) >= Ctx.MAXLEN:
            try:
                del Ctx.results[Ctx.ids.pop(0)]
            except KeyError:
                pass
        Ctx.ids.append(request_id)

    @staticmethod
    def dequeue():
        config = Ctx.run_queue.get()
        Ctx.current_id = config['request_id']
        return config

    @staticmethod
    def release():
        Ctx.current_id = None
        Ctx.busy = False

    @staticmethod
    def set_result(res):
        res['request_id'] = Ctx.current_id
        Ctx.results[Ctx.current_id] = res
        Ctx.result = res

    @staticmethod
    def get_result(request_id=None):
        if request_id:
            try:
                res = Ctx.results[request_id]
            except KeyError:
                return None

            if Ctx.result and request_id == Ctx.results['request_id']:
                Ctx.result = None

            return res
        res = Ctx.result
        if res:
            Ctx.result = None
        return res

    @staticmethod
    def is_busy():
        return Ctx.busy

    @staticmethod
    def get_current_request_id():
        return Ctx.current_id


def setup_flask():
    app = Flask(__name__)
    busy_json = result_json(STATUS_ERROR, 'there is already an NFVbench request running')
    not_busy_json = result_json(STATUS_ERROR, 'no pending NFVbench run')
    not_found_msg = 'results not found'
    pending_msg = 'NFVbench run still pending'

    # --------- HTTP requests ------------

    @app.route('/version', methods=['GET'])
    def _version():
        return __version__

    @app.route('/start_run', methods=['POST'])
    def _start_run():
        config = load_json(request.json)
        if not config:
            config = {}
        if Ctx.is_busy():
            return jsonify(busy_json)
        request_id = get_uuid()
        Ctx.enqueue(config, request_id)
        return jsonify(result_json(STATUS_PENDING, pending_msg, request_id))

    @app.route('/status', defaults={'request_id': None}, methods=['GET'])
    @app.route('/status/<request_id>', methods=['GET'])
    def _get_status(request_id):
        if request_id:
            if Ctx.is_busy() and request_id == Ctx.get_current_request_id():
                # task with request_id still pending
                return jsonify(result_json(STATUS_PENDING, pending_msg, request_id))

            res = Ctx.get_result(request_id)
            if res:
                # found result for given request_id
                return jsonify(res)
            # result for given request_id not found
            return jsonify(result_json(STATUS_NOT_FOUND, not_found_msg, request_id))
        if Ctx.is_busy():
            # task still pending, return with request_id
            return jsonify(result_json(STATUS_PENDING,
                                       pending_msg,
                                       Ctx.get_current_request_id()))

        res = Ctx.get_result()
        if res:
            return jsonify(res)
        return jsonify(not_busy_json)

    return app

class WebServer(object):
    """This class takes care of the web server. Caller should simply create an instance
    of this class and pass a runner object then invoke the run method
    """

    def __init__(self, runner, fluent_logger):
        self.nfvbench_runner = runner
        self.app = setup_flask()
        self.fluent_logger = fluent_logger

    def run(self, host, port):

        # app.run will not return so we need to run it in a background thread so that
        # the calling thread (main thread) can keep doing work
        Thread(target=self.app.run, args=(host, port)).start()

        # wait for run requests
        # the runner must be executed from the main thread (Trex client library requirement)
        while True:

            # print 'main thread waiting for requests...'
            config = Ctx.dequeue()
            # print 'main thread processing request...'
            # print config
            try:
                # remove unfilled values as we do not want them to override default values with None
                config = {k: v for k, v in list(config.items()) if v is not None}
                with RunLock():
                    if self.fluent_logger:
                        self.fluent_logger.start_new_run()
                    results = self.nfvbench_runner.run(config, config)
            except Exception as exc:
                results = result_json(STATUS_ERROR, str(exc))
                LOG.exception('NFVbench runner exception:')

            # this might overwrite a previously unfetched result
            Ctx.set_result(results)
            try:
                summary = NFVBenchSummarizer(results['result'], self.fluent_logger)
                LOG.info(str(summary))
            except KeyError:
                # in case of error, 'result' might be missing
                if 'error_message' in results:
                    LOG.error(results['error_message'])
                else:
                    LOG.error('REST request completed without results or error message')
            Ctx.release()
            if self.fluent_logger:
                self.fluent_logger.send_run_summary(True)
