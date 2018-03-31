.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

RELEASE NOTES
+++++++++++++

OPNFV Fraser Release
====================

Over 30 Jira tickets have been addressed in this release (Jira NFVBENCH-55 to NFVBENCH-78)

The Fraser release adds the following new features:

- support for benchmarking non-OpenStack environments (with external setup and no OpenStack openrc file)
- PVVP packet path with SRIOV at the edge and vswitch between VMs
- support logging events and results through fluentd

Enhancements and main bug fixes:

- end to end connectivity for larger chain count is now much more accurate for large chain count - avoiding excessive drops
- use newer version of TRex (2.32)
- use newer version of testpmd DPDK
- NDR/PDR uses actual TX rate to calculate drops - resulting in more accurate results
- add pylint to unit testing
- add self sufficient and standalone unit testing (without actual testbed)


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







