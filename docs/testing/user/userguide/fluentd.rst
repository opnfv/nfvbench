.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

NFVbench Fluentd Integration
============================================

NFVbench has an optional fluentd integration to save logs and results.

Configuring Fluentd to receive NFVbench logs and results
--------------------------------------------------------

The following configurations should be added to Fluentd configuration file to enable logs or results.

To receive logs, and forward to a storage server:

In the example below nfvbench is the tag name for logs (which should be matched with logging_tag
under NFVbench configuration), and storage backend is elasticsearch which is
running at localhost:9200.


.. code-block:: bash
    <match nfvbench.**>
    @type copy
    <store>
        @type elasticsearch
        host localhost
        port 9200
        logstash_format true
        logstash_prefix nfvbench
        utc_index false
        flush_interval 15s
    </store>
    </match>

To receive results, and forward to a storage server:

In the example below resultnfvbench is the tag name for results (which should be matched with result_tag
under NFVbench configuration), and storage backend is elasticsearch which is
running at localhost:9200.

.. code-block:: bash
    <match resultnfvbench.**>
    @type copy
    <store>
        @type elasticsearch
        host localhost
        port 9200
        logstash_format true
        logstash_prefix resultnfvbench
        utc_index false
        flush_interval 15s
    </store>
    </match>

Configuring NFVbench to connect Fluentd
---------------------------------------

To configure NFVbench to connect Fluentd, fill following configuration parameters in the
configuration file

+------------------------------------------------------+------------------------------------------------------+
| Configuration                                        | Description                                          |
+======================================================+======================================================+
| logging_tag                                          | Tag for NFVbench logs, it should be the same tag     |
|                                                      | defined in Fluentd configuration                     |
+------------------------------------------------------+------------------------------------------------------+
| result_tag                                           | Tag for NFVbench results, it should be the same tag  |
|                                                      | defined in Fluentd configuration                     |
+------------------------------------------------------+------------------------------------------------------+
| ip                                                   | ip address of Fluentd server                         |
+------------------------------------------------------+------------------------------------------------------+
| port                                                 | port number of Fluentd serverd                       |
+------------------------------------------------------+------------------------------------------------------+

An example of configuration for Fluentd working at 127.0.0.1:24224 and tags for logging is nfvbench
and result is resultnfvbench

.. code-block:: bash
    fluentd:
        # by default (logging_tag is empty) nfvbench log messages are not sent to fluentd
        # to enable logging to fluents, specify a valid fluentd tag name to be used for the
        # log records
        logging_tag: nfvbench

        # by default (result_tag is empty) nfvbench results are not sent to fluentd
        # to enable sending nfvbench results to fluentd, specify a valid fluentd tag name
        # to be used for the results records, which is different than logging_tag
        result_tag: resultnfvbench

        # IP address of the server, defaults to loopback
        ip: 127.0.0.1

        # port # to use, by default, use the default fluentd forward port
        port: 24224

Example of logs and results
---------------------------

An example of log sent to fluentd:

.. code-block:: bash

    {
      "_index": "nfvbench-2017.10.17",
      "_type": "fluentd",
      "_id": "AV8rhnCjTgGF_dX8DiKK",
      "_version": 1,
      "_score": 3,
      "_source": {
        "loglevel": "INFO",
        "message": "Service chain 'PVP' run completed.",
        "@timestamp": "2017-10-17T18:09:09.516897+0000",
        "runlogdate": "2017-10-17T18:08:51.851253+0000"
      },
      "fields": {
        "@timestamp": [
          1508263749516
        ]
      }
    }

An example of result sent to fluentd:

For each packet size and rate a result record is sent. Users can label those results by passing
--user-label parameter to NFVbench run

.. code-block::bash
    nfvbench --rate 1% --user-label nfvbench-label

Result of this run:

.. code-block:: bash

    {
      "_index": "resultnfvbench-2017.10.17",
      "_type": "fluentd",
      "_id": "AV8rjYlbTgGF_dX8Drl1",
      "_version": 1,
      "_score": null,
      "_source": {
        "compute_nodes": [
          "nova:cork-compute-3.cisco.com"
        ],
        "total_orig_rate_bps": 200000000,
        "@timestamp": "2017-10-17T18:16:43.755240+0000",
        "frame_size": "64",
        "forward_orig_rate_pps": 148809,
        "flow_count": 10000,
        "avg_delay_usec": 6271,
        "total_tx_rate_pps": 283169,
        "total_tx_rate_bps": 190289668,
        "forward_tx_rate_bps": 95143832,
        "reverse_tx_rate_bps": 95145836,
        "forward_tx_rate_pps": 141583,
        "chain_analysis_duration": "60.091",
        "service_chain": "PVP",
        "version": "1.0.10.dev1",
        "runlogdate": "2017-10-17T18:10:12.134260+0000",
        "Encapsulation": "VLAN",
        "user_label": "nfvbench-label",
        "min_delay_usec": 70,
        "profile": "traffic_profile_64B",
        "reverse_rx_rate_pps": 68479,
        "reverse_rx_rate_bps": 46018044,
        "reverse_orig_rate_pps": 148809,
        "total_rx_rate_bps": 92030085,
        "drop_rate_percent": 51.6368455626846,
        "forward_orig_rate_bps": 100000000,
        "bidirectional": true,
        "vSwitch": "OPENVSWITCH",
        "sc_count": 1,
        "total_orig_rate_pps": 297618,
        "type": "single_run",
        "reverse_orig_rate_bps": 100000000,
        "total_rx_rate_pps": 136949,
        "max_delay_usec": 106850,
        "forward_rx_rate_pps": 68470,
        "forward_rx_rate_bps": 46012041,
        "reverse_tx_rate_pps": 141586
      },
      "fields": {
        "@timestamp": [
          1508264203755
        ]
      },
      "sort": [
        1508264203755
      ]
    }