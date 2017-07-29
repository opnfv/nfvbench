.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Frequently Asked Questions
**************************

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