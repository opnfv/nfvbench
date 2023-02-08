.. Copyright 2016 - 2023, Cisco Systems, Inc. and the NFVbench project contributors
.. SPDX-License-Identifier: CC-BY-4.0

==========================
MPLS encapsulation feature
==========================

This feature allows to generate packets with standard MPLS L2VPN double stack MPLS labels, where the outer label is transport and the inner label is VPN.
The top layer of a packets encapsulated inside MPLS L2VPN seems to be an Ethernet layer with the rest of the IP stack inside.
Please refer to RFC-3031 for more details.
The whole MPLS packet structure looks like the following:

###[ Ethernet ]###
  dst       = ['00:8a:96:bb:14:28']
  src       = 3c:fd:fe:a3:48:7c
  type      = 0x8847
###[ MPLS ]### <-------------- Outer Label
     label     = 16303
     cos       = 1
     s         = 0
     ttl       = 255
###[ MPLS ]### <-------------- Inner Label
        label     = 5010
        cos       = 1
        s         = 1
        ttl       = 255
###[ Ethernet ]###
           dst       = fa:16:3e:bd:02:b5
           src       = 3c:fd:fe:a3:48:7c
           type      = 0x800
###[ IP ]###
              version   = 4
              ihl       = None
              tos       = 0x0
              len       = None
              id        = 1
              flags     =
              frag      = 0
              ttl       = 64
              proto     = udp
              chksum    = None
              src       = 16.0.0.1
              dst       = 48.0.0.1
              \options   \
###[ UDP ]###
                 sport     = 53
                 dport     = 53
                 len       = None
                 chksum    = None

Example: nfvbench generates mpls traffic port A ----> port B. This example assumes openstack is at the other end of the mpls tunnels.
Packets generated and sent to port B are delivered to the MPLS domain infrastructure which will transport that packet to the other end
of the MPLS transport tunnel using the outer label. At that point, the outer label is decapsulated and the inner label is used to
select the destination openstack network. After decapsulation of the inner label, the resulting L2 frame is then forwarded to the
destination VM corresponding to the destination MAC. When the VM receives the packet, it is sent back to far end port of the traffic
generator (port B) using either L2 forwarding or L3 routing though the peer virtual interface. The return packet is then encapsulated
with the inner label first then outer label to reach nfvbench on port B.

Only 2 MPLS labels stack is supported. If more than two labels stack is required then these operations should be handled by MPLS transport
domain where nfvbench is attached next-hop mpls router and rest of the mpls domain should be configured accordingly to be able
pop/swap/push labels and deliver packet to the proper destination based on an initial transport label injected by nfvbench, VPN label
should stay unchanged until its delivered to PE (compute node).
Set nfvbench 'mpls' parameter to 'true' to enable MPLS encapsulation.
When this option is enabled internal networks 'network type' parameter value should be 'mpls'
MPLS and VxLAN encapsulations are mutual exclusive features if 'mpls' is 'true' then 'vxlan' should be set to 'false' and vise versa.
no_flow_stats, no_latency_stats, no_latency_streams parameters should be set to 'true' because these features are not supported at the moment.
In future when these features will be supported they will require special NIC hardware.

Example of 1-chain MPLS configuration:
 internal_networks:
    left:
        network_type: mpls
        segmentation_id: 5010
        mpls_transport_labels: 16303
        physical_network: phys_sriov0
    right:
        network_type: mpls
        segmentation_id: 5011
        mpls_transport_labels: 16303
        physical_network: phys_sriov1

Example of 2-chain MPLS configuration:
 internal_networks:
    left:
        network_type: mpls
        segmentation_id: [5010, 5020]
        mpls_transport_labels: [16303, 16304]
        physical_network: phys_sriov0
    right:
        network_type: mpls
        segmentation_id: [5011, 5021]
        mpls_transport_labels: [16303, 16304]
        physical_network: phys_sriov1

Example of how to run:
nfvbench --rate 50000pps --duration 30 --mpls
