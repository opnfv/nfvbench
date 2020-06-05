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


TRex force restart
------------------

NFVbench allows to restart TRex traffic generator between runs.
It runs the whole test, but restart TRex instance before generating new traffic.

To force restart, use the --restart option:

.. code-block:: bash

    nfvbench --restart

Used parameters:

* ``--restart`` : restart traffic generator (TRex)

Rate Units
^^^^^^^^^^

Parameter ``--rate`` accepts different types of values:

* packets per second (pps, kpps, mpps), e.g. ``1000pps`` or ``10kpps``
* load percentage (%), e.g. ``50%``
* bits per second (bps, kbps, Mbps, Gbps), e.g. ``1Gbps``, ``1000bps``
* NDR/PDR (ndr, pdr, ndr_pdr), e.g. ``ndr_pdr``

NDR/PDR is the default rate when not specified.

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

A fixed rate run can also be used to check the running drop rate while traffic is being generated. In that case the --interval option can be used
to specify the reporting interval in seconds (minimum is 1 second). This can be useful for example to see how packet drop rate
evolves over time. One common use case is to see the drop rate when there is a network degradation (e.g. one of the 2 links in a bond
goes down).
The console output will show at every reporting interval the number of packets transmitted, received and estimated drop rate for the last reporting interval.
The smaller is the interval the more precise is the drop rate.

Example of output where the reporting interval is set to 1 (second):

.. code-block:: bash

    2020-04-25 12:59:16,618 INFO TX:   1,878,719,266; RX:   1,666,641,890; (Est.) Dropped:            2; Drop rate:   0.0000%
    2020-04-25 12:59:17,625 INFO TX:   1,883,740,078; RX:   1,671,662,706; (Est.) Dropped:           -4; Drop rate:  -0.0001%
    2020-04-25 12:59:18,632 INFO TX:   1,888,764,404; RX:   1,676,686,993; (Est.) Dropped:           39; Drop rate:   0.0008%
    2020-04-25 12:59:19,639 INFO TX:   1,893,785,063; RX:   1,681,276,714; (Est.) Dropped:      430,938; Drop rate:   8.5833%
    2020-04-25 12:59:20,645 INFO TX:   1,898,805,769; RX:   1,683,782,636; (Est.) Dropped:    2,514,784; Drop rate:  50.0883%
    2020-04-25 12:59:21,652 INFO TX:   1,903,829,191; RX:   1,686,289,860; (Est.) Dropped:    2,516,198; Drop rate:  50.0893%
    2020-04-25 12:59:22,658 INFO TX:   1,908,850,478; RX:   1,691,283,008; (Est.) Dropped:       28,139; Drop rate:   0.5604%
    2020-04-25 12:59:23,665 INFO TX:   1,913,870,692; RX:   1,696,301,242; (Est.) Dropped:        1,980; Drop rate:   0.0394%
    2020-04-25 12:59:24,672 INFO TX:   1,918,889,696; RX:   1,698,806,224; (Est.) Dropped:    2,514,022; Drop rate:  50.0901%
    2020-04-25 12:59:25,680 INFO TX:   1,923,915,470; RX:   1,701,314,663; (Est.) Dropped:    2,517,335; Drop rate:  50.0885%
    2020-04-25 12:59:26,687 INFO TX:   1,928,944,879; RX:   1,705,886,869; (Est.) Dropped:      457,203; Drop rate:   9.0906%
    2020-04-25 12:59:27,696 INFO TX:   1,933,969,377; RX:   1,710,911,346; (Est.) Dropped:           21; Drop rate:   0.0004%
    2020-04-25 12:59:28,702 INFO TX:   1,938,998,536; RX:   1,713,843,740; (Est.) Dropped:    2,096,765; Drop rate:  41.6922%
    2020-04-25 12:59:29,710 INFO TX:   1,944,019,920; RX:   1,718,226,356; (Est.) Dropped:      638,768; Drop rate:  12.7210%
    2020-04-25 12:59:30,718 INFO TX:   1,949,050,206; RX:   1,723,256,639; (Est.) Dropped:            3; Drop rate:   0.0001%
    2020-04-25 12:59:31,725 INFO TX:   1,954,075,270; RX:   1,728,281,726; (Est.) Dropped:          -23; Drop rate:  -0.0005%
    2020-04-25 12:59:32,732 INFO TX:   1,959,094,908; RX:   1,733,301,290; (Est.) Dropped:           74; Drop rate:   0.0015%
    2020-04-25 12:59:33,739 INFO TX:   1,964,118,902; RX:   1,738,325,357; (Est.) Dropped:          -73; Drop rate:  -0.0015%
    2020-04-25 12:59:34,746 INFO TX:   1,969,143,790; RX:   1,743,350,230; (Est.) Dropped:           15; Drop rate:   0.0003%
    2020-04-25 12:59:35,753 INFO TX:   1,974,165,773; RX:   1,748,372,291; (Est.) Dropped:          -78; Drop rate:  -0.0016%
    2020-04-25 12:59:36,759 INFO TX:   1,979,188,496; RX:   1,753,394,957; (Est.) Dropped:           57; Drop rate:   0.0011%
    2020-04-25 12:59:37,767 INFO TX:   1,984,208,956; RX:   1,757,183,844; (Est.) Dropped:    1,231,573; Drop rate:  24.5311%
    2020-04-25 12:59:38,773 INFO TX:   1,989,233,595; RX:   1,761,729,705; (Est.) Dropped:      478,778; Drop rate:   9.5286%
    2020-04-25 12:59:39,780 INFO TX:   1,994,253,350; RX:   1,766,749,467; (Est.) Dropped:           -7; Drop rate:  -0.0001%
    2020-04-25 12:59:40,787 INFO TX:   1,999,276,622; RX:   1,771,772,738; (Est.) Dropped:            1; Drop rate:   0.0000%
    2020-04-25 12:59:41,794 INFO TX:   2,004,299,940; RX:   1,776,796,065; (Est.) Dropped:           -9; Drop rate:  -0.0002%
    2020-04-25 12:59:42,800 INFO TX:   2,009,320,453; RX:   1,781,816,583; (Est.) Dropped:           -5; Drop rate:  -0.0001%
    2020-04-25 12:59:43,807 INFO TX:   2,014,340,581; RX:   1,786,503,172; (Est.) Dropped:      333,539; Drop rate:   6.6440%
    2020-04-25 12:59:44,814 INFO TX:   2,019,362,996; RX:   1,789,009,857; (Est.) Dropped:    2,515,730; Drop rate:  50.0900%
    2020-04-25 12:59:45,821 INFO TX:   2,024,386,346; RX:   1,791,517,070; (Est.) Dropped:    2,516,137; Drop rate:  50.0888%


How to read each line:

.. code-block:: bash

    2020-04-25 10:46:41,276 INFO TX:       4,004,436; RX:       4,004,381; (Est.) Dropped:           55; Drop rate:   0.0014%

At this poing in time, NFvbench has sent 4,004,436 and received 4,004,381 since the start of the run.
There is deficit of 55 packets on reception which corresponds to 0.0014% of all packets sent during that reporting window interval (last 1 second)
A negative value means that the RX count is higher than the tx count in that window – this is possible since the RX and TX reads are not atomic.


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

UDP ports can be controlled with the following NFVbench configuration options:

.. code-block:: bash

    udp_src_port: ['1024', '65000']
    udp_dst_port: 53
    udp_port_step: '1'

``udp_src_port`` and ``udp_dst_port`` are the UDP port value used by the traffic generators.
These can be written for unique port or range ports for all flow.

The corresponding ``udp_port_step`` is used for ranging the UDP port.
1 is the default step for all UDP ranges, 'random' can be configured which tells NFVBench to generate random src/dst UDP pairs in the traffic stream.

NB:
    Use of UDP range will increase possible values of flows (based on ip src/dst and port src/dst tuple).
    NFVBench will calculate the least common multiple for this tuple to adapt flows generation to ``flow_count`` parameter.

Examples of multiflow
^^^^^^^^^^^^^^^^^^^^^

1. Source IP is static and one UDP port used (default configuration)

NFVbench configuration options:

.. code-block:: bash

    ip_addrs: ['110.0.0.0/8', '120.0.0.0/8']
    ip_addrs_step: 0.0.0.1
    tg_gateway_ip_addrs: ['1.1.0.100', '2.2.0.100']
    tg_gateway_ip_addrs_step: 0.0.0.1
    gateway_ip_addrs: ['1.1.0.2', '2.2.0.2']
    gateway_ip_addrs_step: 0.0.0.1

To run NFVbench with 3 chains and 100 flows, use the following command:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3 -fc 100

The least common multiple for this configuration is lcm(16 777 216, 16 777 216, 1, 1) = 16 777 216.
.. note:: LCM method used IP pools sizes and UDP source and destination range sizes

Requested flow count is lower than configuration capacity. So, NFVbench will limit IP range to generate accurate flows:

.. code-block:: bash

    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP src range [110.0.0.0,110.0.0.0]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP dst range [120.0.0.0,120.0.0.15]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP dst range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP src range [120.0.0.0,120.0.0.0]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP dst range [110.0.0.0,110.0.0.15]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP dst range [53,53]

    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP src range [110.0.0.1,110.0.0.1]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.16,120.0.0.32]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP src range [120.0.0.1,120.0.0.1]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.16,110.0.0.32]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP dst range [53,53]

    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP src range [110.0.0.2,110.0.0.2]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.33,120.0.0.49]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP src range [120.0.0.2,120.0.0.2]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.33,110.0.0.49]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP dst range [53,53]


2. Source IP is static, IP step is random and one UDP port used

NFVbench configuration options:

.. code-block:: bash

    ip_addrs: ['110.0.0.0/8', '120.0.0.0/8']
    ip_addrs_step: 'random'
    tg_gateway_ip_addrs: ['1.1.0.100', '2.2.0.100']
    tg_gateway_ip_addrs_step: 0.0.0.1
    gateway_ip_addrs: ['1.1.0.2', '2.2.0.2']
    gateway_ip_addrs_step: 0.0.0.1

To run NFVbench with 3 chains and 100 flows, use the following command:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3 -fc 100

The least common multiple for this configuration is lcm(16 777 216, 16 777 216, 1, 1) = 16 777 216.
.. note:: LCM method used IP pools sizes and UDP source and destination range sizes

Requested flow count is lower than configuration capacity. So, NFVbench will limit IP range to generate accurate flows:

.. code-block:: bash

    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP src range [110.0.0.0,110.0.0.0]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP dst range [120.0.0.0,120.0.0.15]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP dst range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP src range [120.0.0.0,120.0.0.0]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP dst range [110.0.0.0,110.0.0.15]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP dst range [53,53]

    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP src range [110.0.0.1,110.0.0.1]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.16,120.0.0.32]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP src range [120.0.0.1,120.0.0.1]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.16,110.0.0.32]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP dst range [53,53]

    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP src range [110.0.0.2,110.0.0.2]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.33,120.0.0.49]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP src range [120.0.0.2,120.0.0.2]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.33,110.0.0.49]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP dst range [53,53]
    2020-06-17 07:39:47,015 WARNING Using random step, the number of flows can be less than the requested number of flows due to repeatable multivariate random generation which can reproduce the same pattern of values

By using a random step the number of generated flows may be less than the number of requested flows. This is due to the probability of drawing the same value several times (Bernouillian drawing) from the IP range used and thus generating the same flow sequence.
By using a high range of UDP ports couple with ``udp_port_step='random'`` the probability to reach the requested flow counts is greater.
As latency stream is a separate stream than data one and have his own random draw, NFVbench will use only one packet signature (same IP and ports used for all latency packets) to avoid flow count overflow.
So in some cases, generated flow count can be equal to the requested flow count + 1 (latency stream).

**For deterministic flow count we recommend to use a step different from random.**


3. Source IP is static, IP step is 5 and one UDP port used

NFVbench configuration options:

.. code-block:: bash

    ip_addrs: ['110.0.0.0/8', '120.0.0.0/8']
    ip_addrs_step: '0.0.0.5'
    tg_gateway_ip_addrs: ['1.1.0.100', '2.2.0.100']
    tg_gateway_ip_addrs_step: 0.0.0.1
    gateway_ip_addrs: ['1.1.0.2', '2.2.0.2']
    gateway_ip_addrs_step: 0.0.0.1

To run NFVbench with 3 chains and 100 flows, use the following command:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3 -fc 100

The least common multiple for this configuration is lcm(16 777 216, 16 777 216, 1, 1) = 16 777 216.
.. note:: LCM method used IP pools sizes and UDP source and destination range sizes

Requested flow count is lower than configuration capacity. So, NFVbench will limit IP range to generate accurate flows:

.. code-block:: bash

    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP src range [110.0.0.0,110.0.0.0]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP dst range [120.0.0.0,120.0.0.75]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP dst range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP src range [120.0.0.0,120.0.0.0]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP dst range [110.0.0.0,110.0.0.75]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP src range [53,53]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP dst range [53,53]

    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP src range [110.0.0.5,110.0.0.5]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.80,120.0.0.160]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP src range [120.0.0.5,120.0.0.5]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.80,110.0.0.160]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP dst range [53,53]

    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP src range [110.0.0.10,110.0.0.10]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.165,120.0.0.245]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP dst range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP src range [120.0.0.10,120.0.0.10]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.165,110.0.0.245]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP src range [53,53]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP dst range [53,53]

4. Source IP is static, IP and UDP ranges sizes lether than requested flow count, UDP step is random

NFVbench configuration options:

.. code-block:: bash

    ip_addrs: ['110.0.0.0/29', '120.0.0.0/30']
    tg_gateway_ip_addrs: ['1.1.0.100', '2.2.0.100']
    tg_gateway_ip_addrs_step: 0.0.0.1
    gateway_ip_addrs: ['1.1.0.2', '2.2.0.2']
    gateway_ip_addrs_step: 0.0.0.1
    udp_src_port: ['10', '14']
    udp_dst_port: ['20', '25']
    udp_port_step: 'random'

To run NFVbench with 3 chains and 100 flows, use the following command:

.. code-block:: bash

    nfvbench -c nfvbench.cfg --rate 10000pps -scc 3 -fc 100

The least common multiple for this configuration is lcm(8, 4, 5, 6) = 120.
.. note:: LCM method used IP pools sizes and UDP source and destination range sizes

Requested flow count is higher than IP range (8 and 4 IP addresses available) and UDP (5 and 6 ports available) configuration capacity.
As the combination of ranges does not permit to obtain an accurate flow count, NFVbench will override the `udp_port_step` property to '1' (was 'random') to allow flows creation.
A warning log will appear to inform NFVbench user that step properties will be overriden
So, NFVbench will determine each pool size to generate accurate flows:

.. code-block:: bash

    2020-06-17 07:37:47,010 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:37:47,011 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP src range [110.0.0.0,110.0.0.0]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: IP dst range [120.0.0.0,120.0.0.0]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP src range [10,14]
    2020-06-17 07:37:47,012 INFO Port 0, chain 0: UDP dst range [20,25]
    2020-06-17 07:37:47,013 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:37:47,013 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP src range [120.0.0.0,120.0.0.0]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: IP dst range [110.0.0.0,110.0.0.0]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP src range [10,14]
    2020-06-17 07:37:47,015 INFO Port 1, chain 0: UDP dst range [20,25]

    2020-06-17 07:38:47,010 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:38:47,011 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP src range [110.0.0.1,110.0.0.1]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.1,120.0.0.1]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP src range [10,14]
    2020-06-17 07:38:47,012 INFO Port 0, chain 1: UDP dst range [20,25]
    2020-06-17 07:38:47,013 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:38:47,013 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP src range [120.0.0.1,120.0.0.1]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.1,110.0.0.1]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP src range [10,14]
    2020-06-17 07:38:47,015 INFO Port 1, chain 1: UDP dst range [20,25]

    2020-06-17 07:39:47,010 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:39:47,011 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP src range [110.0.0.2,110.0.0.2]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: IP dst range [120.0.0.2,120.0.0.2]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP src range [10,14]
    2020-06-17 07:39:47,012 INFO Port 0, chain 1: UDP dst range [20,25]
    2020-06-17 07:39:47,013 WARNING Current values of ip_addrs_step and/or udp_port_step properties do not allow to control an accurate flow count. Values will be overridden as follows:
    2020-06-17 07:39:47,013 INFO udp_port_step='1' (previous value: udp_port_step='random'
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP src range [120.0.0.2,120.0.0.2]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: IP dst range [110.0.0.2,110.0.0.2]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP src range [10,14]
    2020-06-17 07:39:47,015 INFO Port 1, chain 1: UDP dst range [20,25]




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
- In case of L3 chain with SDN-GW or router between traffic generator and loop VM ARP is needed to discover SDN-GW mac addresses, use ``--loop-vm-arp`` flag or ``loop_vm_arp: true`` in config file.

Status and Cleanup of NFVbench Resources
----------------------------------------

The --status option will display the status of NFVbench and list any NFVbench resources. You need to pass the OpenStack RC
file in order to connect to OpenStack.

.. code-block:: none

    # nfvbench --status -r /tmp/nfvbench/openrc
    2018-04-09 17:05:48,682 INFO Version: 1.3.2.dev1
    2018-04-09 17:05:48,683 INFO Status: idle
    2018-04-09 17:05:48,757 INFO Discovering instances nfvbench-loop-vm...
    2018-04-09 17:05:49,252 INFO Discovering flavor nfvbench.medium...
    2018-04-09 17:05:49,281 INFO Discovering networks...
    2018-04-09 17:05:49,365 INFO No matching NFVbench resources found
    #

The Status can be either "idle" or "busy (run pending)".

The --cleanup option will first discover resources created by NFVbench and prompt if you want to proceed with cleaning them up.
Example of run:

.. code-block:: none

    # nfvbench --cleanup -r /tmp/nfvbench/openrc
    2018-04-09 16:58:00,204 INFO Version: 1.3.2.dev1
    2018-04-09 16:58:00,205 INFO Status: idle
    2018-04-09 16:58:00,279 INFO Discovering instances nfvbench-loop-vm...
    2018-04-09 16:58:00,829 INFO Discovering flavor nfvbench.medium...
    2018-04-09 16:58:00,876 INFO Discovering networks...
    2018-04-09 16:58:00,960 INFO Discovering ports...
    2018-04-09 16:58:01,012 INFO Discovered 6 NFVbench resources:
    +----------+-------------------+--------------------------------------+
    | Type     | Name              | UUID                                 |
    |----------+-------------------+--------------------------------------|
    | Instance | nfvbench-loop-vm0 | b039b858-777e-467e-99fb-362f856f4a94 |
    | Flavor   | nfvbench.medium   | a027003c-ad86-4f24-b676-2b05bb06adc0 |
    | Network  | nfvbench-net0     | bca8d183-538e-4965-880e-fd92d48bfe0d |
    | Network  | nfvbench-net1     | c582a201-8279-4309-8084-7edd6511092c |
    | Port     |                   | 67740862-80ac-4371-b04e-58a0b0f05085 |
    | Port     |                   | b5db95b9-e419-4725-951a-9a8f7841e66a |
    +----------+-------------------+--------------------------------------+
    2018-04-09 16:58:01,013 INFO NFVbench will delete all resources shown...
    Are you sure? (y/n) y
    2018-04-09 16:58:01,865 INFO Deleting instance nfvbench-loop-vm0...
    2018-04-09 16:58:02,058 INFO     Waiting for 1 instances to be fully deleted...
    2018-04-09 16:58:02,182 INFO     1 yet to be deleted by Nova, retries left=6...
    2018-04-09 16:58:04,506 INFO     1 yet to be deleted by Nova, retries left=5...
    2018-04-09 16:58:06,636 INFO     1 yet to be deleted by Nova, retries left=4...
    2018-04-09 16:58:08,701 INFO Deleting flavor nfvbench.medium...
    2018-04-09 16:58:08,729 INFO Deleting port 67740862-80ac-4371-b04e-58a0b0f05085...
    2018-04-09 16:58:09,102 INFO Deleting port b5db95b9-e419-4725-951a-9a8f7841e66a...
    2018-04-09 16:58:09,620 INFO Deleting network nfvbench-net0...
    2018-04-09 16:58:10,357 INFO Deleting network nfvbench-net1...
    #

The --force-cleanup option will do the same but without prompting for confirmation.

Service mode for TRex
---------------------

The ``--service-mode`` option allows you to capture traffic on a TRex window during the NFVBench test. Thus, you will be
able to capture packets generated by TRex to observe many information on it.

Example of use :

.. code-block:: bash

    nfvbench ``--service-mode``

.. note:: It is preferable to define the minimum rate (2002 pps) to have a better capture

In another bash window, you should connect to the TRex console doing:

.. code-block:: bash

    cd /opt/trex/vX.XX/ #use completion here to find your corresponding TRex version
    ./trex-console -r
    capture start monitor --rx [port number] -v

Start this capture once you have started the NFVBench test, and you will observe packets on the TRex console:

.. code-block:: bash

    #26342 Port: 0 ◀── RX

    trex(read-only)>

        Type: UDP, Size: 66 B, TS: 26.30 [sec]

    trex(read-only)>
        ###[ Ethernet ]###
            dst       = a0:36:9f:7a:58:8e
            src       = fa:16:3e:57:8f:df
            type      = 0x8100
        ###[ 802.1Q ]###
            prio      = 0
            id        = 0
            vlan      = 1093
            type      = 0x800
        ###[ IP ]###
            version   = 4
            ihl       = 5
            tos       = 0x1
            len       = 46
            id        = 65535
            flags     =
            frag      = 0
            ttl       = 63
            proto     = udp
            chksum    = 0x8425
            src       = 120.0.0.0
            dst       = 110.0.17.153
            \options   \
        ###[ UDP ]###
            sport     = 53
            dport     = 53
            len       = 26
            chksum    = 0xfd83
        ###[ Raw ]###
            load      = "xx\xab'\x01\x00?s\x00\x00\xbci\xf0_{U~\x00"
        ###[ Padding ]###
            load      = '6\x85'

Check on the NFVBench window that the following log appears just before the testing phase:

.. code-block:: bash

    2019-10-21 09:38:51,532 INFO Starting to generate traffic...
    2019-10-21 09:38:51,532 INFO Running traffic generator
    2019-10-21 09:38:51,541 INFO ``Service mode is enabled``
    2019-10-21 09:38:52,552 INFO TX: 2004; RX: 2003; Est. Dropped: 1; Est. Drop rate: 0.0499%
    2019-10-21 09:38:53,559 INFO TX: 4013; RX: 4011; Est. Dropped: 2; Est. Drop rate: 0.0498%

Recording packet using service mode for TRex
--------------------------------------------

Check on the NFVBench window that the following log appears just before the testing phase:

.. code-block:: bash

    2019-10-21 09:38:51,532 INFO Starting to generate traffic...
    2019-10-21 09:38:51,532 INFO Running traffic generator
    2019-10-21 09:38:51,541 INFO ``Service mode is enabled``
    2019-10-21 09:38:52,552 INFO TX: 2004; RX: 2003; Est. Dropped: 1; Est. Drop rate: 0.0499%

In another bash window, you should connect to the TRex console doing :

.. code-block:: bash

    cd /opt/trex/vX.XX/ #use completion here to find your corresponding TRex version
    ./trex-console -r
    capture start record --rx [port number] --limit 10000
.. note::Start this capture once traffic generation is started (after ``Service mode is enabled`` log)

Check on the TRex window that the following log appears just after capture is started:

.. code-block:: bash
    Starting packet capturing up to 10000 packets               [SUCCESS]
    *** Capturing ID is set to '8' ***
    *** Please call 'capture record stop --id 8 -o <out.pcap>' when done ***

Then **before end of traffic generation**, stop capture and save it as a PCAP file:

.. code-block:: bash

    capture record stop --id 8 -o /tmp/nfvb/record.pcap
.. note:: Provide a shared path with between NFVbench container and your host to retrieve pcap file

Check on the TRex window that the following log appears just after capture is started:

.. code-block:: bash

    Stopping packet capture 8                                    [SUCCESS]
    Writing up to 10000 packets to '/tmp/nfvb/record.pcap'       [SUCCESS]
    Removing PCAP capture 8 from server                          [SUCCESS]