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


def setup(product_name):
    # logging.basicConfig()
    formatter_str = '%(asctime)s %(levelname)s %(message)s'
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(formatter_str))

    # Add handler to logger
    logger = logging.getLogger(product_name)
    logger.addHandler(handler)


def set_level(product, debug=False):
    log_level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger(product)
    logger.setLevel(log_level)


def getLogger(product):
    logger = logging.getLogger(product)

    return logger

LOG = getLogger('nfvbench')
