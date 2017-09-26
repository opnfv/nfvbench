.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

NFVbench Server mode and NFVbench client API
============================================

NFVbench can run as an HTTP server to:

- optionally provide access to any arbitrary HTLM files (HTTP server function) - this is optional
- service fully parameterized aynchronous run requests using the HTTP protocol (REST/json with polling)
- service fully parameterized run requests with interval stats reporting using the WebSocket/SocketIO protocol.

Start the NFVbench server
-------------------------
To run in server mode, simply use the --server <http_root_path> and optionally the listen address to use (--host <ip>, default is 0.0.0.0) and listening port to use (--port <port>, default is 7555).


If HTTP files are to be serviced, they must be stored right under the http root path.
This root path must contain a static folder to hold static files (css, js) and a templates folder with at least an index.html file to hold the template of the index.html file to be used.
This mode is convenient when you do not already have a WEB server hosting the UI front end.
If HTTP files servicing is not needed (REST only or WebSocket/SocketIO mode), the root path can point to any dummy folder.

Once started, the NFVbench server will be ready to service HTTP or WebSocket/SocketIO requests at the advertised URL.

Example of NFVbench server start in a container:

.. code-block:: bash

    # get to the container shell (assume the container name is "nfvbench")
    docker exec -it nfvbench bash
    # from the container shell start the NFVbench server in the background
    nfvbench -c /tmp/nfvbench/nfvbench.cfg --server /tmp &
    # exit container
    exit



HTTP Interface
--------------

<http-url>/echo (GET)
^^^^^^^^^^^^^^^^^^^^^

This request simply returns whatever content is sent in the body of the request (body should be in json format, only used for testing)

Example request: curl -XGET '127.0.0.1:7556/echo' -H "Content-Type: application/json" -d '{"nfvbench": "test"}'
Response:
{
  "nfvbench": "test"
}


<http-url>/status (GET)
^^^^^^^^^^^^^^^^^^^^^^^

This request fetches the status of an asynchronous run. It will return in json format:

- a request pending reply (if the run is still not completed)
- an error reply if there is no run pending
- or the complete result of the run

The client can keep polling until the run completes.

Example of return when the run is still pending:

.. code-block:: bash

    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }

Example of return when the run completes:

.. code-block:: bash

    {
      "result": {...}
      "status": "OK"
    }


<http-url>/start_run (POST)
^^^^^^^^^^^^^^^^^^^^^

This request starts an NFVBench run with passed configurations. If no configuration is passed, a run with default configurations will be executed.

Example request: curl -XPOST 'localhost:7556/start_run' -H "Content-Type: application/json" -d @nfvbenchconfig.json

See "NFVbench configuration JSON parameter" below for details on how to format this parameter.

The request returns immediately with a json content indicating if there was an error (status=ERROR) or if the request was submitted successfully (status=PENDING).
Example of return when the submission is successful:

.. code-block:: bash

    {
      "error_message": "NFVbench run still pending",
      "request_id": "42cccb7effdc43caa47f722f0ca8ec96",
      "status": "PENDING"
    }

If there is already an NFVBench running then it will return

.. code-block:: bash

    {
     "error_message": "there is already an NFVbench request running",
     "status": "ERROR"
    }

WebSocket/SocketIO events
-------------------------

List of SocketIO events supported:

Client to Server
^^^^^^^^^^^^^^^^

start_run:

    sent by client to start a new run with the configuration passed in argument (JSON).
    The configuration can be any valid NFVbench configuration passed as a JSON document (see "NFVbench configuration JSON parameter" below)

Server to Client
^^^^^^^^^^^^^^^^

run_interval_stats:

    sent by server to report statistics during a run
    the message contains the statistics {'time_ms': time_ms, 'tx_pps': tx_pps, 'rx_pps': rx_pps, 'drop_pct': drop_pct}

ndr_found:

    (during NDR-PDR search)
    sent by server when the NDR rate is found
    the message contains the NDR value {'rate_pps': ndr_pps}

ndr_found:

    (during NDR-PDR search)
    sent by server when the PDR rate is found
    the message contains the PDR value {'rate_pps': pdr_pps}


run_end:

    sent by server to report the end of a run
    the message contains the complete results in JSON format

NFVbench configuration JSON parameter
-------------------------------------
The NFVbench configuration describes the parameters of an NFVbench run and can be passed to the NFVbench server as a JSON document.

Default configuration
^^^^^^^^^^^^^^^^^^^^^

The simplest JSON document is the empty dictionary "{}" which indicates to use the default NFVbench configuration:

- PVP
- NDR-PDR measurement
- 64 byte packets
- 1 flow per direction

The entire default configuration can be viewed using the --show-json-config option on the cli:

.. code-block:: bash

    # nfvbench --show-config
    {
        "availability_zone": null,
        "compute_node_user": "root",
        "compute_nodes": null,
        "debug": false,
        "duration_sec": 60,
        "flavor": {
            "disk": 0,
            "extra_specs": {
                "hw:cpu_policy": "dedicated",
                "hw:mem_page_size": 2048
            },
            "ram": 8192,
            "vcpus": 2
        },
        "flavor_type": "nfv.medium",
        "flow_count": 1,
        "generic_poll_sec": 2,
        "generic_retry_count": 100,
        "inter_node": false,
        "internal_networks": {
            "left": {
                "name": "nfvbench-net0",
                "subnet": "nfvbench-subnet0",
                "cidr": "192.168.1.0/24",
            },
            "right": {
                "name": "nfvbench-net1",
                "subnet": "nfvbench-subnet1",
                "cidr": "192.168.2.0/24",
            },
            "middle": {
                "name": "nfvbench-net2",
                "subnet": "nfvbench-subnet2",
                "cidr": "192.168.3.0/24",
            }
        },
        "interval_sec": 10,
        "json": null,
        "loop_vm_name": "nfvbench-loop-vm",
        "measurement": {
            "NDR": 0.001,
            "PDR": 0.1,
            "load_epsilon": 0.1
        },
        "name": "(built-in default config)",
        "no_cleanup": false,
        "no_int_config": false,
        "no_reset": false,
        "no_tor_access": false,
        "no_traffic": false,
        "no_vswitch_access": false,
        "openrc_file": "/tmp/nfvbench/openstack/openrc",
        "openstack_defaults": "/tmp/nfvbench/openstack/defaults.yaml",
        "openstack_setup": "/tmp/nfvbench/openstack/setup_data.yaml",
        "rate": "ndr_pdr",
        "service_chain": "PVP",
        "service_chain_count": 1,
        "sriov": false,
        "std_json": null,
        "tor": {
            "switches": [
                {
                    "host": "172.26.233.12",
                    "password": "lab",
                    "port": 22,
                    "username": "admin"
                }
            ],
            "type": "N9K"
        },
        "traffic": {
            "bidirectional": true,
            "profile": "traffic_profile_64B"
        },
        "traffic_generator": {
            "default_profile": "trex-local",
            "gateway_ip_addrs": [
                "1.1.0.2",
                "2.2.0.2"
            ],
            "gateway_ip_addrs_step": "0.0.0.1",
            "generator_profile": [
                {
                    "cores": 3,
                    "interfaces": [
                        {
                            "pci": "0a:00.0",
                            "port": 0,
                            "switch_port": "Ethernet1/33",
                            "vlan": null
                        },
                        {
                            "pci": "0a:00.1",
                            "port": 1,
                            "switch_port": "Ethernet1/34",
                            "vlan": null
                        }
                    ],
                    "intf_speed": "10Gbps",
                    "ip": "127.0.0.1",
                    "name": "trex-local",
                    "tool": "TRex"
                }
            ],
            "host_name": "nfvbench_tg",
            "ip_addrs": [
                "10.0.0.0/8",
                "20.0.0.0/8"
            ],
            "ip_addrs_step": "0.0.0.1",
            "mac_addrs": [
                "00:10:94:00:0A:00",
                "00:11:94:00:0A:00"
            ],
            "step_mac": null,
            "tg_gateway_ip_addrs": [
                "1.1.0.100",
                "2.2.0.100"
            ],
            "tg_gateway_ip_addrs_step": "0.0.0.1"
        },
        "traffic_profile": [
            {
                "l2frame_size": [
                    "64"
                ],
                "name": "traffic_profile_64B"
            },
            {
                "l2frame_size": [
                    "IMIX"
                ],
                "name": "traffic_profile_IMIX"
            },
            {
                "l2frame_size": [
                    "1518"
                ],
                "name": "traffic_profile_1518B"
            },
            {
                "l2frame_size": [
                    "64",
                    "IMIX",
                    "1518"
                ],
                "name": "traffic_profile_3sizes"
            }
        ],
        "unidir_reverse_traffic_pps": 1,
        "vlan_tagging": true,
        "vts_ncs": {
            "host": null,
            "password": "secret",
            "port": 22,
            "username": "admin"
        }
    }


Common examples of JSON configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the default configuration but use 10000 flows per direction (instead of 1):

.. code-block:: bash

    { "flow_count": 10000 }


Use default confguration but with 10000 flows, "EXT" chain and IMIX packet size:

.. code-block:: bash

    {
       "flow_count": 10000,
       "service_chain": "EXT",
        "traffic": {
            "profile": "traffic_profile_IMIX"
        },
    }

A short run of 5 seconds at a fixed rate of 1Mpps (and everything else same as the default configuration):

.. code-block:: bash

    {
       "duration": 5,
       "rate": "1Mpps"
    }

Example of interaction with the NFVbench server using HTTP and curl
-------------------------------------------------------------------
HTTP requests can be sent directly to the NFVbench server from CLI using curl from any host that can connect to the server (here we run it from the local host).

This is a POST request to start a run using the default NFVbench configuration but with traffic generation disabled ("no_traffic" property is set to true):

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -H "Accept: application/json" -H "Content-type: application/json" -X POST -d '{"no_traffic":true}' http://127.0.0.1:7555/start_run
    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }
    [root@sjc04-pod3-mgmt ~]#

This request will return immediately with status set to "PENDING" if the request was started successfully.

The status can be polled until the run completes. Here the poll returns a "PENDING" status, indicating the run is still not completed:

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -G http://127.0.0.1:7555/status
    {
      "error_message": "nfvbench run still pending",
      "status": "PENDING"
    }
    [root@sjc04-pod3-mgmt ~]#

Finally, the status request returns a "OK" status along with the full results (truncated here):

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# curl -G http://127.0.0.1:7555/status
    {
      "result": {
        "benchmarks": {
          "network": {
            "service_chain": {
              "PVP": {
                "result": {
                  "bidirectional": true,
                  "compute_nodes": {
                    "nova:sjc04-pod3-compute-4": {
                      "bios_settings": {
                        "Adjacent Cache Line Prefetcher": "Disabled",
                        "All Onboard LOM Ports": "Enabled",
                        "All PCIe Slots OptionROM": "Enabled",
                        "Altitude": "300 M",
    ...

        "date": "2017-03-31 22:15:41",
        "nfvbench_version": "0.3.5",
        "openstack_spec": {
          "encaps": "VxLAN",
          "vswitch": "VTS"
        }
      },
      "status": "OK"
    }
    [root@sjc04-pod3-mgmt ~]#



Example of interaction with the NFVbench server using a python CLI app (nfvbench_client)
----------------------------------------------------------------------------------------
The module client/client.py contains an example of python class that can be used to control the NFVbench server from a python app using HTTP or WebSocket/SocketIO.

The module client/nfvbench_client.py has a simple main application to control the NFVbench server from CLI.
The "nfvbench_client" wrapper script can be used to invoke the client front end (this wrapper is pre-installed in the NFVbench container)

Example of invocation of the nfvbench_client front end, from the host (assume the name of the NFVbench container is "nfvbench"),
use the default NFVbench configuration but do not generate traffic (no_traffic property set to true, the full json result is truncated here):

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# docker exec -it nfvbench nfvbench_client -c '{"no_traffic":true}' http://127.0.0.1:7555
    {u'status': u'PENDING', u'error_message': u'nfvbench run still pending'}
    {u'status': u'PENDING', u'error_message': u'nfvbench run still pending'}
    {u'status': u'PENDING', u'error_message': u'nfvbench run still pending'}

    {u'status': u'OK', u'result': {u'date': u'2017-03-31 22:04:59', u'nfvbench_version': u'0.3.5',
    u'config': {u'compute_nodes': None, u'compute_node_user': u'root', u'vts_ncs': {u'username': u'admin', u'host': None, u'password': u'secret', u'port': 22}, u'traffic_generator': {u'tg_gateway_ip_addrs': [u'1.1.0.100', u'2.2.0.100'], u'ip_addrs_step': u'0.0.0.1', u'step_mac': None, u'generator_profile': [{u'intf_speed': u'10Gbps', u'interfaces': [{u'pci': u'0a:00.0', u'port': 0, u'vlan': 1998, u'switch_port': None},

    ...

    [root@sjc04-pod3-mgmt ~]#

The http interface is used unless --use-socketio is defined.

Example of invocation using Websocket/SocketIO, execute NFVbench using the default configuration but with a duration of 5 seconds and a fixed rate run of 5kpps.

.. code-block:: bash

    [root@sjc04-pod3-mgmt ~]# docker exec -it nfvbench nfvbench_client -c '{"duration":5,"rate":"5kpps"}' --use-socketio  http://127.0.0.1:7555 >results.json







