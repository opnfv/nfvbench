.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Features
********

Data Plane Performance Measurement Features
-------------------------------------------

NFVbench supports the following main measurement capabilities:

- supports 2 measurement modes:
    - *fixed rate* mode to generate traffic at a fixed rate for a fixed duration
    - NDR (No Drop Rate) and PDR (Partial Drop Rate) measurement mode
- configurable frame sizes (any list of fixed sizes or 'IMIX')
- built-in packet paths (PVP, PVVP)
- built-in loopback VNFs based on fast L2 or L3 forwarders running in VMs
- configurable number of flows and service chains
- configurable traffic direction (single or bi-directional)


NDR is the highest throughput achieved without dropping packets.
PDR is the highest throughput achieved without dropping more than a pre-set limit (called PDR threshold or allowance, expressed in %).

Results of each run include the following data:

- Aggregated achieved throughput in bps
- Aggregated achieved packet rate in pps (or fps)
- Actual drop rate in %
- Latency in usec (min, max, average in the current version)

Built-in OpenStack support
--------------------------
NFVbench can stage OpenStack resources to build 1 or more service chains using direct OpenStack APIs. Each service chain is composed of:

- 1 or 2 loopback VM instances per service chain
- 2 Neutron networks per loopback VM

OpenStack resources are staged before traffic is measured using OpenStack APIs (Nova and Neutron) then disposed after completion of measurements.

The loopback VM flavor to use can be configured in the NFVbench configuration file.

Note that NFVbench does not use OpenStack Heat nor any higher level service (VNFM or NFVO) to create the service chains because its
main purpose is to measure the performance of the NFVi infrastructure which is mainly focused on L2 forwarding performance.

External Chains
---------------
NFVbench also supports settings that involve externally staged packet paths with or without OpenStack:

- run benchmarks on existing service chains at the L3 level that are staged externally by any other tool (e.g. any VNF capable of L3 routing)
- run benchmarks on existing L2 chains that are configured externally (e.g. pure L2 forwarder such as DPDK testpmd)


Traffic Generation
------------------

NFVbench currently integrates with the open source TRex traffic generator:

- `TRex <https://trex-tgn.cisco.com>`_ (pre-built into the NFVbench container)


Supported Packet Paths
----------------------
Packet paths describe where packets are flowing in the NFVi platform. The most commonly used paths are identified by 3 or 4 letter abbreviations.
A packet path can generally describe the flow of packets associated to one or more service chains, with each service chain composed of 1 or more VNFs.

The following packet paths are currently supported by NFVbench:

- PVP (Physical interface to VM to Physical interface)
- PVVP (Physical interface to VM to VM to Physical interface)
- N*PVP (N concurrent PVP packet paths)
- N*PVVP (N concurrent PVVP packet paths)

The traffic is made of 1 or more flows of L3 frames (UDP packets) with different payload sizes. Each flow is identified by a unique source and destination MAC/IP tuple.


Loopback VM
^^^^^^^^^^^

NFVbench provides a loopback VM image that runs CentOS with 2 pre-installed forwarders:

- DPDK testpmd configured to do L2 cross connect between 2 virtual interfaces
- FD.io VPP configured to perform L3 routing between 2 virtual interfaces

Frames are just forwarded from one interface to the other.
In the case of testpmd, the source and destination MAC are rewritten, which corresponds to the mac forwarding mode (--forward-mode=mac).
In the case of VPP, VPP will act as a real L3 router, and the packets are routed from one port to the other using static routes.

Which forwarder and what Nova flavor to use can be selected in the NFVbench configuration. Be default the DPDK testpmd forwarder is used with 2 vCPU per VM.
The configuration of these forwarders (such as MAC rewrite configuration or static route configuration) is managed by NFVbench.


PVP Packet Path
^^^^^^^^^^^^^^^

This packet path represents a single service chain with 1 loopback VNF and 2 Neutron networks:

.. image:: images/nfvbench-pvp.png


PVVP Packet Path
^^^^^^^^^^^^^^^^

This packet path represents a single service chain with 2 loopback VNFs in sequence and 3 Neutron networks.
The 2 VNFs can run on the same compute node (PVVP intra-node):

.. image:: images/nfvbench-pvvp.png

or on different compute nodes (PVVP inter-node) based on a configuration option:

.. image:: images/nfvbench-pvvp2.png


Multi-Chaining (N*PVP or N*PVVP)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Multiple service chains can be setup by NFVbench without any limit on the concurrency (other than limits imposed by available resources on compute nodes).
In the case of multiple service chains, NFVbench will instruct the traffic generator to use multiple L3 packet streams (frames directed to each path will have a unique destination MAC address).

Example of multi-chaining with 2 concurrent PVP service chains:

.. image:: images/nfvbench-npvp.png

This innovative feature will allow to measure easily the performance of a fully loaded compute node running multiple service chains.

Multi-chaining is currently limited to 1 compute node (PVP or PVVP intra-node) or 2 compute nodes (for PVVP inter-node).
The 2 edge interfaces for all service chains will share the same 2 networks.

SR-IOV
^^^^^^

By default, service chains will be based on virtual switch interfaces.

NFVbench provides an option to select SR-IOV based virtual interfaces instead (thus bypassing any virtual switch) for those OpenStack system that include and support SR-IOV capable NICs on compute nodes.

The PVP packet path will bypass the virtual switch completely when the SR-IOV option is selected:

.. image:: images/nfvbench-sriov-pvp.png

The PVVP packet path will use SR-IOV for the left and right networks and the virtual switch for the middle network by default:

.. image:: images/nfvbench-sriov-pvvp.png

Or in the case of inter-node:

.. image:: images/nfvbench-sriov-pvvp2.png

This packet path is a good way to approximate VM to VM (V2V) performance (middle network) given the high efficiency of the left and right networks. The V2V throughput will likely be very close to the PVVP throughput while its latency will be very close to the difference between the SR-IOV PVVP latency and the SR-IOV PVP latency.

It is possible to also force the middle network to use SR-IOV (in this version, the middle network is limited to use the same SR-IOV phys net):

.. image:: images/nfvbench-all-sriov-pvvp.png


Other Misc Packet Paths
^^^^^^^^^^^^^^^^^^^^^^^

P2P (Physical interface to Physical interface - no VM) can be supported using the external chain/L2 forwarding mode.

V2V (VM to VM) is not supported but PVVP provides a more complete (and more realistic) alternative.


Supported Neutron Network Plugins and vswitches
-----------------------------------------------

Any Virtual Switch, Any Encapsulation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

NFVbench is agnostic of the virtual switch implementation and has been tested with the following virtual switches:

- ML2/VPP/VLAN (networking-vpp)
- OVS/VLAN and OVS-DPDK/VLAN
- ML2/ODL/VPP (OPNFV Fast Data Stack)







