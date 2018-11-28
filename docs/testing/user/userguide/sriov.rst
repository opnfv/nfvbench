.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc


Testing SR-IOV
==============

NFVbench supports SR-IOV with the PVP packet flow (PVVP is not supported). SR-IOV support is not applicable for external chains since the networks have to be setup externally (and can themselves be pre-set to use SR-IOV or not).

Pre-requisites
--------------
To test SR-IOV you need to have compute nodes configured to support one or more SR-IOV interfaces (also knows as PF or physical function) and you need OpenStack to be configured to support SR-IOV.
You will also need to know:
- the name of the physical networks associated to your SR-IOV interfaces (this is a configuration in Nova compute)
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

Example of configuration file (summary)
---------------------------------------

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
