.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

==============
Advanced Usage
==============

This section covers a few examples on how to run NFVbench with multiple different settings.
Below are shown the most common and useful use-cases and explained some fields from a default config file.

How to change any NFVbench run configuration (CLI)
--------------------------------------------------
NFVbench always starts with a default configuration which can further be refined (overridden) by the user from the CLI or from REST requests.

At first have a look at the default config:

.. code-block:: bash

    nfvbench --show-default-config

It is sometimes useful derive your own configuration from a copy of the default config:

.. code-block:: bash

    nfvbench --show-default-config > nfvbench.cfg

At this point you can edit the copy by:

- removing any parameter that is not to be changed (since NFVbench will always load the default configuration, default values are not needed)
- edit the parameters that are to be changed changed

A run with the new confguration can then simply be requested using the -c option and by using the actual path of the configuration file
as seen from inside the container (in this example, we assume the current directory is mapped to /tmp/nfvbench in the container):

.. code-block:: bash

    nfvbench -c /tmp/nfvbench/nfvbench.cfg

The same -c option also accepts any valid yaml or json string to override certain parameters without having to create a configuration file.

NFVbench provides many configuration options as optional arguments. For example the number of flows can be specified using the --flow-count option.

The flow count option can be specified in any of 3 ways:

- by providing a confguration file that has the flow_count value to use (-c myconfig.yaml and myconfig.yaml contains 'flow_count: 100k')
- by passing that yaml paremeter inline (-c "flow_count: 100k") or (-c "{flow_count: 100k}")
- by using the flow count optional argument (--flow-count 100k)

Showing the running configuration
---------------------------------

Because configuration parameters can be overriden, it is sometimes useful to show the final configuration (after all oevrrides are done) by using the --show-config option.
This final configuration is also called the "running" configuration.

For example, this will only display the running configuration (without actually running anything):

.. code-block:: bash

    nfvbench -c "{flow_count: 100k, debug: true}" --show-config


Connectivity and Configuration Check
------------------------------------

NFVbench allows to test connectivity to devices used with the selected packet path.
It runs the whole test, but without actually sending any traffic.
It is also a good way to check if everything is configured properly in the configuration file and what versions of components are used.

To verify everything works without sending any traffic, use the --no-traffic option:

.. code-block:: bash

    nfvbench --no-traffic

Used parameters:

* ``--no-traffic`` or ``-0`` : sending traffic from traffic generator is skipped



Fixed Rate Run
--------------

Fixed rate run is the most basic type of NFVbench usage. It can be used to measure the drop rate with a fixed transmission rate of packets.

This example shows how to run the PVP packet path (which is the default packet path) with multiple different settings:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --no-cleanup --rate 100000pps --duration 30 --interval 15 --json results.json

Used parameters:

* ``-c nfvbench.cfg`` : path to the config file
* ``--no-cleanup`` : resources (networks, VMs, attached ports) are not deleted after test is finished
* ``--rate 100000pps`` : defines rate of packets sent by traffic generator
* ``--duration 30`` : specifies how long should traffic be running in seconds
* ``--interval 15`` : stats are checked and shown periodically (in seconds) in this interval when traffic is flowing
* ``--json results.json`` : collected data are stored in this file after run is finished

.. note:: It is your responsibility to clean up resources if needed when ``--no-cleanup`` parameter is used. You can use the nfvbench_cleanup helper script for that purpose.

The ``--json`` parameter makes it easy to store NFVbench results. The --show-summary (or -ss) option can be used to display the results in a json results file in a text tabular format:

.. code-block:: bash

    nfvbench --show-summary results.json


This example shows how to specify a different packet path:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 1Mbps --inter-node --service-chain PVVP

Used parameters:

* ``-c nfvbench.cfg`` : path to the config file
* ``--rate 1Mbps`` : defines rate of packets sent by traffic generator
* ``--inter-node`` : VMs are created on different compute nodes, works only with PVVP flow
* ``--service-chain PVVP`` or ``-sc PVVP`` : specifies the type of service chain (or packet path) to use

.. note:: When parameter ``--inter-node`` is not used or there aren't enough compute nodes, VMs are on the same compute node.


Rate Units
^^^^^^^^^^

Parameter ``--rate`` accepts different types of values:

* packets per second (pps, kpps, mpps), e.g. ``1000pps`` or ``10kpps``
* load percentage (%), e.g. ``50%``
* bits per second (bps, kbps, Mbps, Gbps), e.g. ``1Gbps``, ``1000bps``
* NDR/PDR (ndr, pdr, ndr_pdr), e.g. ``ndr_pdr``

NDR/PDR is the default rate when not specified.

NDR and PDR
-----------

The NDR and PDR test is used to determine the maximum throughput performance of the system under test
following guidelines defined in RFC-2544:

* NDR (No Drop Rate): maximum packet rate sent without dropping any packet
* PDR (Partial Drop Rate): maximum packet rate sent while allowing a given maximum drop rate

The NDR search can also be relaxed to allow some very small amount of drop rate (lower than the PDR maximum drop rate).
NFVbench will measure the NDR and PDR values by driving the traffic generator through multiple iterations
at different transmission rates using a binary search algorithm.

The configuration file contains section where settings for NDR/PDR can be set.

.. code-block:: bash

    # NDR/PDR configuration
    measurement:
        # Drop rates represent the ratio of dropped packet to the total number of packets sent.
        # Values provided here are percentages. A value of 0.01 means that at most 0.01% of all
        # packets sent are dropped (or 1 packet every 10,000 packets sent)

        # No Drop Rate; Default to 0.001%
        NDR: 0.001
        # Partial Drop Rate; NDR should always be less than PDR
        PDR: 0.1
        # The accuracy of NDR and PDR load percentiles; The actual load percentile that match NDR
        # or PDR should be within `load_epsilon` difference than the one calculated.
        load_epsilon: 0.1

Because NDR/PDR is the default ``--rate`` value, it is possible to run NFVbench simply like this:

.. code-block:: bash

    nfvbench -c nfvbench.cfg

Other possible run options:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --duration 120 --json results.json

Used parameters:

* ``-c nfvbench.cfg`` : path to the config file
* ``--duration 120`` : specifies how long should be traffic running in each iteration
* ``--json results.json`` : collected data are stored in this file after run is finished


Multichain
----------

NFVbench allows to run multiple chains at the same time. For example it is possible to stage the PVP service chain N-times,
where N can be as much as your compute power can scale. With N = 10, NFVbench will spawn 10 VMs as a part of 10 simultaneous PVP chains.

The number of chains is specified by ``--service-chain-count`` or ``-scc`` flag with a default value of 1.
For example to run NFVbench with 3 PVP chains:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3

It is not necessary to specify the service chain type (-sc) because PVP is set as default. The PVP service chains will have 3 VMs in 3 chains with this configuration.
If ``-sc PVVP`` is specified instead, there would be 6 VMs in 3 chains as this service chain has 2 VMs per chain.
Both **single run** or **NDR/PDR** can be run as multichain. Running multichain is a scenario closer to a real life situation than runs with a single chain.


External Chain
--------------

NFVbench can measure the performance of 1 or more L3 service chains that are setup externally. Instead of being setup by NFVbench,
the complete environment (VMs and networks) has to be setup prior to running NFVbench.

Each external chain is made of 1 or more VNFs and has exactly 2 end network interfaces (left and right network interfaces) that are connected to 2 neutron networks (left and right networks).
The internal composition of a multi-VNF service chain can be arbitrary (usually linear) as far as NFVbench is concerned,
the only requirement is that the service chain can route L3 packets properly between the left and right networks.

To run NFVbench on such external service chains:

- explicitly tell NFVbench to use external service chain by adding ``-sc EXT`` or ``--service-chain EXT`` to NFVbench CLI options
- specify the number of external chains using the ``-scc`` option (defaults to 1 chain)
- specify the 2 end point networks of your environment in ``external_networks`` inside the config file.
    - The two networks specified there have to exist in Neutron and will be used as the end point networks by NFVbench ('napa' and 'marin' in the diagram below)
- specify the router gateway IPs for the external service chains (1.1.0.2 and 2.2.0.2)
- specify the traffic generator gateway IPs for the external service chains (1.1.0.102 and 2.2.0.102 in diagram below)
- specify the packet source and destination IPs for the virtual devices that are simulated (10.0.0.0/8 and 20.0.0.0/8)


.. image:: images/extchain-config.png

L3 routing must be enabled in the VNF and configured to:

- reply to ARP requests to its public IP addresses on both left and right networks
- route packets from each set of remote devices toward the appropriate dest gateway IP in the traffic generator using 2 static routes (as illustrated in the diagram)

Upon start, NFVbench will:
- first retrieve the properties of the left and right networks using Neutron APIs,
- extract the underlying network ID (typically VLAN segmentation ID),
- generate packets with the proper VLAN ID and measure traffic.

Note that in the case of multiple chains, all chains end interfaces must be connected to the same two left and right networks.
The traffic will be load balanced across the corresponding gateway IP of these external service chains.


Multiflow
---------

NFVbench always generates L3 packets from the traffic generator but allows the user to specify how many flows to generate.
A flow is identified by a unique src/dest MAC IP and port tuple that is sent by the traffic generator. Flows are
generated by ranging the IP adresses but using a small fixed number of MAC addresses.

The number of flows will be spread roughly even between chains when more than 1 chain is being tested.
For example, for 11 flows and 3 chains, number of flows that will run for each chain will be 3, 4, and 4 flows respectively.

The number of flows is specified by ``--flow-count`` or ``-fc`` flag, the default value is 2 (1 flow in each direction).
To run NFVbench with 3 chains and 100 flows, use the following command:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3 -fc 100

Note that from a vswitch point of view, the
number of flows seen will be higher as it will be at least 4 times the number of flows sent by the traffic generator
(add flow to VM and flow from VM).

IP addresses generated can be controlled with the following NFVbench configuration options:

.. code-block:: bash

    ip_addrs: ['10.0.0.0/8', '20.0.0.0/8']
    ip_addrs_step: 0.0.0.1
    tg_gateway_ip_addrs: ['1.1.0.100', '2.2.0.100']
    tg_gateway_ip_addrs_step: 0.0.0.1
    gateway_ip_addrs: ['1.1.0.2', '2.2.0.2']
    gateway_ip_addrs_step: 0.0.0.1

``ip_addrs`` are the start of the 2 ip address ranges used by the traffic generators as the packets source and destination packets
where each range is associated to virtual devices simulated behind 1 physical interface of the traffic generator.
These can also be written in CIDR notation to represent the subnet.

``tg_gateway_ip_addrs`` are the traffic generator gateway (virtual) ip addresses, all traffic to/from the virtual devices go through them.

``gateway_ip_addrs`` are the 2 gateway ip address ranges of the VMs used in the external chains. They are only used with external chains and must correspond to their public IP address.

The corresponding ``step`` is used for ranging the IP addresses from the `ip_addrs``, ``tg_gateway_ip_addrs`` and ``gateway_ip_addrs`` base addresses.
0.0.0.1 is the default step for all IP ranges. In ``ip_addrs``, 'random' can be configured which tells NFVBench to generate random src/dst IP pairs in the traffic stream.


Traffic Configuration via CLI
-----------------------------

While traffic configuration can be modified using the configuration file, it can be inconvenient to have to change the configuration file everytime
you need to change a traffic configuration option. Traffic configuration options can be overridden with a few CLI options.

Here is an example of configuring traffic via CLI:

.. code-block:: bash

    nfvbench --rate 10kpps --service-chain-count 2 -fs 64 -fs IMIX -fs 1518 --unidir

This command will run NFVbench with a unidirectional flow for three packet sizes 64B, IMIX, and 1518B.

Used parameters:

* ``--rate 10kpps`` : defines rate of packets sent by traffic generator (total TX rate)
* ``-scc 2`` or ``--service-chain-count 2`` : specifies number of parallel chains of given flow to run (default to 1)
* ``-fs 64`` or ``--frame-size 64``: add the specified frame size to the list of frame sizes to run
* ``--unidir`` : run traffic with unidirectional flow (default to bidirectional flow)


MAC Addresses
-------------

NFVbench will dicover the MAC addresses to use for generated frames using:
- either OpenStack discovery (find the MAC of an existing VM) in the case of PVP and PVVP service chains
- or using dynamic ARP discovery (find MAC from IP) in the case of external chains.

Cleanup Script
--------------

The nfvbench_cleanup script will cleanup resources created by NFVbench. You need to pass the OpenStack RC file in order to connect to
OpenStack.
Example of run:

.. code-block:: none

    # nfvbench_cleanup -r /tmp/nfvbench/openrc
    Discovering Storage resources...
    Discovering Compute resources...
    Discovering Network resources...
    Discovering Keystone resources...

    SELECTED RESOURCES:
    +-----------+-------------------+--------------------------------------+
    | Type      | Name              | UUID                                 |
    |-----------+-------------------+--------------------------------------|
    | flavors   | nfvbench.medium   | 362b2215-89d1-4f46-8b89-8e58165ff5bc |
    | instances | nfvbench-loop-vm0 | f78dfb74-1b8e-4c5c-8d83-652a7571da95 |
    | networks  | nfvbench-net0     | 57d7e6c9-325f-4c13-9b1b-929344cc9c39 |
    | networks  | nfvbench-net1     | 2d429bcd-33fa-4aa4-9f2e-299a735177c9 |
    +-----------+-------------------+--------------------------------------+

    Warning: You didn't specify a resource list file as the input. The script will delete all resources shown above.
    Are you sure? (y/n) y
    *** STORAGE cleanup
    *** COMPUTE cleanup
        . Waiting for 1 instances to be fully deleted...
        . INSTANCE 1 left to be deleted, retries left=5...
        . INSTANCE 1 left to be deleted, retries left=4...
        + INSTANCE nfvbench-loop-vm0 is successfully deleted
        + FLAVOR nfvbench.medium is successfully deleted
    *** NETWORK cleanup
        + Network port 075d91f3-fa6a-428c-bd3f-ebd40cd935e1 is successfully deleted
        + Network port 3a7ccd8c-53a6-43d0-a823-4b5ca762d06e is successfully deleted
        + NETWORK nfvbench-net0 is successfully deleted
        + Network port 5b5a75bd-e0b5-4f81-91b9-9e216d194f48 is successfully deleted
        + Network port cc2d8f1b-49fe-491e-9e44-6990fc57e891 is successfully deleted
        + NETWORK nfvbench-net1 is successfully deleted
    *** KEYSTONE cleanup
    #
