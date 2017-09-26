#!/bin/bash
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

if [ -z "$1" ] ||  [ $1 != 'start_rest_server' ]; then
        tail -f /dev/null
else
        PARAMS="--server /tmp/http_root"
        if [ -n "$HOST" ]; then
                PARAMS+=" --host $HOST"
        fi
        if [ -n "$PORT" ]; then
                PARAMS+=" --port $PORT"
        fi
        if [ -n "$CONFIG_FILE" ]; then
            if [ -f "$CONFIG_FILE" ]; then
                PARAMS+=" -c $CONFIG_FILE"
            fi
        fi
        eval "nfvbench $PARAMS"
fi