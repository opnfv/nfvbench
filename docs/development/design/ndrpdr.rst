.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

NDR/PDR Binary Search
=====================

The NDR/PDR binary search algorithm used by NFVbench is based on the algorithm used by the
FD.io CSIT project, with some additional optimizations.

Algorithm Outline
-----------------

The ServiceChain class (nfvbench/service_chain.py) is responsible for calculating the NDR/PDR
or all frame sizes requested in the configuration.
Calculation for 1 frame size is delegated to the TrafficClient class (nfvbench/traffic_client.py)

Call chain for calculating the NDR-PDR for a list of frame sizes:

- ServiceChain.run()
    - ServiceChain._get_chain_results()
        - for every frame size:
            - ServiceChain.__get_result_per_frame_size()
                - TrafficClient.get_ndr_pdr()
                    - TrafficClient.__range_search() recursive binary search

The search range is delimited by a left and right rate (expressed as a % of line rate per direction).
The search always start at line rate per port, e.g. in the case of 2x10Gbps, the first iteration
will send 10Gbps of traffic on each port.

The load_epsilon configuration parameter defines the accuracy of the result as a % of line rate.
The default value of 0.1 indicates for example that the measured NDR and PDR are within 0.1% of line rate of the
actual NDR/PDR (e.g. 0.1% of 10Gbps is 10Mbps). It also determines how small the search range must be in the binary search.
Smaller values of load_epsilon will result in more iterations and will take more time but may not
always be beneficial if the absolute value falls below the precision level of the measurement.
For example a value of 0.01% would translate to an absolute value of 1Mbps (for a 10Gbps port) or
around 10kpps (at 64 byte size) which might be too fine grain.

The recursion narrows down the range by half and stops when:

- the range is smaller than the configured load_epsilon value
- or when the search hits 100% or 0% of line rate

Optimization
------------

Binary search algorithms assume that the drop rate curve is monotonically increasing with the Tx rate.
To save time, the algorithm used by NFVbench is capable of calculating the optimal Tx rate for an
arbitrary list of target maximum drop rates in one pass instead of the usual 1 pass per target maximum drop rate.
This saves time linearly to the number target drop rates.
For example, a typical NDR/PDR search will have 2 target maximum drop rates:

- NDR = 0.001%
- PDR = 0.1%

The binary search will then start with a sorted list of 2 target drop rates: [0.1, 0.001].
The first part of the binary search will then focus on finding the optimal rate for the first target
drop rate (0.1%). When found, the current target drop rate is removed from the list and
iteration continues with the next target drop rate in the list but this time
starting from the upper/lower range of the previous target drop rate, which saves significant time.
The binary search continues until the target maximum drop rate list is empty.

Results Granularity
-------------------
The binary search results contain per direction stats (forward and reverse).
In the case of multi-chaining, results contain per chain stats.
The current code only reports aggregated stats (forward + reverse for all chains) but could be enhanced
to report per chain stats.


CPU Limitations
---------------
One particularity of using a software traffic generator is that the requested Tx rate may not always be met due to
resource limitations (e.g. CPU is not fast enough to generate a very high load). The algorithm should take this into
consideration:

- always monitor the actual Tx rate achieved as reported back by the traffic generator
- actual Tx rate is always <= requested Tx rate
- the measured drop rate should always be relative to the actual Tx rate
- if the actual Tx rate is < requested Tx rate and the measured drop rate is already within threshold
  (<NDR/PDR threshold) then the binary search must stop with proper warning because the actual NDR/PDR
  might probably be higher than the reported values
