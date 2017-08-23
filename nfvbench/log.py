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
