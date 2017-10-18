.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

.. contents::
   :depth: 3
   :local:

Introduction
----------------
NFVbench is a python application that is designed to run in a compact and portable format inside a container and on production pods.
As such it only uses open sourec software with minimal hardware requirements (just a NIC card that is DPDK compatible).
Traffic generation is handled by TRex on 2 physical ports (2x10G or higher) forming traffic loops up to VNF level and following
a path that is common to all NFV applications: external source to top of rack switch(es) to conpute node(s) to vswitch (if applicable)
to VNF(s) and back.

Configuration of benchmarks is through a hierarchy of yaml configuraton files and command line arguments.

Results are available in different formats:
- text output with tabular results
- json result in file or in REST reply (most detailed)

Logging is available in a log file.

Benchmark results and logs can be optionally sent to one or more remote fluentd aggeregators using json format.
