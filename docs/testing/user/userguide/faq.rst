.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Frequently Asked Questions
**************************

General Questions
=================

Can NFVbench be used with a different traffic generator than TRex?
------------------------------------------------------------------
This is possible but requires developing a new python class to manage the new traffic generator interface.

Can I connect Trex directly to my compute node?
-----------------------------------------------
That is possible but you will not be able to run more advanced use cases such as PVVP inter-node which requires 2 compute nodes.

Can I drive NFVbench using a REST interface?
--------------------------------------------
NFVbench can run in server mode and accept HTTP or WebSocket/SocketIO events to run any type of measurement (fixed rate run or NDR_PDR run)
with any run configuration.

Can I run NFVbench on a Cisco UCS-B series blade?
-------------------------------------------------
Yes provided your UCS-B series server has a Cisco VIC 1340 (with a recent firmware version).
TRex will require VIC firmware version 3.1(2) or higher for blade servers (which supports more filtering capabilities).
In this setting, the 2 physical interfaces for data plane traffic are simply hooked to the UCS-B fabric interconnect (no need to connect to a switch).

Troubleshooting
===============

TrafficClientException: End-to-end connectivity cannot be ensured
------------------------------------------------------------------
Prior to running a benchmark, NFVbench will make sure that traffic is passing in the service chain by sending a small flow of packets in each direction and verifying that they are received back at the other end.
This exception means that NFVbench cannot pass any traffic in the service chain.

The most common issues that prevent traffic from passing are:
- incorrect wiring of the NFVbench/TRex interfaces
- incorrect vlan_tagging setting in the NFVbench configuration, this needs to match how the NFVbench ports on the switch are configured (trunk or access port)
   - if the switch port is configured as access port, you must disable vlan_tagging in the NFVbench configuration
   - of the switch port is configured as trunk (recommended method), you must enable it

