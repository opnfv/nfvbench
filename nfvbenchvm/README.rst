NFVBENCH VM IMAGE FOR OPENSTACK

+++++++++++++++++++++++++++++++

This repo will build a centos 7 image with nfvbench, trex, testpmd and VPP installed.
The VM will come with a pre-canned user/password: nfvbench/nfvbench

BUILD INSTRUCTIONS
==================

Pre-requisites
--------------

- must run on Linux
- the following packages must be installed prior to using this script:
  - git
  - qemu-utils
  - kpartx

Build the image
---------------

- cd dib
- update the version number for the image (if needed) by modifying __version__ in build-image.sh
- setup your http_proxy if needed
- bash build-image.sh

IMAGE INSTANCE AND CONFIG
=========================

Interface Requirements
----------------------

The new CentOS based hybrid image can be used as loop VM for PVP, PVVP & other use cases and also to create the traffic-generator VM to run nfvbench.

The loop VM image can be deployed with:

**1. Loop VM without management port, total 2 interfaces**

The instance must be launched using OpenStack with 2 network interfaces.
For best performance, it should use a flavor with:

- 2 vCPU
- 4 GB RAM
- cpu pinning set to exclusive

**2. Loop VM with management port, total 3 interfaces**

The instance must be launched on Openstack with one SRIOV compute node with 3 network interfaces (1 for management network and 2 for Trex traffic generator)

Following are the minimum requirements for launcher VM and SRIOV:

- 8GB RAM
- 8 vCPU
- 20GB DISK

Auto-configuration
------------------

**For Loop VM:**

nfvbench VM will automatically find the two virtual interfaces to use, and use the forwarder specifed in the config file.

In the case testpmd is used, testpmd will be launched with mac forwarding mode where the destination macs rewritten according to the config file.

In the case VPP is used, VPP will set up a L3 router, and forwarding traffic from one port to the other.

**For Trex traffic generator VM:**

nfvbench-launcher VM will automatically bring up management network with virtio-pci on boot of trex traffic generator VM  and other two interfaces can be used to generate traffic.

These minimal changes allows to run nfvbench in VM without need of any external connectivity. It doesn't modify the procedure to use this image as loop VM.

nfvbenchvm Config
-----------------

nfvbenchvm config file is located at ``/etc/nfvbenchvm.conf``.

.. code-block:: bash

    FORWARDER=testpmd
    INTF_MAC1=FA:16:3E:A2:30:41
    INTF_MAC2=FA:16:3E:10:DA:10
    TG_MAC1=00:10:94:00:0A:00
    TG_MAC2=00:11:94:00:0A:00
    VNF_GATEWAY1_CIDR=1.1.0.2/8
    VNF_GATEWAY2_CIDR=2.2.0.2/8
    TG_NET1=10.0.0.0/8
    TG_NET2=20.0.0.0/8
    TG_GATEWAY1_IP=1.1.0.100
    TG_GATEWAY2_IP=2.2.0.100


Launching nfvbenchvm VM
-----------------------

Normally this image will be used together with NFVBench, and the required configurations will be automatically generated and pushed to VM by NFVBench. If launched manually, no forwarder will be run. Users will have the full control to run either testpmd or VPP via VNC console.

To check if testpmd is running, you can run this command in VNC console:

.. code-block:: bash

    sudo screen -r testpmd

To check if VPP is running, you can run this command in VNC console:

.. code-block:: bash

    service vpp status

Launching Trex traffic-generator VM
-----------------------

This image will be used together with NFVBench, and the required configurations will be automatically generated and pushed to VM by NFVBench.  This image is used to create a new image which can be used to run nfvbench as well as can be used as loop VM. The nfvbench and trex comes preinstalled in the new hybrid CentOS image.

The new CentOS based hybrid image can be used as loop VM for PVP, PVVP & other use cases.

To check if nfvbench is installed, you can run this command in VNC console:


.. code-block:: bash

    nfvbench --version


Hardcoded Username and Password
--------------------------------

- Username: nfvbench
- Password: nfvbench

