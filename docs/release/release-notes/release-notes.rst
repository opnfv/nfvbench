.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

OPNFV Euphrates Release
=======================

This is the introductory release for NFVbench. In this release, NFVbench provides the following features/capabilities:

- standalone installation with a single Docker container integrating the open source TRex traffic generator
- can measure data plane performance for any NFVi full stack
- can setup automatically service chains with the following packet paths:
    - PVP (physical-VM-physical)
    - PVVP (physical-VM-VM-physical) intra-node and inter-node
- can setup multiple service chains
    - N * PVP
    - N * PVVP
- supports any external service chain (pre-set externally) that can do basic IPv4 routing
- can measure
    - drop rate and latency for any given fixed rate
    - NDR (No Drop Rate) and PDR (Partial Drop Rate) with configurable drop rates
- traffic specification
    - any fixed frame size or IMIX
    - uni or bidirectional traffic
    - any number of flows
    - vlan tagging can be enabled or disabled
- user interface:
    - CLI
    - REST+socketIO
- fully configurable runs with yaml-JSON configuration
- detailed results in JSON format
- summary tabular results
- can send logs and results to one or more fluentd aggregators (per configuration)


Euphrates 5.1.0 Release
-----------------------
Pick NFVBENCH-45 (fix typo in calculation of IMIX average size)




