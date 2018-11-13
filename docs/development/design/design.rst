

.. contents::
   :depth: 3
   :local:

.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc


Introduction
------------

NFVbench can be decomposed in the following components:
- Configuration
- Orchestration:

  - Staging
  - Traffic generation
  - Results analysis

Configuration
-------------
This component is in charge of getting the configuration options from the user and consolidate them with
the default configuration into a running configuration.

default configuration + user configuration options = running configuration

User configuration can come from:
- CLI configuration shortcut arguments (e.g --frame-size)
- CLI configuration file (--config [file])
- CLI configuration string (--config [string])
- REST request body
- custom platform pluging

The precedence order for configuration is (from highest precedence to lowest precedence)
- CLI configuration or REST configuration
- custom platform plugin
- default configuration

The custom platform plugin is an optional python class that can be used to override default configuration options
with default platform options which can be either hardcoded or calculated at runtime from platform specific sources
(such as platform deployment configuration files).
A custom platform plugin class is a child of the parent class nfvbench.config_plugin.ConfigPlugin.

Orchestration
-------------
Once the configuration is settled, benchmark orchestration is managed by the ChainRunner class (nfvbench.chain_runner.ChainRunner).
The chain runner will take care of orchestrating the staging, traffic generation and results analysis.


Staging
-------
The staging component is in charge of staging the OpenStack resources that are used for the requested packet path.
For example, for a PVP packet path, this module will create 2 Neutron networks and one VM instance connected to these 2 networks.
Multi-chaining and VM placement is also handled by this module.

Main class: nfvbench.chaining.ChainManager

Traffic Generation
------------------
The traffic generation component is in charge of contrilling the TRex traffic generator using its python API.
It includes tasks such as:
- traffic check end to end to make sure the packet path is clear in both directions before starting a benchmark
- programming the TRex traffic flows based on requested parameters
- fixed rate control
- NDR/PDR binary search

Main class: nfvbench.traffic_client.TrafficClient


Traffic Generator Results Analysis
----------------------------------
At the end of a traffic generation session, this component collects the results from TRex and packages them in a format that
is suitable for the various output formats (JSON, REST, file, fluentd).
In the case of multi-chaining, it handles aggregation of results across chains.

Main class: nfvbench.stats_manager.StatsManager
