# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
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

_product_name = 'nfvbench'


def setup(mute_stdout=False):
    # ADD RUN_SUMMARY as a custom log level
    logging.addLevelName(LogLevel.RUN_SUMMARY, "RUN_SUMMARY")

    def run_summary(self, message, *args, **kws):
        # Yes, logger takes its '*args' as 'args'.
        if self.isEnabledFor(LogLevel.RUN_SUMMARY):
            self._log(LogLevel.RUN_SUMMARY, message, args, **kws)

    logging.Logger.run_summary = run_summary
    # logging.basicConfig()
    if mute_stdout:
        handler = logging.NullHandler()
    else:
        formatter_str = '%(asctime)s %(levelname)s %(message)s'
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(formatter_str))

    # Add handler to logger
    logger = logging.getLogger(_product_name)
    logger.addHandler(handler)
    # disable unnecessary information capture
    logging.logThreads = 0
    logging.logProcesses = 0
    logging._srcfile = None


def add_file_logger(logfile):
    if logfile:
        file_formatter_str = '%(asctime)s %(levelname)s %(message)s'
        file_handler = logging.FileHandler(logfile, mode='w')
        file_handler.setFormatter(logging.Formatter(file_formatter_str))
        logger = logging.getLogger(_product_name)
        logger.addHandler(file_handler)


def set_level(debug=False):
    log_level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger(_product_name)
    logger.setLevel(log_level)


def getLogger():
    logger = logging.getLogger(_product_name)
    return logger


LOG = getLogger()


class LogLevel(object):
    INFO = 20
    WARNING = 30
    ERROR = 40
    RUN_SUMMARY = 100
    highest_level = INFO

    @staticmethod
    def get_highest_level_log_name():
        if LogLevel.highest_level == LogLevel.INFO:
            return "GOOD RUN"
        elif LogLevel.highest_level == LogLevel.WARNING:
            return "RUN WITH WARNINGS"
        else:
            return "RUN WITH ERRORS"
