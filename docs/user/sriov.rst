.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc


Testing SR-IOV
==============

NFVbench supports SR-IOV with the PVP and PVVP packet flow. Most use cases for SR-IOV only require single VNF chains (NxPVP).
Daisy chaining VNFs with SR-IOV (PVVP) requires selecting either SR-IOV for the middle network or a fast vswitch (using the
standard OVS for that purpose works but would be a serious bottleneck)

Instructions below refer to the PVP or PVVP use cases.
For external chains using SR-IOV, select the VLAN tagging option that corresponds to the external chains SR-IOV setting.

Pre-requisites
--------------
To test SR-IOV you need to have compute nodes configured to support one or more SR-IOV interfaces (also knows as PF or physical function)
and you need OpenStack to be configured to support SR-IOV.
You will also need to know:
- the name of the physical networks associated to the SR-IOV interfaces (this is a configuration in Nova compute)
- the VLAN range that can be used on the switch ports that are wired to the SR-IOV ports. Such switch ports are normally configured in trunk mode with a range of VLAN ids enabled on that port

For example, in the case of 2 SR-IOV ports per compute node, 2 physical networks are generally configured in OpenStack with a distinct name.
The VLAN range to use is is also allocated and reserved by the network administrator and in coordination with the corresponding top of rack switch port configuration.


Configuration
-------------
To enable SR-IOV test, you will need to provide the following configuration options to NFVbench (in the configuration file).
This example instructs NFVbench to create the left and right networks of a PVP packet flow to run on 2 SRIOV ports named "phys_sriov0" and "phys_sriov1" using resp. segmentation_id 2000 and 2001:

.. code-block:: bash

    sriov: true
    internal_networks:
       left:
           segmentation_id: 2000
           physical_network: phys_sriov0
       right:
           segmentation_id: 2001
           physical_network: phys_sriov1

The segmentation ID fields must be different.
In the case of PVVP, the middle network also needs to be provisioned properly.
The same physical network can also be shared by the virtual networks but with different segmentation IDs.

Multi-Chaining
--------------
The above configuration works for multi-chaining and shared network ("service_chain_shared_net" set to true).
In that case all VNFs will share the same left and right network/VLAN.

In the case of non shared network ("service_chain_shared_net" set to false), the segmentation_id fields must
contain a list of distinct VLANs to use for each chain. Example of configuration for 3 chains:

.. code-block:: bash

    sriov: true
    internal_networks:
       left:
           segmentation_id: [2000, 2001, 2002]
           physical_network: phys_sriov0
       right:
           segmentation_id: [2100, 2101, 2102]
           physical_network: phys_sriov1

Alternatively it is also possible to specify different physnets per chain:

.. code-block:: bash

    sriov: true
    internal_networks:
       left:
           segmentation_id: [2000, 2001, 2002]
           physical_network: [phys_sriov0, phys_sriov2, phys_sriov4]
       right:
           segmentation_id: [2100, 2101, 2102]
           physical_network: [phys_sriov1, phys_srviov3, phys_sriov5]


NFVbench cores with SR-IOV
--------------------------
The default core count for NFVbench/TRex may not be sufficient for higher throughput line cards (greater than 10Gbps).
This will result in warning messages such as:

.. code-block:: bash

    INFO WARNING: There is a significant difference between requested TX rate (119047618) and actual TX rate (38897379).
    The traffic generator may not have sufficient CPU to achieve the requested TX rate.

In that case it is recommended to try allocating more cores to TRex using the cores property in the configuration
file, for example to set to 8 cores:

.. code-block:: bash

    cores: 8

It is also advisable to increase the number of vcpus in the VMs:


VM Flavor for SR-IOV and NIC NUMA socket placement
--------------------------------------------------

Because SR-IOV throughput uses a lot of CPU in the VM, it is recommended to increase the
vcpu count, for example to 4 vcpus:

.. code-block:: bash

    flavor:
      # Number of vCPUs for the flavor
      vcpus: 4
      # Memory for the flavor in MB
      ram: 8192
      # Size of local disk in GB
      disk: 0
      extra_specs:
          "hw:cpu_policy": dedicated

If the 2 selected ports reside on NICs that are on different NUMA sockets, you will need to explicitly tell Nova to use 2 numa nodes in the flavor used for the VMs in order to satisfy the filters, for example:

.. code-block:: bash

    flavor:
      # Number of vCPUs for the flavor
      vcpus: 4
      # Memory for the flavor in MB
      ram: 8192
      # Size of local disk in GB
      disk: 0
      extra_specs:
          "hw:cpu_policy": dedicated
          "hw:numa_nodes": 2

Failure to do so might cause the VM creation to fail with the Nova error
"Instance creation error: Insufficient compute resources:
Requested instance NUMA topology together with requested PCI devices cannot fit the given host NUMA topology."

Example of configuration file (shared network)
----------------------------------------------

Single chain or multi-chain with shared network (only requires 2 segmentation ID for all chains):

.. code-block:: bash

    flavor:
       # Number of vCPUs for the flavor
       vcpus: 4
       # Memory for the flavor in MB
       ram: 8192
       # Size of local disk in GB
       disk: 0
       extra_specs:
          "hw:cpu_policy": dedicated
    cores: 8
    sriov: true
    internal_networks:
       left:
          segmentation_id: 3830
          physical_network: phys_sriov0
       right:
          segmentation_id: 3831
          physical_network: phys_sriov1

Example of full run 2xPVP shared network SR-IOV:

.. code-block:: bash

    2018-12-03 18:24:07,419 INFO Loading configuration file: /tmp/nfvbench/sriov.yaml
    2018-12-03 18:24:07,423 INFO -c /tmp/nfvbench/sriov.yaml --rate 10Mpps --duration 1 -scc 2 --no-cleanup
    2018-12-03 18:24:07,426 INFO Connecting to TRex (127.0.0.1)...
    2018-12-03 18:24:07,575 INFO Connected to TRex
    2018-12-03 18:24:07,575 INFO    Port 0: Ethernet Controller XL710 for 40GbE QSFP+ speed=40Gbps mac=3c:fd:fe:b5:3d:70 pci=0000:5e:00.0 driver=net_i40e
    2018-12-03 18:24:07,575 INFO    Port 1: Ethernet Controller XL710 for 40GbE QSFP+ speed=40Gbps mac=3c:fd:fe:b5:3d:71 pci=0000:5e:00.1 driver=net_i40e
    2018-12-03 18:24:07,626 INFO Found built-in VM image file nfvbenchvm-0.6.qcow2
    2018-12-03 18:24:09,072 INFO Created flavor 'nfvbench.medium'
    2018-12-03 18:24:10,004 INFO Created network: nfvbench-lnet.
    2018-12-03 18:24:10,837 INFO Created network: nfvbench-rnet.
    2018-12-03 18:24:12,065 INFO Security disabled on port nfvbench-loop-vm0-0
    2018-12-03 18:24:13,425 INFO Security disabled on port nfvbench-loop-vm0-1
    2018-12-03 18:24:13,425 INFO Creating instance nfvbench-loop-vm0 with AZ
    2018-12-03 18:24:16,052 INFO Created instance nfvbench-loop-vm0 - waiting for placement resolution...
    2018-12-03 18:24:16,240 INFO Waiting for instance nfvbench-loop-vm0 to become active (retry 1/101)...
    <snip>
    2018-12-03 18:24:59,266 INFO Waiting for instance nfvbench-loop-vm0 to become active (retry 21/101)...
    2018-12-03 18:25:01,427 INFO Instance nfvbench-loop-vm0 is active and has been placed on nova:charter-compute-5
    2018-12-03 18:25:02,819 INFO Security disabled on port nfvbench-loop-vm1-0
    2018-12-03 18:25:04,198 INFO Security disabled on port nfvbench-loop-vm1-1
    2018-12-03 18:25:04,199 INFO Creating instance nfvbench-loop-vm1 with AZ nova:charter-compute-5
    2018-12-03 18:25:05,032 INFO Created instance nfvbench-loop-vm1 on nova:charter-compute-5
    2018-12-03 18:25:05,033 INFO Instance nfvbench-loop-vm0 is ACTIVE on nova:charter-compute-5
    2018-12-03 18:25:05,212 INFO Waiting for 1/2 instance to become active (retry 1/100)...
    <snip>
    2018-12-03 18:25:48,531 INFO Waiting for 1/2 instance to become active (retry 21/100)...
    2018-12-03 18:25:50,677 INFO Instance nfvbench-loop-vm1 is ACTIVE on nova:charter-compute-5
    2018-12-03 18:25:50,677 INFO All instances are active
    2018-12-03 18:25:50,677 INFO Port 0: VLANs [3830, 3830]
    2018-12-03 18:25:50,677 INFO Port 1: VLANs [3831, 3831]
    2018-12-03 18:25:50,677 INFO Port 0: dst MAC ['fa:16:3e:de:4e:54', 'fa:16:3e:7a:26:2b']
    2018-12-03 18:25:50,677 INFO Port 1: dst MAC ['fa:16:3e:6c:bb:cd', 'fa:16:3e:e0:48:45']
    2018-12-03 18:25:50,678 INFO ChainRunner initialized
    2018-12-03 18:25:50,678 INFO Starting 2xPVP benchmark...
    2018-12-03 18:25:50,683 INFO Starting traffic generator to ensure end-to-end connectivity
    2018-12-03 18:25:50,698 INFO Created 2 traffic streams for port 0.
    2018-12-03 18:25:50,700 INFO Created 2 traffic streams for port 1.
    2018-12-03 18:25:50,821 INFO Captured unique src mac 0/4, capturing return packets (retry 1/100)...
    2018-12-03 18:25:52,944 INFO Received packet from mac: fa:16:3e:de:4e:54 (chain=0, port=0)
    2018-12-03 18:25:52,945 INFO Received packet from mac: fa:16:3e:6c:bb:cd (chain=0, port=1)
    2018-12-03 18:25:53,077 INFO Captured unique src mac 2/4, capturing return packets (retry 2/100)...
    <snip>
    2018-12-03 18:26:10,798 INFO End-to-end connectivity established
    2018-12-03 18:26:10,816 INFO Cleared all existing streams
    2018-12-03 18:26:10,846 INFO Created 4 traffic streams for port 0.
    2018-12-03 18:26:10,849 INFO Created 4 traffic streams for port 1.
    2018-12-03 18:26:10,849 INFO Starting to generate traffic...
    2018-12-03 18:26:10,850 INFO Running traffic generator
    2018-12-03 18:26:11,877 INFO TX: 10000004; RX: 9999999; Est. Dropped: 5; Est. Drop rate: 0.0000%
    2018-12-03 18:26:11,877 INFO ...traffic generating ended.
    2018-12-03 18:26:11,882 INFO Service chain 'PVP' run completed.
    2018-12-03 18:26:11,936 INFO Clean up skipped.
    2018-12-03 18:26:11,969 INFO
    ========== NFVBench Summary ==========
    Date: 2018-12-03 18:25:50
    NFVBench version 3.0.3.dev1
    Openstack Neutron:
      vSwitch: OPENVSWITCH
      Encapsulation: VLAN
    Benchmarks:
    > Networks:
      > Components:
        > Traffic Generator:
            Profile: trex-local
            Tool: TRex
        > Versions:
          > Traffic_Generator:
              build_date: Nov 13 2017
              version: v2.32
              built_by: hhaim
              mode: STL
              build_time: 10:58:17
          > CiscoVIM: 2.9.7-17036
      > Service chain:
        > PVP:
          > Traffic:
              Profile: traffic_profile_64B
              Bidirectional: True
              Flow count: 10000
              Service chains count: 2
              Compute nodes: [u'nova:charter-compute-5']

              Run Summary:

                +-----------------+-------------+----------------------+----------------------+----------------------+
                |   L2 Frame Size |  Drop Rate  |   Avg Latency (usec) |   Min Latency (usec) |   Max Latency (usec) |
                +=================+=============+======================+======================+======================+
                |              64 |   0.0000%   |                   13 |                   10 |                  141 |
                +-----------------+-------------+----------------------+----------------------+----------------------+


              L2 frame size: 64

              Run Config:

                +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                |  Direction  |  Requested TX Rate (bps)  |  Actual TX Rate (bps)  |  RX Rate (bps)  |  Requested TX Rate (pps)  |  Actual TX Rate (pps)  |  RX Rate (pps)  |
                +=============+===========================+========================+=================+===========================+========================+=================+
                |   Forward   |       336.0000 Mbps       |     336.0000 Mbps      |  336.0000 Mbps  |        500,000 pps        |      500,000 pps       |   500,000 pps   |
                +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                |   Reverse   |       336.0000 Mbps       |     336.0000 Mbps      |  336.0000 Mbps  |        500,000 pps        |      500,000 pps       |   500,000 pps   |
                +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                |    Total    |       672.0000 Mbps       |     672.0000 Mbps      |  672.0000 Mbps  |       1,000,000 pps       |     1,000,000 pps      |  1,000,000 pps  |
                +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+

              Forward Chain Packet Counters and Latency:

                +---------+--------------+--------------+------------+------------+------------+
                |  Chain  |  TRex.TX.p0  |  TRex.RX.p1  |  Avg lat.  |  Min lat.  |  Max lat.  |
                +=========+==============+==============+============+============+============+
                |    0    |   250,000    |   250,000    |  17 usec   |  10 usec   |  138 usec  |
                +---------+--------------+--------------+------------+------------+------------+
                |    1    |   250,000    |   250,000    |  17 usec   |  10 usec   |  139 usec  |
                +---------+--------------+--------------+------------+------------+------------+
                |  total  |   500,000    |   500,000    |  17 usec   |  10 usec   |  139 usec  |
                +---------+--------------+--------------+------------+------------+------------+

              Reverse Chain Packet Counters and Latency:

                +---------+--------------+--------------+------------+------------+------------+
                |  Chain  |  TRex.TX.p1  |  TRex.RX.p0  |  Avg lat.  |  Min lat.  |  Max lat.  |
                +=========+==============+==============+============+============+============+
                |    0    |   250,000    |   250,000    |  12 usec   |  10 usec   |  141 usec  |
                +---------+--------------+--------------+------------+------------+------------+
                |    1    |   250,000    |   250,000    |  11 usec   |  10 usec   |  132 usec  |
                +---------+--------------+--------------+------------+------------+------------+
                |  total  |   500,000    |   500,000    |  12 usec   |  10 usec   |  141 usec  |
                +---------+--------------+--------------+------------+------------+------------+

Example of configuration file (non shared network)
--------------------------------------------------

Multi-chain with non shared network (requires 2 segmentation ID per chain), example with 2 chains
sharing the same 2 SRIOV ports (or PF):

.. code-block:: bash

    flavor:
       # Number of vCPUs for the flavor
       vcpus: 4
       # Memory for the flavor in MB
       ram: 8192
       # Size of local disk in GB
       disk: 0
       extra_specs:
          "hw:cpu_policy": dedicated
    cores: 8
    sriov: true
    internal_networks:
       left:
            segmentation_id: [3830, 3831]
            physical_network: phys_sriov0
       right:
            segmentation_id: [3832, 3833]
            physical_network: phys_sriov1

Example of full run 2xPVP non-shared network SR-IOV:

.. code-block:: bash

    2018-12-04 17:15:25,284 INFO -c /tmp/nfvbench/sriov.yaml --rate 1Mpps --duration 1 -scc 2 --no-cleanup
    2018-12-04 17:15:25,287 INFO Connecting to TRex (127.0.0.1)...
    2018-12-04 17:15:25,463 INFO Connected to TRex
    2018-12-04 17:15:25,464 INFO    Port 0: Ethernet Controller XL710 for 40GbE QSFP+ speed=40Gbps mac=3c:fd:fe:b5:3d:70 pci=0000:5e:00.0 driver=net_i40e
    2018-12-04 17:15:25,464 INFO    Port 1: Ethernet Controller XL710 for 40GbE QSFP+ speed=40Gbps mac=3c:fd:fe:b5:3d:71 pci=0000:5e:00.1 driver=net_i40e
    2018-12-04 17:15:25,515 INFO Found built-in VM image file nfvbenchvm-0.6.qcow2
    2018-12-04 17:15:26,457 INFO Created flavor 'nfvbench.medium'
    2018-12-04 17:15:27,449 INFO Created network: nfvbench-lnet0.
    2018-12-04 17:15:28,368 INFO Created network: nfvbench-rnet0.
    2018-12-04 17:15:29,143 INFO Created port nfvbench-loop-vm0-0
    2018-12-04 17:15:29,626 INFO Security disabled on port nfvbench-loop-vm0-0
    2018-12-04 17:15:30,636 INFO Created port nfvbench-loop-vm0-1
    2018-12-04 17:15:31,139 INFO Security disabled on port nfvbench-loop-vm0-1
    2018-12-04 17:15:31,140 INFO Creating instance nfvbench-loop-vm0 with AZ
    2018-12-04 17:15:34,893 INFO Created instance nfvbench-loop-vm0 - waiting for placement resolution...
    2018-12-04 17:15:35,068 INFO Waiting for instance nfvbench-loop-vm0 to become active (retry 1/101)...
    <snip>
    2018-12-04 17:16:22,253 INFO Instance nfvbench-loop-vm0 is active and has been placed on nova:charter-compute-4
    2018-12-04 17:16:23,154 INFO Created network: nfvbench-lnet1.
    2018-12-04 17:16:23,863 INFO Created network: nfvbench-rnet1.
    2018-12-04 17:16:24,799 INFO Created port nfvbench-loop-vm1-0
    2018-12-04 17:16:25,267 INFO Security disabled on port nfvbench-loop-vm1-0
    2018-12-04 17:16:26,006 INFO Created port nfvbench-loop-vm1-1
    2018-12-04 17:16:26,612 INFO Security disabled on port nfvbench-loop-vm1-1
    2018-12-04 17:16:26,612 INFO Creating instance nfvbench-loop-vm1 with AZ nova:charter-compute-4
    2018-12-04 17:16:27,610 INFO Created instance nfvbench-loop-vm1 on nova:charter-compute-4
    2018-12-04 17:16:27,610 INFO Instance nfvbench-loop-vm0 is ACTIVE on nova:charter-compute-4
    2018-12-04 17:16:27,788 INFO Waiting for 1/2 instance to become active (retry 1/100)...
    <snip>

    2018-12-04 17:17:04,258 INFO Instance nfvbench-loop-vm1 is ACTIVE on nova:charter-compute-4
    2018-12-04 17:17:04,258 INFO All instances are active
    2018-12-04 17:17:04,259 INFO Port 0: VLANs [3830, 3831]
    2018-12-04 17:17:04,259 INFO Port 1: VLANs [3832, 3833]
    2018-12-04 17:17:04,259 INFO Port 0: dst MAC ['fa:16:3e:ef:f4:b0', 'fa:16:3e:e5:74:cd']
    2018-12-04 17:17:04,259 INFO Port 1: dst MAC ['fa:16:3e:d6:dc:84', 'fa:16:3e:8e:d9:30']
    2018-12-04 17:17:04,259 INFO ChainRunner initialized
    2018-12-04 17:17:04,260 INFO Starting 2xPVP benchmark...
    2018-12-04 17:17:04,266 INFO Starting traffic generator to ensure end-to-end connectivity
    2018-12-04 17:17:04,297 INFO Created 2 traffic streams for port 0.
    2018-12-04 17:17:04,300 INFO Created 2 traffic streams for port 1.
    2018-12-04 17:17:04,420 INFO Captured unique src mac 0/4, capturing return packets (retry 1/100)...
    2018-12-04 17:17:06,532 INFO Received packet from mac: fa:16:3e:d6:dc:84 (chain=0, port=1)
    2018-12-04 17:17:06,532 INFO Received packet from mac: fa:16:3e:ef:f4:b0 (chain=0, port=0)
    2018-12-04 17:17:06,644 INFO Captured unique src mac 2/4, capturing return packets (retry 2/100)...
    <snip>

    2018-12-04 17:17:24,337 INFO Received packet from mac: fa:16:3e:8e:d9:30 (chain=1, port=1)
    2018-12-04 17:17:24,338 INFO Received packet from mac: fa:16:3e:e5:74:cd (chain=1, port=0)
    2018-12-04 17:17:24,338 INFO End-to-end connectivity established
    2018-12-04 17:17:24,355 INFO Cleared all existing streams
    2018-12-04 17:17:24,383 INFO Created 4 traffic streams for port 0.
    2018-12-04 17:17:24,386 INFO Created 4 traffic streams for port 1.
    2018-12-04 17:17:24,386 INFO Starting to generate traffic...
    2018-12-04 17:17:24,386 INFO Running traffic generator
    2018-12-04 17:17:25,415 INFO TX: 1000004; RX: 1000004; Est. Dropped: 0; Est. Drop rate: 0.0000%
    2018-12-04 17:17:25,415 INFO ...traffic generating ended.
    2018-12-04 17:17:25,420 INFO Service chain 'PVP' run completed.
    2018-12-04 17:17:25,471 INFO Clean up skipped.
    2018-12-04 17:17:25,508 INFO
    ========== NFVBench Summary ==========
    Date: 2018-12-04 17:17:04
    NFVBench version 3.0.3.dev1
    Openstack Neutron:
      vSwitch: OPENVSWITCH
      Encapsulation: VLAN
    Benchmarks:
    > Networks:
      > Components:
        > Traffic Generator:
            Profile: trex-local
            Tool: TRex
        > Versions:
          > Traffic_Generator:
              build_date: Nov 13 2017
              version: v2.32
              built_by: hhaim
              mode: STL
              build_time: 10:58:17
          > CiscoVIM: 2.9.7-17036
      > Service chain:
        > PVP:
          > Traffic:
              Profile: traffic_profile_64B
              Bidirectional: True
              Flow count: 10000
              Service chains count: 2
              Compute nodes: [u'nova:charter-compute-4']

                Run Summary:

                  +-----------------+-------------+----------------------+----------------------+----------------------+
                  |   L2 Frame Size |  Drop Rate  |   Avg Latency (usec) |   Min Latency (usec) |   Max Latency (usec) |
                  +=================+=============+======================+======================+======================+
                  |              64 |   0.0000%   |                   18 |                   10 |                  120 |
                  +-----------------+-------------+----------------------+----------------------+----------------------+


                L2 frame size: 64

                Run Config:

                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |  Direction  |  Requested TX Rate (bps)  |  Actual TX Rate (bps)  |  RX Rate (bps)  |  Requested TX Rate (pps)  |  Actual TX Rate (pps)  |  RX Rate (pps)  |
                  +=============+===========================+========================+=================+===========================+========================+=================+
                  |   Forward   |       336.0000 Mbps       |     336.0013 Mbps      |  336.0013 Mbps  |        500,000 pps        |      500,002 pps       |   500,002 pps   |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |   Reverse   |       336.0000 Mbps       |     336.0013 Mbps      |  336.0013 Mbps  |        500,000 pps        |      500,002 pps       |   500,002 pps   |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |    Total    |       672.0000 Mbps       |     672.0027 Mbps      |  672.0027 Mbps  |       1,000,000 pps       |     1,000,004 pps      |  1,000,004 pps  |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+

                Forward Chain Packet Counters and Latency:

                  +---------+--------------+--------------+------------+------------+------------+
                  |  Chain  |  TRex.TX.p0  |  TRex.RX.p1  |  Avg lat.  |  Min lat.  |  Max lat.  |
                  +=========+==============+==============+============+============+============+
                  |    0    |   250,001    |   250,001    |  26 usec   |  10 usec   |  70 usec   |
                  +---------+--------------+--------------+------------+------------+------------+
                  |    1    |   250,001    |   250,001    |  11 usec   |  10 usec   |  39 usec   |
                  +---------+--------------+--------------+------------+------------+------------+
                  |  total  |   500,002    |   500,002    |  19 usec   |  10 usec   |  70 usec   |
                  +---------+--------------+--------------+------------+------------+------------+

                Reverse Chain Packet Counters and Latency:

                  +---------+--------------+--------------+------------+------------+------------+
                  |  Chain  |  TRex.TX.p1  |  TRex.RX.p0  |  Avg lat.  |  Min lat.  |  Max lat.  |
                  +=========+==============+==============+============+============+============+
                  |    0    |   250,001    |   250,001    |  19 usec   |  10 usec   |  119 usec  |
                  +---------+--------------+--------------+------------+------------+------------+
                  |    1    |   250,001    |   250,001    |  19 usec   |  10 usec   |  120 usec  |
                  +---------+--------------+--------------+------------+------------+------------+
                  |  total  |   500,002    |   500,002    |  19 usec   |  10 usec   |  120 usec  |
                  +---------+--------------+--------------+------------+------------+------------+
