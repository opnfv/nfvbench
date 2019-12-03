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
#

from attrdict import AttrDict
import yaml

from .log import LOG

def config_load(file_name, from_cfg=None, whitelist_keys=None):
    """Load a yaml file into a config dict, merge with from_cfg if not None
    The config file content taking precedence in case of duplicate
    """
    try:
        with open(file_name) as fileobj:
            cfg = AttrDict(yaml.safe_load(fileobj))
    except IOError:
        raise Exception("Configuration file at '{}' was not found. Please use correct path "
                        "and verify it is visible to container if you run nfvbench in container."
                        .format(file_name))

    if from_cfg:
        if not whitelist_keys:
            whitelist_keys = []
        _validate_config(cfg, from_cfg, whitelist_keys)
        cfg = from_cfg + cfg

    return cfg


def config_loads(cfg_text, from_cfg=None, whitelist_keys=None):
    """Same as config_load but load from a string
    """
    try:
        cfg = AttrDict(yaml.safe_load(cfg_text))
    except TypeError:
        # empty string
        cfg = AttrDict()
    except ValueError as e:
        # In case of wrong path or file not readable or string not well formatted
        LOG.error("String %s is not well formatted. Please verify your yaml/json string. "
                  "If string is a file path, file was not found. Please use correct path and "
                  "verify it is visible to container if you run nfvbench in container.", cfg_text)
        raise Exception(e)
    if from_cfg:
        if not whitelist_keys:
            whitelist_keys = []
        _validate_config(cfg, from_cfg, whitelist_keys)
        return from_cfg + cfg
    return cfg


def _validate_config(subset, superset, whitelist_keys):
    def get_err_config(subset, superset):
        result = {}
        for k, v in list(subset.items()):
            if k not in whitelist_keys:
                if k not in superset:
                    result.update({k: v})
                elif v is not None and superset[k] is not None:
                    if not isinstance(v, type(superset[k])):
                        result.update({k: v})
                        continue
                if isinstance(v, dict):
                    res = get_err_config(v, superset[k])
                    if res:
                        result.update({k: res})
        if not result:
            return None
        return result

    err_cfg = get_err_config(subset, superset)
    if err_cfg:
        err_msg = 'The provided configuration has unknown options or values with invalid type: '\
                  + str(err_cfg)
        LOG.error(err_msg)
        raise Exception(err_msg)
