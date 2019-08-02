.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Frequently Asked Questions
**************************

General Questions
=================

Can NFVbench be used without OpenStack
--------------------------------------
Yes. This can be done using the EXT chain mode, with or without ARP
(depending on whether your systen under test can do routing) and by setting the openrc_file
property to empty in the NFVbench configuration.

Can NFVbench be used with a different traffic generator than TRex?
------------------------------------------------------------------
This is possible but requires developing a new python class to manage the new traffic generator interface.

Can I connect Trex directly to my compute node?
-----------------------------------------------
Yes.

Can I drive NFVbench using a REST interface?
--------------------------------------------
NFVbench can run in server mode and accept HTTP requests to run any type of measurement (fixed rate run or NDR_PDR run)
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

Issues with high performances at a high line rate
-------------------------------------------------

Flow statistics and/or latency stream can cause performance issue when testing high line rate.

Flow statistics implies CPU usage to analyse packets and retrieve statistics. CPU can reach 100% usage when high throughput is tested because only one CPU is used for packet reception in TRex.
The ``--no-flow-stats`` option allows you to disable TRex statistics aggregation during the NFVBench test.
This, will permit to save CPU capabilities used for packet reception.

Example of use :

.. code-block:: bash

    nfvbench ``--no-flow-stats``

    2019-10-28 10:26:52,099 INFO End-to-end connectivity established
    2019-10-28 10:26:52,127 INFO Cleared all existing streams
    2019-10-28 10:26:52,129 INFO Traffic flow statistics are disabled.


Latency streams implies also CPU usage to analyse packets and retrieve latency values. CPU can reach 100% usage when high throughput is tested because only one CPU is used for packet reception in TRex.
The ``--no-latency-streams`` option allows you to disable latency streams during the NFVBench test.
This, will permit to save CPU capabilities used for packet reception but no latency information will be return (to be used only if latency value has no meaning for your test).

Example of use :

.. code-block:: bash

    nfvbench ``--no-latency-streams``
    2019-10-28 10:30:03,955 INFO End-to-end connectivity established
    2019-10-28 10:30:03,982 INFO Cleared all existing streams
    2019-10-28 10:30:03,982 INFO Latency streams are disabled


Latency flow statistics implies CPU usage to analyse packets and retrieve statistics. CPU can reach 100% usage when high throughput is tested because only one CPU is used for packet reception in TRex.
The ``--no-latency-stats`` option allows you to disable TRex statistics aggregation for latency packets during the NFVBench test.
This, will permit to save CPU capabilities used for packet reception.

Example of use :

.. code-block:: bash

    nfvbench ``--no-latency-stats``
    2019-10-28 10:28:21,559 INFO Cleared all existing streams
    2019-10-28 10:28:21,567 INFO Latency flow statistics are disabled.
