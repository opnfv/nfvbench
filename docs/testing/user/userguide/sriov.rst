.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc


Testing SR-IOV
==============

NFVbench supports SR-IOV with the PVP and PVVP packet flows. SR-IOV support is not applicable for external chains since the networks have to be setup externally (and can themselves be pre-set to use SR-IOV or not).

Pre-requisites
--------------
To test SR-IOV you need to have compute nodes configured to support one or more SR-IOV interfaces (also knows as PF or physical function) and you need OpenStack to be configured to support SR-IOV.
You will also need to know:
- the name of the physical networks associated to your SR-IOV interfaces (this is a configuration in Nova compute)
- the VLAN range that can be used on the switch ports that are wired to the SR-IOV ports. Such switch ports are normally configured in trunk mode with a range of VLAN ids enabled on that port

For example, in the case of 2 SR-IOV ports per compute node, 2 physical networks are generally configured in OpenStack with a distinct name. The VLAN range to use is is also allocated and reserved by the network administrator and in coordination with the corresponding top of rack switch port configuration.


Configuration
-------------
To enable SR-IOV test, you will need to provide the following configuration options to NFVbench (in the configuration file).
This example instructs NFVbench to create the left and right networks of a PVP packet flow to run on 2 SRIOV ports named "phys_sriov0" and "phys_sriov1" using resp. segmentation_id 2000 and 2001:

.. code-block:: bash
    
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


NIC NUMA socket placement and flavors
-------------------------------------
If the 2 selected ports reside on NICs that are on different NUMA sockets, you will need to explicitly tell Nova to use 2 numa nodes in the flavor used for the VMs in order to satisfy the filters, for example:

.. code-block:: bash

    flavor:
      # Number of vCPUs for the flavor
      vcpus: 2
      # Memory for the flavor in MB
      ram: 8192
      # Size of local disk in GB
      disk: 0
      extra_specs:
          "hw:cpu_policy": dedicated
          "hw:mem_page_size": large
          "hw:numa_nodes": 2

Failure to do so might cause the VM creation to fail with the Nova error "Instance creation error: Insufficient compute resources: Requested instance NUMA topology together with requested PCI devices cannot fit the given host NUMA topology."

