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
        if [ -n "$OPENRC" ]; then
            if [ -f "$OPENRC" ]; then
                PARAMS+=" -c \"openrc_file: $OPENRC\""
            else
                echo "Aborting... Openrc config file cannot be found in the given path: $OPENRC"
                exit 1
            fi
        else
            echo "Aborting... Openrc config path is absent"
            exit 1
        fi
        eval "nfvbench $PARAMS"
fi