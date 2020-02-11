.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc


XTesting integration
--------------------

In this mode, the NFVbench code will reside in a container running in the background. This container will not run anything in the background.
XTesting python library is then used to invoke a new NFVbench benchmark run using docker exec and run_tests command.
The $HOME/nfvbench directory on the host is mapped on the /tmp/nfvbench in the container to facilitate file sharing between the 2 environments and an nfvbench.cfg file needs to be present in this folder.

XTesting use testcases.yaml file to list and run tests.
One basic testcases.yaml is provided by NFVBench natively but can be override.

Override testcases.yaml file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To replace existing testcases.yaml file:

.. code-block:: bash

   docker exec -it nfvbench cp /tmp/nfvbench/testcases.yaml /usr/local/lib/python3.6/dist-packages/xtesting/ci/testcases.yaml


Example of XTesting test case
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


Examples of run
~~~~~~~~~~~~~~~

To do a single run at 10,000pps bi-directional (or 5kpps in each direction) using the PVP packet path:

.. code-block:: bash

   docker exec -it nfvbench run_tests -t 10kpps-pvp-run

XTesting option used:

* ``-t 10kpps-pvp-run`` : specify the test case to run

To pass all test cases:

.. code-block:: bash

   docker exec -it nfvbench run_tests -t all

XTesting option used:

* ``-t all`` : select all test cases existing in testcases.yaml file

