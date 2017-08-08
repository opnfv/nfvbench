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

The recursion narrows down the range by half and stops when:
- the range is smaller than the configured load_epsilon value
- or when the search hits 100% or 0% of line rate

