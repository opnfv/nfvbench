.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

Example of Results
******************
Example run for fixed rate

.. code-block:: bash
    nfvbench -c /nfvbench/nfvbenchconfig.json --rate 1%

.. code-block:: bash
    ========== NFVBench Summary ==========
    Date: 2017-09-21 23:57:44
    NFVBench version 1.0.9
    Openstack Neutron:
      vSwitch: BASIC
      Encapsulation: BASIC
    Benchmarks:
    > Networks:
      > Components:
        > TOR:
            Type: None
        > Traffic Generator:
            Profile: trex-local
            Tool: TRex
        > Versions:
          > TOR:
          > Traffic Generator:
              build_date: Aug 30 2017
              version: v2.29
              built_by: hhaim
              build_time: 16:43:55
      > Service chain:
        > PVP:
          > Traffic:
              Profile: traffic_profile_64B
              Bidirectional: True
              Flow count: 10000
              Service chains count: 1
              Compute nodes: []

                Run Summary:

                  +-----------------+-------------+----------------------+----------------------+----------------------+
                  |   L2 Frame Size |  Drop Rate  |   Avg Latency (usec) |   Min Latency (usec) |   Max Latency (usec) |
                  +=================+=============+======================+======================+======================+
                  |              64 |   0.0000%   |                   53 |                   20 |                  211 |
                  +-----------------+-------------+----------------------+----------------------+----------------------+


                L2 frame size: 64
                Chain analysis duration: 60.076 seconds

                Run Config:

                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |  Direction  |  Requested TX Rate (bps)  |  Actual TX Rate (bps)  |  RX Rate (bps)  |  Requested TX Rate (pps)  |  Actual TX Rate (pps)  |  RX Rate (pps)  |
                  +=============+===========================+========================+=================+===========================+========================+=================+
                  |   Forward   |       100.0000 Mbps       |      95.4546 Mbps      |  95.4546 Mbps   |        148,809 pps        |      142,045 pps       |   142,045 pps   |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |   Reverse   |       100.0000 Mbps       |      95.4546 Mbps      |  95.4546 Mbps   |        148,809 pps        |      142,045 pps       |   142,045 pps   |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+
                  |    Total    |       200.0000 Mbps       |     190.9091 Mbps      |  190.9091 Mbps  |        297,618 pps        |      284,090 pps       |   284,090 pps   |
                  +-------------+---------------------------+------------------------+-----------------+---------------------------+------------------------+-----------------+

                Chain Analysis:

                  +-------------------+----------+-----------------+---------------+---------------+-----------------+---------------+---------------+
                  |     Interface     |  Device  |  Packets (fwd)  |   Drops (fwd) |  Drop% (fwd)  |  Packets (rev)  |   Drops (rev) |  Drop% (rev)  |
                  +===================+==========+=================+===============+===============+=================+===============+===============+
                  | traffic-generator |   trex   |    8,522,729    |               |               |    8,522,729    |             0 |    0.0000%    |
                  +-------------------+----------+-----------------+---------------+---------------+-----------------+---------------+---------------+
                  | traffic-generator |   trex   |    8,522,729    |             0 |    0.0000%    |    8,522,729    |               |               |
                  +-------------------+----------+-----------------+---------------+---------------+-----------------+---------------+---------------+

Example run for NDR/PDR with package size 1518B

.. code-block:: bash
    nfvbench -c /nfvbench/nfvbenchconfig.json --fs 1518

.. code-block:: bash
    ========== NFVBench Summary ==========
    Date: 2017-09-22 00:02:07
    NFVBench version 1.0.9
    Openstack Neutron:
      vSwitch: BASIC
      Encapsulation: BASIC
    Benchmarks:
    > Networks:
      > Components:
        > TOR:
            Type: None
        > Traffic Generator:
            Profile: trex-local
            Tool: TRex
        > Versions:
          > TOR:
          > Traffic Generator:
              build_date: Aug 30 2017
              version: v2.29
              built_by: hhaim
              build_time: 16:43:55
      > Measurement Parameters:
          NDR: 0.001
          PDR: 0.1
      > Service chain:
        > PVP:
          > Traffic:
              Profile: custom_traffic_profile
              Bidirectional: True
              Flow count: 10000
              Service chains count: 1
              Compute nodes: []

                Run Summary:

                  +-----+-----------------+------------------+------------------+-----------------+----------------------+----------------------+----------------------+
                  |  -  |   L2 Frame Size |  Rate (fwd+rev)  |  Rate (fwd+rev)  |  Avg Drop Rate  |   Avg Latency (usec) |   Min Latency (usec) |  Max Latency (usec)  |
                  +=====+=================+==================+==================+=================+======================+======================+======================+
                  | NDR |            1518 |   19.9805 Gbps   |  1,623,900 pps   |     0.0001%     |                  342 |                   30 |         704          |
                  +-----+-----------------+------------------+------------------+-----------------+----------------------+----------------------+----------------------+
                  | PDR |            1518 |   20.0000 Gbps   |  1,625,486 pps   |     0.0022%     |                  469 |                   40 |        1,266         |
                  +-----+-----------------+------------------+------------------+-----------------+----------------------+----------------------+----------------------+


                L2 frame size: 1518
                Chain analysis duration: 660.442 seconds
                NDR search duration: 660 seconds
                PDR search duration: 0 seconds
