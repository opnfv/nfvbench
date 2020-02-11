.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0


Xtesting integration
--------------------

For test automation purpose, Xtesting framework can be used as an executor of NFVBench test cases and called by a CI chain (Jenkins, Gitlab CI ...).
Xtesting use a testcases.yaml file to list and run test case. One basic testcases.yaml is provided by NFVBench natively but can be override.

Example of CI scenario:

.. image:: images/nfvbench-xtesting.png

1. Run NFVBench container using Xtesting python library

The NFVbench container can be started using docker run command.

To run NFVBench using docker run:

.. code-block:: bash

    docker run --rm \
        -e TEST_DB_URL=http://127.0.0.1:8000/api/v1/results \
        -e NODE_NAME=nfvbench \
        -e BUILD_TAG=$BUILD_TAG \
        --privileged \
        -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) \
        -v /usr/src/kernels:/usr/src/kernels -v /dev:/dev \
        -v $HOME/nfvbench:/tmp/nfvbench \
        -v $HOME/workspace/$JOB_NAME/results:/var/lib/xtesting/results \
        opnfv/nfvbench run_tests -t 10kpps-pvp-run -r

+---------------------------------------------------------------+------------------------------------------------------------------------+
| Docker options                                                | Description                                                            |
+===============================================================+========================================================================+
| --rm                                                          | clean up container after execution                                     |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -e TEST_DB_URL                                                | (Xtesting) Environnement variable used to export NFVBench results in DB|
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -e NODE_NAME                                                  | (Xtesting) Environnement variable used as result key identifier in DB  |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -e BUILD_TAG                                                  | (Xtesting) Environnement variable used as result key identifier in DB  |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| --privileged                                                  | (optional) required if SELinux is enabled on the host                  |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -v /lib/modules:/lib/modules                                  | needed by kernel modules in the container                              |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -v /usr/src/kernels:/usr/src/kernels                          | needed by TRex to build kernel modules when needed                     |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -v /dev:/dev                                                  | needed by kernel modules in the container                              |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -v $HOME/nfvbench:/tmp/nfvbench                               | folder mapping to pass files between the                               |
|                                                               | host and the docker space (see examples below)                         |
|                                                               | Here we map the $HOME/nfvbench directory on the host                   |
|                                                               | to the /tmp/nfvbench director in the container.                        |
|                                                               | Any other mapping can work as well                                     |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -v $HOME/workspace/$JOB_NAME/results:/var/lib/xtesting/results| (Xtesting) folder mapping to pass files between the                    |
|                                                               | CI chain workspace and the docker space to store Xtesting result files |
|                                                               | in orchestrator (Jenkins, Gitlab ...)                                  |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| opnfv/nfvbench                                                | container image name                                                   |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| run_tests                                                     | (Xtesting) Xtesting command to run test cases                          |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -t 10kpps-pvp-run                                             | (Xtesting) Xtesting parameter: Test case or tier (group of tests)      |
|                                                               | to be executed. It will run all the test if not specified.             |
+---------------------------------------------------------------+------------------------------------------------------------------------+
| -r                                                            | (Xtesting) Xtesting parameter: publish result to database              |
+---------------------------------------------------------------+------------------------------------------------------------------------+

2. Run Xtesting test cases

Executed directly by NFVBench docker entrypoint after docker start.

3. Perform NFVBench test

Xtesting call NFVBench python script to execute test case scenario and wait for run to be terminated.

4. Export NFVBench result

If ``-r`` option is used, results are pushed to a DB through Xtesting.


Override testcases.yaml file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To replace existing testcases.yaml file, at docker run command add following volume:

.. code-block:: bash

    docker run --name nfvbench --detach --privileged -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) -v /usr/src/kernels:/usr/src/kernels -v /dev:/dev -v $HOME/nfvbench:/tmp/nfvbench \
    -v $HOME/xtesting/testcases.yaml:/usr/local/lib/python3.6/dist-packages/xtesting/ci/testcases.yaml \
    opnfv/nfvbench

* ``-v $HOME/xtesting/testcases.yaml:/usr/local/lib/python3.6/dist-packages/xtesting/ci/testcases.yaml`` : volume mapping to pass testcases.yaml file between the host and the docker space. Host path required testcases.yaml file inside.

Example of Xtesting test case
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    ---
    tiers:
        -
            name: nfvbench
            order: 1
            description: 'Data Plane Performance Testing'
            testcases:
                -
                    case_name: 10kpps-pvp-run
                    project_name: nfvbench
                    criteria: 100
                    blocking: true
                    clean_flag: false
                    description: ''
                    run:
                        name: 'bashfeature'
                        args:
                            cmd:
                                - nfvbench -c /tmp/nfvbench/nfvbench.cfg --rate 10kpps


Examples of manual run
~~~~~~~~~~~~~~~~~~~~~~

If NFVBench container is already started in CLI mode (see Starting NFVbench in CLI mode dedicated chapter).
To do a single run at 10,000pps bi-directional (or 5kpps in each direction) using the PVP packet path:

.. code-block:: bash

   docker exec -it nfvbench run_tests -t 10kpps-pvp-run

Xtesting option used:

* ``-t 10kpps-pvp-run`` : specify the test case to run

To pass all test cases:

.. code-block:: bash

   docker exec -it nfvbench run_tests -t all

Xtesting option used:

* ``-t all`` : select all test cases existing in testcases.yaml file

