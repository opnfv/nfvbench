.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

NDR/PDR Binary Search
=====================

Algorithm Outline
-----------------

The ServiceChain class is responsible for calculating the NDR/PDR for all frame sizes requested in the configuration.
Calculation for 1 frame size is delegated to the TrafficClient class.

Call chain for calculating the NDR-PDR for a list of frame sizes:

- ServiceChain.run()
    - ServiceChain._get_chain_results()
        - for every frame size:
            - ServiceChain.__get_result_per_frame_size()
                - TrafficClient.get_ndr_pdr()
                    - TrafficClient.__range_search() recursive binary search

The search range is delimited by a left and right rate (expressed as a % of line rate per direction).

The load_epsilon configuration parameter defines the accuracy of the result as a % of line rate.
The default value of 0.1 indicates for example that the measured NDR and PDR are within 0.1% of line rate of the
actual NDR/PDR (e.g. 0.1% of 10Gbps is 10Mbps). It also determines how small the search range must be in the binary search.

The recursion narrows down the range by half and stops when:

- the range is smaller than the configured load_epsilon value
- or when the search hits 100% or 0% of line rate

One particularity of using a software traffic generator is that the requested Tx rate may not always be met due to
resource limitations (e.g. CPU is not fast enough to generate a very high load). The algorithm should take this into
consideration:

- always monitor the actual Tx rate achieved
- actual Tx rate is always <= requested Tx rate
- the measured drop rate should always be relative to the actual Tx rate
- if the actual Tx rate is < requested Tx rate and the measured drop rate is already within threshold (<NDR/PDR threshold) then the binary search must stop with proper warning


