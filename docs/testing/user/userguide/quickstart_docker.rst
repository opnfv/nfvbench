.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

===========================================
NFVbench Installation and Quick Start Guide
===========================================

.. _docker_installation:

Make sure you satisfy the `hardware and software requirements <requirements>` before you start .


1. Container installation
-------------------------

To pull the latest NFVbench container image:

.. code-block:: bash

    docker pull opnfv/nfvbench/nfvbench

2. Docker Container configuration
---------------------------------

The NFVbench container requires the following Docker options to operate properly.

+------------------------------------------------------+------------------------------------------------------+
| Docker options                                       | Description                                          |
+======================================================+======================================================+
| -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) | needed by kernel modules in the container            |
+------------------------------------------------------+------------------------------------------------------+
| -v /dev:/dev                                         | needed by kernel modules in the container            |
+------------------------------------------------------+------------------------------------------------------+
| -v $PWD:/tmp/nfvbench                                | optional but recommended to pass files between the   |
|                                                      | host and the docker space (see examples below)       |
|                                                      | Here we map the current directory on the host to the |
|                                                      | /tmp/nfvbench director in the container but any      |
|                                                      | other similar mapping can work as well               |
+------------------------------------------------------+------------------------------------------------------+
| --net=host                                           | (optional) needed if you run the NFVbench ok         |
|                                                      | server in the container (or use any appropriate      |
|                                                      | docker network mode other than "host")               |
+------------------------------------------------------+------------------------------------------------------+
| --privileged                                         | (optional) required if SELinux is enabled on the host|
+------------------------------------------------------+------------------------------------------------------+
| -e HOST="127.0.0.1"                                  | (optional) required if REST server is enabled        |
+------------------------------------------------------+------------------------------------------------------+
| -e PORT=7556                                         | (optional) required if REST server is enabled        |
+------------------------------------------------------+------------------------------------------------------+
| -e CONFIG_FILE="/root/nfvbenchconfig.json            | (optional) required if REST server is enabled        |
+------------------------------------------------------+------------------------------------------------------+

It can be convenient to write a shell script (or an alias) to automatically insert the necessary options.

The minimal configuration file required must specify the openrc file to use (using in-container path), the PCI addresses of the 2 NIC ports to use
for generating traffic and the line rate (in each direction) of each of these 2 interfaces.

Here is an example of mimimal configuration where:
the openrc file is located on the host current directory which is mapped under /tmp/nfvbench in the container (this is achieved using -v $PWD:/tmp/nfvbench)
the 2 NIC ports to use for generating traffic have the PCI addresses "04:00.0" and "04:00.1"

.. code-block:: bash

    {
        "openrc_file": "/tmp/nfvbench/openrc",
        "traffic_generator": {
            "generator_profile": [
                {
                    "interfaces": [
                        {
                            "pci": "04:00.0",
                            "port": 0,
                        },
                        {
                            "pci": "04:00.1",
                            "port": 1,
                        }
                    ],
                    "intf_speed": "10Gbps",
                    "ip": "127.0.0.1",
                    "name": "trex-local",
                    "tool": "TRex"
                }
            ]
        }
    }

The other options in the minimal configuration must be present and must have the same values as above.

3. Start the Docker container
-----------------------------
As for any Docker container, you can execute NFVbench measurement sessions using a temporary container ("docker run" - which exits after each NFVbench run)
or you can decide to run the NFVbench container in the background then execute one or more NFVbench measurement sessions on that container ("docker exec").

The former approach is simpler to manage (since each container is started and terminated after each command) but incurs a small delay at start time (several seconds).
The second approach is more responsive as the delay is only incurred once when starting the container.

We will take the second approach and start the NFVbench container in detached mode with the name "nfvbench" (this works with bash, prefix with "sudo" if you do not use the root login)

To run NFVBench without server mode

.. code-block:: bash

    docker run --detach --net=host --privileged -v $PWD:/tmp/nfvbench -v /dev:/dev -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) --name nfvbench opnfv/nfvbench

To run NFVBench enabling REST server (mount the configuration json and the path for openrc)

.. code-block:: bash

    docker run --detach --net=host --privileged -e HOST="127.0.0.1" -e PORT=7556 --e CONFIG_FILE="/tmp/nfvbench/nfvbenchconfig.json -v $PWD:/tmp/nfvbench -v /dev:/dev -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) --name nfvbench opnfv/nfvbench start_rest_server


The create an alias to make it easy to execute nfvbench commands directly from the host shell prompt:

.. code-block:: bash

    alias nfvbench='docker exec -it nfvbench nfvbench'

The next to last "nfvbench" refers to the name of the container while the last "nfvbench" refers to the NFVbench binary that is available to run in the container.

To verify it is working:

.. code-block:: bash

    nfvbench --version
    nfvbench --help


4. NFVbench configuration
-------------------------

Create a new file containing the minimal configuration for NFVbench, we can call it any name, for example "my_nfvbench.cfg" and paste the following yaml template in the file:

.. code-block:: bash

  openrc_file:
  traffic_generator:
      generator_profile:
          - name: trex-local
            tool: TRex
            ip: 127.0.0.1
            cores: 3
            interfaces:
              - port: 0
                switch_port:
                pci:
              - port: 1
                switch_port:
                pci:
            intf_speed: 10Gbps

NFVbench requires an ``openrc`` file to connect to OpenStack using the OpenStack API. This file can be downloaded from the OpenStack Horizon dashboard (refer to the OpenStack documentation on how to
retrieve the openrc file). The file pathname in the container must be stored in the "openrc_file" property. If it is stored on the host in the current directory, its full pathname must start with /tmp/nfvbench (since the current directory is mapped to /tmp/nfvbench in the container).

The required configuration is the PCI address of the 2 physical interfaces that will be used by the traffic generator. The PCI address can be obtained for example by using the "lspci" Linux command. For example:

.. code-block:: bash

    [root@sjc04-pod6-build ~]# lspci | grep 710
    0a:00.0 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.1 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.2 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.3 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)


Example of edited configuration with an OpenStack RC file stored in the current directory with the "openrc" name, and
PCI addresses "0a:00.0" and "0a:00.1" (first 2 ports of the quad port NIC):

.. code-block:: bash

  openrc_file: /tmp/nfvbench/openrc
  traffic_generator:
      generator_profile:
          - name: trex-local
            tool: TRex
            ip: 127.0.0.1
            cores: 3
            interfaces:
              - port: 0
                switch_port:
                pci: 0a:00.0
              - port: 1
                switch_port:
                pci: 0a:00.1
            intf_speed: 10Gbps

Alternatively, the full template with comments can be obtained using the --show-default-config option in yaml format:

.. code-block:: bash

    nfvbench --show-default-config > my_nfvbench.cfg

Edit the nfvbench.cfg file to only keep those properties that need to be modified (preserving the nesting)


5. Run NFVbench
---------------

To do a single run at 10,000pps bi-directional (or 5kpps in each direction) using the PVP packet path:

.. code-block:: bash

   nfvbench -c /tmp/nfvbench/my_nfvbench.cfg --rate 10kpps

NFVbench options used:

* ``-c /tmp/nfvbench/my_nfvbench.cfg`` : specify the config file to use (this must reflect the file path from inside the container)
* ``--rate 10kpps`` : specify rate of packets for test for both directions using the kpps unit (thousands of packets per second)

This should produce a result similar to this (a simple run with the above options should take less than 5 minutes):

.. code-block:: none

  [TBP]


7. Terminating the NFVbench container
-------------------------------------
When no longer needed, the container can be terminated using the usual docker commands:

.. code-block:: bash

    docker kill nfvbench
    docker rm nfvbench

