.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Requirements for running NFVbench
=================================

.. _requirements:

Hardware Requirements
---------------------
To run NFVbench you need the following hardware:
- a Linux server
- a DPDK compatible NIC with at least 2 ports (preferably 10Gbps or higher)
- 2 ethernet cables between the NIC and the OpenStack pod under test (usually through a top of rack switch)

The DPDK-compliant NIC must be one supported by the TRex traffic generator (such as Intel X710, refer to the `Trex Installation Guide <https://trex-tgn.cisco.com/trex/doc/trex_manual.html#_download_and_installation>`_ for a complete list of supported NIC)

To run the TRex traffic generator (that is bundled with NFVbench) you will need to wire 2 physical interfaces of the NIC to the TOR switch(es):
    - if you have only 1 TOR, wire both interfaces to that same TOR
    - 1 interface to each TOR if you have 2 TORs and want to use bonded links to your compute nodes

.. image:: images/nfvbench-trex-setup.png


Switch Configuration
--------------------
The 2 corresponding ports on the switch(es) facing the Trex ports on the Linux server should be configured in trunk mode (NFVbench will instruct TRex to insert the appropriate vlan tag).

Using a TOR switch is more representative of a real deployment and allows to measure packet flows on any compute node in the rack without rewiring and includes the overhead of the TOR switch.

Although not the primary targeted use case, NFVbench could also support the direct wiring of the traffic generator to
a compute node without a switch.

Software Requirements
---------------------

You need Docker to be installed on the Linux server.

TRex uses the DPDK interface to interact with the DPDK compatible NIC for sending and receiving frames. The Linux server will
need to be configured properly to enable DPDK.

DPDK requires a uio (User space I/O) or vfio (Virtual Function I/O) kernel module to be installed on the host to work.
There are 2 main uio kernel modules implementations (igb_uio and uio_pci_generic) and one vfio kernel module implementation.

To check if a uio or vfio is already loaded on the host:

.. code-block:: bash

    lsmod | grep -e igb_uio -e uio_pci_generic -e vfio


If missing, it is necessary to install a uio/vfio kernel module on the host server:

- find a suitable kernel module for your host server (any uio or vfio kernel module built with the same Linux kernel version should work)
- load it using the modprobe and insmod commands

Example of installation of the igb_uio kernel module:

.. code-block:: bash

    modprobe uio
    insmod ./igb_uio.ko

Finally, the correct iommu options and huge pages to be configured on the Linux server on the boot command line:

- enable intel_iommu and iommu pass through: "intel_iommu=on iommu=pt"
- for Trex, pre-allocate 1024 huge pages of 2MB each (for a total of 2GB): "hugepagesz=2M hugepages=1024"

More detailed instructions can be found in the DPDK documentation (https://buildmedia.readthedocs.org/media/pdf/dpdk/latest/dpdk.pdf).
