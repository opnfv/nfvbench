NFVBENCH VM IMAGES FOR OPENSTACK
++++++++++++++++++++++++++++++++

This repo will build two centos 7 images with:
    - testpmd and VPP installed for loop VM use case
    - NFVbench and TRex installed for generator VM use case
These VMs will come with a pre-canned user/password: nfvbench/nfvbench

BUILD INSTRUCTIONS
==================

Pre-requisites
--------------
- must run on Linux
- the following packages must be installed prior to using this script:
    - python3 (+ python3-venv on Ubuntu)
    - python3-pip
    - git
    - qemu-img (CentOs) or qemu-utils (Ubuntu)
    - kpartx

.. note:: the image build process is based on `diskimage-builder
          <https://docs.openstack.org/diskimage-builder/latest/index.html>`_
          that will be installed in a Python virtual environment by nfvbenchvm
          build script build-image.sh.

.. note:: build-image.sh uses the `gsutil <https://pypi.org/project/gsutil/>`_
          tool to interact with Google cloud storage (to check if the images
          exist and to upload the images).  This is normally only needed in the
          context of OPNFV build infrastructure, and build-image.sh can be used
          without that tool in development environments.

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

Pre-requisites
--------------
To use openstack APIs, NFVbench generator VM will use `clouds.yaml` file as openstack configuration.
The OpenStack clouds configuration from clouds.yaml file to use.
clouds.yaml file must be in one of the following paths:
- ~/.config/openstack
- /etc/openstack

Example of `clouds.yaml`:

.. code-block:: yaml

    clouds:
      devstack:
        auth:
          auth_url: http://192.168.122.10:35357/
          project_name: demo
          username: demo
          password: 0penstack
        region_name: RegionOne

.. note:: Add `CLOUD_DETAIL` property with the accurate value for your openstack configuration (`devstack` in the above example) in ``/etc/nfvbenchvm.conf``

Interface Requirements
----------------------
The instance must be launched using OpenStack with 2 network interfaces for dataplane traffic (using SR-IOV function) and 1 management interface to control nfvbench.
For best performance, it should use network interfaces for dataplane traffic with a `vnic_type` to `direct-physical` (or `direct` if physical function is not possible)
and a flavor with:

- 6 vCPU
- 8 GB RAM
- cpu pinning set to exclusive

.. note:: For the management interface: any interface type can be used. This interface required a routable IP (through floating IP or direct) and an access to the openstack APIs.
.. note:: CPU pinning: 1 core dedicated for guest OS and NFVbench process, other provided cores are used by TRex

Template of a genarator profile using CPU pinning:

.. code-block:: bash

    generator_profile:
        - name: {{name}}
          tool: {{tool}}
          ip: {{ip}}
          zmq_pub_port: {{zmq_pub_port}}
          zmq_rpc_port: {{zmq_rpc_port}}
          software_mode: {{software_mode}}
          cores: {{CORES}}
          platform:
            master_thread_id: '0'
            latency_thread_id: '1'
            dual_if:
              - socket: 0
                threads: [{{CORE_THREADS}}]

          interfaces:
            - port: 0
              pci: "{{PCI_ADDRESS_1}}"
              switch:
            - port: 1
              pci: "{{PCI_ADDRESS_2}}"
              switch:
          intf_speed:

.. note:: `CORE_THREADS` value is determined automatically based on the cores available on the VM starting from 2 to last worker core available.

Auto-configuration
------------------
nfvbench VM will automatically find the two virtual interfaces to use for dataplane based on MAC addresses or openstack port name (see config part below).
This applies to the management interface as well.

nfvbenchvm Config
-----------------
nfvbenchvm config file is located at ``/etc/nfvbenchvm.conf``.

Example of configuration:

.. code-block:: bash

    ACTION=e2e
    LOOPBACK_INTF_MAC1=FA:16:3E:A2:30:41
    LOOPBACK_INTF_MAC2=FA:16:3E:10:DA:10
    E2E_INTF_MAC1=FA:16:3E:B0:E2:43
    E2E_INTF_MAC2=FA:16:3E:D3:6A:FC

.. note:: `ACTION` parameter is not mandatory but will permit to start NFVbench with the accurate ports (loopback or e2e).
.. note:: Set of MAC parameters cannot be used in parallel as only one NFVbench/TRex process is running.
.. note:: Switching from `loopback` to `e2e` action can be done manually using `/nfvbench/start-nfvbench.sh <action>` with the accurate keyword for `action` parameter. This script will restart NFVbench with the good set of MAC.

nfvbenchvm config file with management interface:

.. code-block:: bash

    ACTION=e2e
    LOOPBACK_INTF_MAC1=FA:16:3E:A2:30:41
    LOOPBACK_INTF_MAC2=FA:16:3E:10:DA:10
    INTF_MAC_MGMT=FA:16:3E:06:11:8A
    INTF_MGMT_CIDR=172.20.56.228/2
    INTF_MGMT_IP_GW=172.20.56.225

.. note:: `INTF_MGMT_IP_GW` and `INTF_MGMT_CIDR` parameters are used by the VM to automatically configure virtual interface and route to allow an external access through SSH.


Using pre-created direct-physical ports on openstack, mac addresses value are only known when VM is deployed. In this case, you can pass the port name in config:

.. code-block:: bash

    LOOPBACK_PORT_NAME1=nfvbench-pf1
    LOOPBACK_PORT_NAME2=nfvbench-pf2
    E2E_PORT_NAME1=nfvbench-pf1
    E2E_PORT_NAME1=nfvbench-pf3
    INTF_MAC_MGMT=FA:16:3E:06:11:8A
    INTF_MGMT_CIDR=172.20.56.228/2
    INTF_MGMT_IP_GW=172.20.56.225
    DNS_SERVERS=8.8.8.8,dns.server.com

.. note:: A management interface is required to automatically find the virtual interface to use according to the MAC address provided (see `INTF_MAC_MGMT` parameter).
.. note:: NFVbench VM will call openstack API through the management interface to retrieve mac address for these ports
.. note:: If openstack API required a host name resolution, add the parameter DNS_SERVERS to add IP or DNS server names (multiple servers can be added separated by a `,`)

Control nfvbenchvm VM and run test
----------------------------------

By default, NFVbench will be started in server mode (`--server`) and will act as an API.

NFVbench VM will be accessible through SSH or HTTP using the management interface IP.

NFVbench API endpoint is : `http://<management_ip>:<port>`
.. note:: by default port value is 7555

Get NFVbench status
^^^^^^^^^^^^^^^^^^^

To check NFVbench is up and running use REST request:

.. code-block:: bash

curl -XGET '<management_ip>:<port>/status'

Example of answer:

.. code-block:: bash

    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }

Start NFVbench test
^^^^^^^^^^^^^^^^^^^

To start a test run using NFVbench API use this type of REST request:

.. code-block:: bash

curl -XPOST '<management_ip>:<port>/start_run' -H "Content-Type: application/json" -d @nfvbenchconfig.json

Example of return when the submission is successful:

.. code-block:: bash

    {
      "error_message": "NFVbench run still pending",
      "request_id": "42cccb7effdc43caa47f722f0ca8ec96",
      "status": "PENDING"
    }


Start NFVbench test using Xtesting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To start a test run using Xtesting python library and NFVbench API use this type of command on the VM:

.. code-block:: bash

run_tests -t nfvbench-demo

.. note:: `-t` option determine which test case to be runned by Xtesting
 (see `xtesting/testcases.yaml` file content to see available list of test cases)


Connect to the VM using SSH keypair
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If a key is provided at VM creation you can use it to log on the VM using `cloud-user` username:

.. code-block:: bash

    ssh -i key.pem cloud-user@<management_ip>


Connect to VM using SSH username/password
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

VM is accessible over SSH using the hardcoded username and password (see below):

.. code-block:: bash

    ssh nfvbench@<management_ip>


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

