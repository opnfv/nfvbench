NFVBENCH VM IMAGES FOR OPENSTACK
++++++++++++++++++++++++++++++++

This repo will build two centos 7 images with:
    - testpmd and VPP installed for loop VM use case
    - NFVbench and TRex installed for generator VM use case
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
- to build loop VM image only:
    - `bash build-image.sh -l`
- to build generator VM image only:
    - `bash build-image.sh -g`
- to build both images only:
    - `bash build-image.sh`

LOOP VM IMAGE INSTANCE AND CONFIG
=================================

Interface Requirements
----------------------
The instance must be launched using OpenStack with 2 network interfaces.
For best performance, it should use a flavor with:

- 2 vCPU
- 4 GB RAM
- cpu pinning set to exclusive

Auto-configuration
------------------
nfvbench VM will automatically find the two virtual interfaces to use, and use the forwarder specifed in the config file.

In the case testpmd is used, testpmd will be launched with mac forwarding mode where the destination macs rewritten according to the config file.

In the case VPP is used, VPP will set up a L3 router, and forwarding traffic from one port to the other.

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


Hardcoded Username and Password
--------------------------------
- Username: nfvbench
- Password: nfvbench


GENERATOR IMAGE INSTANCE AND CONFIG
===================================

Interface Requirements
----------------------
The instance must be launched using OpenStack with 2 network interfaces using SR-IOV function.
For best performance, it should use interfaces with a `vnic_type` to `direct-physical` (or `direct` if physical function is not possible) a flavor with:

- 6 vCPU
- 8 GB RAM
- cpu pinning set to exclusive


Auto-configuration
------------------
nfvbench VM will automatically find the two virtual interfaces to use.

nfvbenchvm Config
-----------------
nfvbenchvm config file is located at ``/etc/nfvbenchvm.conf``.

Example of configuration:

.. code-block:: bash

    LOOPBACK_INTF_MAC1=FA:16:3E:A2:30:41
    LOOPBACK_INTF_MAC2=FA:16:3E:10:DA:10
    E2E_INTF_MAC1=FA:16:3E:B0:E2:43
    E2E_INTF_MAC2=FA:16:3E:D3:6A:FC
    ACTION=e2e
.. note:: `ACTION` parameter is not mandatory but will permit to start NFVbench with the accurate ports (loopback or e2e)

Using pre-created direct-physical ports on openstack, mac addresses value are only known when VM is deployed. In this case, you can pass the port name in config:

.. code-block:: bash

    LOOPBACK_PORT_NAME1=nfvbench-pf1
    LOOPBACK_PORT_NAME2=nfvbench-pf2
    E2E_PORT_NAME1=nfvbench-pf1
    E2E_PORT_NAME1=nfvbench-pf3
.. note:: NFVbench VM will call openstack API to retrieve mac address for these ports
.. note:: A management interface can be set up and NFVbench VM will automatically find the virtual interface to use according to the MAC address provided (see `INTF_MAC_MGMT` parameter).

nfvbenchvm config file with management interface:

.. code-block:: bash

    LOOPBACK_PORT_NAME1=nfvbench-pf1
    LOOPBACK_PORT_NAME2=nfvbench-pf2
    E2E_PORT_NAME1=nfvbench-pf1
    E2E_PORT_NAME1=nfvbench-pf3
    INTF_MAC_MGMT=FA:16:3E:06:11:8A
    INTF_MGMT_CIDR=172.20.56.228/2
    INTF_MGMT_IP_GW=172.20.56.225

.. note:: `INTF_MGMT_IP_GW` and `INTF_MGMT_CIDR` parameters are used by the VM to automatically configure virtual interface and route to allow an external access through SSH.


Launching nfvbenchvm VM
-----------------------

Normally this image will be deployed using Ansible role, and the required configurations will be automatically generated and pushed to VM by Ansible.
If launched manually, users will have the full control to configure and run NFVbench via VNC console.

To check if NFVbench is running, you can run this command in VNC console:

.. code-block:: bash

    sudo screen -r nfvbench


Hardcoded Username and Password
--------------------------------
- Username: nfvbench
- Password: nfvbench

