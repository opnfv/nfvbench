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
import Queue
import traceback
import uuid

from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request

from flask_socketio import emit
from flask_socketio import SocketIO
from fluentd import FluentLogHandler
from summarizer import NFVBenchSummarizer

from log import LOG
from utils import byteify
from utils import RunLock


# this global cannot reside in Ctx because of the @app and @socketio decorators
app = None
socketio = None

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
    run_queue = Queue.Queue()
    busy = False
    result = None
    request_from_socketio = False
    results = {}
    ids = []
    current_id = None

    @staticmethod
    def enqueue(config, request_id, from_socketio=False):
        Ctx.busy = True
        Ctx.request_from_socketio = from_socketio
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

            if Ctx.result and request_id == Ctx.result['request_id']:
                Ctx.result = None

            return res
        else:
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


def setup_flask(root_path):
    global socketio
    global app
    app = Flask(__name__)
    app.root_path = root_path
    socketio = SocketIO(app, async_mode='threading')
    busy_json = result_json(STATUS_ERROR, 'there is already an NFVbench request running')
    not_busy_json = result_json(STATUS_ERROR, 'no pending NFVbench run')
    not_found_msg = 'results not found'
    pending_msg = 'NFVbench run still pending'

    # --------- socketio requests ------------

    @socketio.on('start_run')
    def _socketio_start_run(config):
        if not Ctx.is_busy():
            Ctx.enqueue(config, get_uuid(), from_socketio=True)
        else:
            emit('error', {'reason': 'there is already an NFVbench request running'})

    @socketio.on('echo')
    def _socketio_echo(config):
        emit('echo', config)

    # --------- HTTP requests ------------

    @app.route('/')
    def _index():
        return render_template('index.html')

    @app.route('/echo', methods=['GET'])
    def _echo():
        config = request.json
        return jsonify(config)

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
        else:
            if Ctx.is_busy():
                # task still pending, return with request_id
                return jsonify(result_json(STATUS_PENDING,
                                           pending_msg,
                                           Ctx.get_current_request_id()))

            res = Ctx.get_result()
            if res:
                return jsonify(res)
            return jsonify(not_busy_json)


class WebSocketIoServer(object):
    """This class takes care of the web socketio server, accepts websocket events, and sends back
    notifications using websocket events (send_ methods). Caller should simply create an instance
    of this class and pass a runner object then invoke the run method
    """

    def __init__(self, http_root, runner, logger):
        self.nfvbench_runner = runner
        setup_flask(http_root)
        self.fluent_logger = logger
        self.result_fluent_logger = None
        if self.fluent_logger:
            self.result_fluent_logger = \
                FluentLogHandler("resultnfvbench",
                                 fluentd_ip=self.fluent_logger.sender.host,
                                 fluentd_port=self.fluent_logger.sender.port)
            self.result_fluent_logger.runlogdate = self.fluent_logger.runlogdate

    def run(self, host='127.0.0.1', port=7556):

        # socketio.run will not return so we need to run it in a background thread so that
        # the calling thread (main thread) can keep doing work
        socketio.start_background_task(target=socketio.run, app=app, host=host, port=port)

        # wait for run requests
        # the runner must be executed from the main thread (Trex client library requirement)
        while True:

            # print 'main thread waiting for requests...'
            config = Ctx.dequeue()
            # print 'main thread processing request...'
            print config
            try:
                # remove unfilled values as we do not want them to override default values with None
                config = {k: v for k, v in config.items() if v is not None}
                with RunLock():
                    results = self.nfvbench_runner.run(config, config)
            except Exception as exc:
                print 'NFVbench runner exception:'
                traceback.print_exc()
                results = result_json(STATUS_ERROR, str(exc))
                LOG.exception()

            if Ctx.request_from_socketio:
                socketio.emit('run_end', results)
            else:
                # this might overwrite a previously unfetched result
                Ctx.set_result(results)
            if self.fluent_logger:
                self.result_fluent_logger.runlogdate = self.fluent_logger.runlogdate
            summary = NFVBenchSummarizer(results['result'], self.result_fluent_logger)
            LOG.info(str(summary))
            Ctx.release()
            if self.fluent_logger:
                self.fluent_logger.send_run_summary(True)

    def send_interval_stats(self, time_ms, tx_pps, rx_pps, drop_pct):
        stats = {'time_ms': time_ms, 'tx_pps': tx_pps, 'rx_pps': rx_pps, 'drop_pct': drop_pct}
        socketio.emit('run_interval_stats', stats)

    def send_ndr_found(self, ndr_pps):
        socketio.emit('ndr_found', {'rate_pps': ndr_pps})

    def send_pdr_found(self, pdr_pps):
        socketio.emit('pdr_found', {'rate_pps': pdr_pps})
