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

import os
import shutil

TREX_OPT = '/opt/trex'


TREX_UNUSED = [
    '_t-rex-64-debug', '_t-rex-64-debug-o', 'bp-sim-64', 'bp-sim-64-debug',
    't-rex-64-debug', 't-rex-64-debug-o', 'automation/__init__.py',
    'automation/graph_template.html',
    'automation/config', 'automation/h_avc.py', 'automation/phantom',
    'automation/readme.txt', 'automation/regression', 'automation/report_template.html',
    'automation/sshpass.exp', 'automation/trex_perf.py', 'wkhtmltopdf-amd64'
]


def remove_unused_libs(path, files):
    """
    Remove files not used by traffic generator.
    """
    for f in files:
        f = os.path.join(path, f)
        try:
            if os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)
        except OSError:
            print("Skipped file:")
            print(f)
            continue


def get_dir_size(start_path='.'):
    """
    Computes size of directory.

    :return: size of directory with subdirectiories
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            try:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
            except OSError:
                continue
    return total_size

if __name__ == "__main__":
    versions = os.listdir(TREX_OPT)
    for version in versions:
        trex_path = os.path.join(TREX_OPT, version)
        print('Cleaning TRex', version)
        try:
            size_before = get_dir_size(trex_path)
            remove_unused_libs(trex_path, TREX_UNUSED)
            size_after = get_dir_size(trex_path)
            print('==== Saved Space ====')
            print(size_before - size_after)
        except OSError:
            import traceback
            print(traceback.print_exc())
            print('Cleanup was not finished.')
