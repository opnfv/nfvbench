.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

===========================================
NFVbench Installation and Quick Start Guide
===========================================

.. _docker_installation:

Make sure you satisfy the `hardware and software requirements <requirements>` before you start .


NFVbench can be used in CLI mode or in REST server mode.
The CLI mode allows to run NFVbench benchmarks from the CLI. The REST server mode allows to run NFVbench benchmarks through a REST interface.

1. Container installation
-------------------------

To pull the latest NFVbench container image:

.. code-block:: bash

    docker pull opnfv/nfvbench

2. NFVbench configuration file
------------------------------

Create a directory under $HOME called nfvbench to store the minimal configuration file:

.. code-block:: bash

    mkdir $HOME/nfvbench

Create a new file containing the minimal configuration for NFVbench, we can call it any name, for example "nfvbench.cfg" and paste the following yaml template in the file:

.. code-block:: bash

  openrc_file: /tmp/nfvbench/openrc
  traffic_generator:
      generator_profile:
          - name: trex-local
            tool: TRex
            ip: 127.0.0.1
            cores: 3
            software_mode: false
            interfaces:
              - port: 0
                pci: "0a:00.0"
              - port: 1
                pci: "0a:00.1"
            intf_speed:

If OpenStack is not used, the openrc_file property can be removed.

If OpenStack is used, the openrc_file property must contain a valid container pathname of the OpenStack ``openrc`` file to connect to OpenStack using the OpenStack API.
This file can be downloaded from the OpenStack Horizon dashboard (refer to the OpenStack documentation on how to
retrieve the openrc file). This property must point to a valid pathname in the container (/tmp/nfvbench/openrc).
We will map the host $HOME/nfvbench directory to the container /tmp/nfvbench directory and name the file "openrc".
The file name viewed from the container will be "/tmp/nfvbench/openrc" (see container file pathname mapping in the next sections).

The PCI address of the 2 physical interfaces that will be used by the traffic generator must be configured.
The PCI address can be obtained for example by using the "lspci" Linux command. For example:

.. code-block:: bash

    [root@sjc04-pod6-build ~]# lspci | grep 710
    0a:00.0 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.1 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.2 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)
    0a:00.3 Ethernet controller: Intel Corporation Ethernet Controller X710 for 10GbE SFP+ (rev 01)

In the above example, the PCI addresses "0a:00.0" and "0a:00.1" (first 2 ports of the quad port NIC) are used.

.. warning::

    You have to put quotes around the pci addresses as shown in the above example, otherwise TRex will read it wrong.
    The other fields in the minimal configuration must be present and must have the same values as above.


3. Starting NFVbench in CLI mode
--------------------------------

In this mode, the NFVbench code will reside in a container running in the background. This container will not run anything in the background.
An alias is then used to invoke a new NFVbench benchmark run using docker exec.
The $HOME/nfvbench directory on the host is mapped on the /tmp/nfvbench in the container to facilitate file sharing between the 2 environments.

.. _start-nfvbench-container:

Start NFVbench container
~~~~~~~~~~~~~~~~~~~~~~~~
The NFVbench container can be started using docker run command or using docker compose.

To run NFVBench in CLI mode using docker run:

.. code-block:: bash

    docker run --name nfvbench --detach --privileged -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) -v /usr/src/kernels:/usr/src/kernels -v /dev:/dev -v $HOME/nfvbench:/tmp/nfvbench opnfv/nfvbench

+-------------------------------------------------------+-------------------------------------------------------+
| Docker options                                        | Description                                           |
+=======================================================+=======================================================+
| --name nfvbench                                       | container name is "nfvbench"                          |
+-------------------------------------------------------+-------------------------------------------------------+
| --detach                                              | run container in background                           |
+-------------------------------------------------------+-------------------------------------------------------+
| --privileged                                          | (optional) required if SELinux is enabled on the host |
+-------------------------------------------------------+-------------------------------------------------------+
| -v /lib/modules:/lib/modules                          | needed by kernel modules in the container             |
+-------------------------------------------------------+-------------------------------------------------------+
| -v /usr/src/kernels:/usr/src/kernels                  | needed by TRex to build kernel modules when needed    |
+-------------------------------------------------------+-------------------------------------------------------+
| -v /dev:/dev                                          | needed by kernel modules in the container             |
+-------------------------------------------------------+-------------------------------------------------------+
| -v $HOME/nfvbench:/tmp/nfvbench                       | folder mapping to pass files between the              |
|                                                       | host and the docker space (see examples below)        |
|                                                       | Here we map the $HOME/nfvbench directory on the host  |
|                                                       | to the /tmp/nfvbench director in the container.       |
|                                                       | Any other mapping can work as well                    |
+-------------------------------------------------------+-------------------------------------------------------+
| opnfv/nfvbench                                        | container image name                                  |
+-------------------------------------------------------+-------------------------------------------------------+

To run NFVbench using docker compose, create the docker-compose.yml file and paste the following content:

.. code-block:: bash

    version: '3'
    services:
        nfvbench:
            image: "opnfv/nfvbench"
            container_name: "nfvbench"
            volumes:
                - /dev:/dev
                - /usr/src/kernels:/usr/src/kernels
                - /lib/modules:/lib/modules
                - ${HOME}/nfvbench:/tmp/nfvbench
            network_mode: "host"
            privileged: true

Then start the container in detached mode:

.. code-block:: bash

    docker-compose up -d

Requesting an NFVbench benchmark run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create an alias to make it easy to execute nfvbench commands directly from the host shell prompt:

.. code-block:: bash

    alias nfvbench='docker exec -it nfvbench nfvbench'

The next to last "nfvbench" refers to the name of the container while the last "nfvbench" refers to the NFVbench binary that is available to run inside the container.

Once the alias is set, NFVbench runs can simply be requested from teh command line using "nfvbench <options>".

To verify it is working:

.. code-block:: bash

    nfvbench --version
    nfvbench --help

Example of run
~~~~~~~~~~~~~~

To do a single run at 10,000pps bi-directional (or 5kpps in each direction) using the PVP packet path:

.. code-block:: bash

   nfvbench -c /tmp/nfvbench/nfvbench.cfg --rate 10kpps

NFVbench options used:

* ``-c /tmp/nfvbench/nfvbench.cfg`` : specify the config file to use
* ``--rate 10kpps`` : specify rate of packets for test for both directions using the kpps unit (thousands of packets per second)


Retrieve complete configuration file as template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The full configuration file template with comments (yaml format) can be obtained using the --show-default-config option in order to use more advanced configuration options:

.. code-block:: bash

    nfvbench --show-default-config > $HOME/nfvbench/full_nfvbench.cfg

Edit the full_nfvbench.cfg file to only keep those properties that need to be modified (preserving the nesting).


4. Start NFVbench in REST server mode
-------------------------------------
In this mode, the NFVbench REST server will run in the container.
The $HOME/nfvbench directory on the host is mapped on the /tmp/nfvbench in the container to facilitate file sharing between the 2 environments.

Start NFVbench container
~~~~~~~~~~~~~~~~~~~~~~~~

To start the NFVbench container with REST server using docker run cli:

.. code-block:: bash

    docker run --name nfvbench --detach --privileged --net=host -e CONFIG_FILE="/tmp/nfvbench/nfvbench.cfg" -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) -v /usr/src/kernels:/usr/src/kernels -v /dev:/dev -v $HOME/nfvbench:/tmp/nfvbench opnfv/nfvbench start_rest_server

REST mode requires the same arguments as CLI mode and adds the following options:
+-------------------------------------------------------+-------------------------------------------------------+
| Docker options                                        | Description                                           |
+=======================================================+=======================================================+
| --net=host                                            | use "host" docker networking mode                     |
|                                                       | Other modes (such as NAT) could be used if required   |
|                                                       | with proper adjustment of the port to use for REST    |
+-------------------------------------------------------+-------------------------------------------------------+
| -e CONFIG_FILE="/tmp/nfvbench/nfvbench.cfg"           | (optional)                                            |
|                                                       | specify the initial NFVbench config file to use.      |
|                                                       | defaults to none                                      |
+-------------------------------------------------------+-------------------------------------------------------+
| start_rest_server                                     | to request a REST server to run in background in the  |
|                                                       | container                                             |
+-------------------------------------------------------+-------------------------------------------------------+
| -e HOST="127.0.0.1"                                   | (optional)                                            |
|                                                       | specify the IP address to listen to.                  |
|                                                       | defaults to 127.0.0.1                                 |
+-------------------------------------------------------+-------------------------------------------------------+
| -e PORT=7555                                          | (optional)                                            |
|                                                       | specify the port address to listen to.                |
|                                                       | defaults to 7555                                      |
+-------------------------------------------------------+-------------------------------------------------------+


The initial configuration file is optional but is handy to define mandatory deployment parameters that are common to all subsequent REST requests.
If this initial configuration file is not passed at container start time, it must be included in every REST request.

To start the NFVbench container with REST server using docker compose, use the following compose file:

.. code-block:: bash

    version: '3'
    services:
        nfvbench:
            image: "opnfv/nfvbench"
            container_name: "nfvbench_server"
            command: start_rest_server
            volumes:
                - /dev:/dev
                - /usr/src/kernels:/usr/src/kernels
                - /lib/modules:/lib/modules
                - ${HOME}/nfvbench:/tmp/nfvbench
            network_mode: "host"
            environment:
                - HOST="127.0.0.1"
                - PORT=7555
            privileged: true

Requesting an NFVbench benchmark run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To request a benchmark run, you must create a JSON document that describes the benchmark and send it to the NFVbench server in the body of a POST request.


Examples of REST requests
~~~~~~~~~~~~~~~~~~~~~~~~~
In this example, we will use curl to interact with the NFVbench REST server.

Query the NFVbench version:

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -G http://127.0.0.1:7555/version
    3.1.1

This is the JSON for a fixed rate run at 10,000pps bi-directional (or 5kpps in each direction) using the PVP packet path:

.. code-block:: bash

    {"rate": "10kpps"}

This is the curl request to send this benchmark request to the NFVbench server:

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -H "Accept: application/json" -H "Content-type: application/json" -X POST -d '{"rate": "10kpps"}' http://127.0.0.1:7555/start_run
    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }
    [root@sjc04-pod3-mgmt ~]#

This request will return immediately with status set to "PENDING" if the request was started successfully.

The status can be polled until the run completes. Here the poll returns a "PENDING" status, indicating the run is still not completed:

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -G http://127.0.0.1:7555/status
    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }
    [root@sjc04-pod3-mgmt ~]#

Finally, the status request returns a "OK" status along with the full results (truncated here):

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -G http://127.0.0.1:7555/status
    {
      "result": {
        "benchmarks": {
          "network": {
            "service_chain": {
              "PVP": {
                "result": {
                  "bidirectional": true,

    ...

      "status": "OK"
    }
    [root@sjc04-pod3-mgmt ~]#


Retrieve complete configuration file as template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


7. Terminating the NFVbench container
-------------------------------------
When no longer needed, the container can be terminated using the usual docker commands:

.. code-block:: bash

    docker kill nfvbench
    docker rm nfvbench
