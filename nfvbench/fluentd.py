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

import logging

from datetime import datetime
from fluent import sender
import pytz


class FluentLogHandler(logging.Handler):
    '''This is a minimalist log handler for use with Fluentd

    Needs to be attached to a logger using the addHandler method.
    It only picks up from every record:
    - the formatted message (no timestamp and no level)
    - the level name
    - the runlogdate (to tie multiple run-related logs together)
    The timestamp is retrieved by the fluentd library.
    There will be only one instance of FluentLogHandler running.
    '''

    def __init__(self, fluentd_configs):
        logging.Handler.__init__(self)
        self.log_senders = []
        self.result_senders = []
        self.runlogdate = "1970-01-01T00:00:00.000000+0000"
        self.formatter = logging.Formatter('%(message)s')
        for fluentd_config in fluentd_configs:
            if fluentd_config.logging_tag:
                self.log_senders.append(
                    sender.FluentSender(fluentd_config.logging_tag, host=fluentd_config.ip,
                                        port=fluentd_config.port))
            if fluentd_config.result_tag:
                self.result_senders.append(
                    sender.FluentSender(fluentd_config.result_tag, host=fluentd_config.ip,
                                        port=fluentd_config.port))
        self.__warning_counter = 0
        self.__error_counter = 0

    def start_new_run(self):
        '''Delimitate a new run in the stream of records with a new timestamp
        '''
        # reset counters
        self.__warning_counter = 0
        self.__error_counter = 0
        self.runlogdate = self.__get_timestamp()
        # send start record
        self.__send_start_record()

    def emit(self, record):
        data = {
            "loglevel": record.levelname,
            "message": self.formatter.format(record),
            "@timestamp": self.__get_timestamp()
        }
        # if runlogdate is Jan 1st 1970, it's a log from server (not an nfvbench run)
        # so do not send runlogdate
        if self.runlogdate != "1970-01-01T00:00:00.000000+0000":
            data["runlogdate"] = self.runlogdate

        self.__update_stats(record.levelno)
        for log_sender in self.log_senders:
            log_sender.emit(None, data)

    # this function is called by summarizer, and used for sending results
    def record_send(self, record):
        for result_sender in self.result_senders:
            result_sender.emit(None, record)

    # send START log record for each run
    def __send_start_record(self):
        data = {
            "runlogdate": self.runlogdate,
            "loglevel": "START",
            "message": "NFVBENCH run is started",
            "numloglevel": 0,
            "numerrors": 0,
            "numwarnings": 0,
            "@timestamp": self.__get_timestamp()
        }
        for log_sender in self.log_senders:
            log_sender.emit(None, data)

    # send stats related to the current run and reset state for a new run
    def send_run_summary(self, run_summary_required):
        if run_summary_required or self.__get_highest_level() == logging.ERROR:
            data = {
                "loglevel": "RUN_SUMMARY",
                "message": self.__get_highest_level_desc(),
                "numloglevel": self.__get_highest_level(),
                "numerrors": self.__error_counter,
                "numwarnings": self.__warning_counter,
                "@timestamp": self.__get_timestamp()
            }
            # if runlogdate is Jan 1st 1970, it's a log from server (not an nfvbench run)
            # so don't send runlogdate
            if self.runlogdate != "1970-01-01T00:00:00.000000+0000":
                data["runlogdate"] = self.runlogdate
            for log_sender in self.log_senders:
                log_sender.emit(None, data)

    def __get_highest_level(self):
        if self.__error_counter > 0:
            return logging.ERROR
        if self.__warning_counter > 0:
            return logging.WARNING
        return logging.INFO

    def __get_highest_level_desc(self):
        highest_level = self.__get_highest_level()
        if highest_level == logging.INFO:
            return "GOOD RUN"
        if highest_level == logging.WARNING:
            return "RUN WITH WARNINGS"
        return "RUN WITH ERRORS"

    def __update_stats(self, levelno):
        if levelno == logging.WARNING:
            self.__warning_counter += 1
        elif levelno == logging.ERROR:
            self.__error_counter += 1

    def __get_timestamp(self):
        return datetime.utcnow().replace(tzinfo=pytz.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f%z")
