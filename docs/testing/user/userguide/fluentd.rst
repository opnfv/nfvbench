.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. SPDX-License-Identifier: CC-BY-4.0
.. (c) Cisco Systems, Inc

NFVbench Fluentd Integration
============================================

NFVbench has an optional fluentd integration to save logs and results.

Configuring Fluentd to receive NFVbench logs and results
--------------------------------------------------------

The following configurations should be added to Fluentd configuration file to enable logs or results.

To receive logs, where TAG is the user defined logging tag (logging_tag value in configuration file)
for NFVbench, and suggested value for TAG is nfvbench.

.. code-block:: bash
    <match TAG.**>
    @type copy
    @include out-syslog.conf
    <store>
        @type elasticsearch
        host localhost
        port 9200
        logstash_format true
        logstash_prefix TAG
        utc_index false
        flush_interval 15s
    </store>
    </match>

To receive results of an NFVbench run, where TAG is the user defined result tag (result_tag value
in configuration file) for NFVbench, and suggested value for TAG is resultnfvbench

.. code-block:: bash
    <match TAG.**>
    @type copy
    @include out-syslog.conf
    <store>
        @type elasticsearch
        host localhost
        port 9200
        logstash_format true
        logstash_prefix TAG
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
