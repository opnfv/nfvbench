.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

Traffic Description
===================

The general packet path model followed by NFVbench requires injecting traffic into an arbitrary
number of service chains, where each service chain is identified by 2 edge networks (left and right).
In the current multi-chaining model:

- all service chains can either share the same left and right edge networks or can have their own edge networks
- each port associated to the traffic generator is dedicated to send traffic to one side of the edge networks

If VLAN encapsulation is used, all traffic sent to a port will either have the same VLAN id (shared networks) or distinct VLAN ids (dedicated egde networks)

Basic Packet Description
------------------------

The code to create the UDP packet is located in TRex.create_pkt() (nfvbench/traffic_gen/trex.py).

NFVbench always generates UDP packets (even when doing L2 forwarding).
The final size of the frame containing each UDP packet will be based on the requested L2 frame size.
When taking into account the minimum payload size requirements from the traffic generator for
the latency streams, the minimum L2 frame size is 64 byte.

Flows Specification
-------------------

Mac Addresses
.............
The source MAC address is always the local port MAC address (for each port).
The destination MAC address is based on the configuration and can be:

- the traffic generator peer port MAC address in the case of L2 loopback at the switch level
  or when using a loopback cable
- the dest MAC as specified by the configuration file (EXT chain no ARP)
- the dest MAC as discovered by ARP (EXT chain)
- the router MAC as discovered from Neutron API (PVPL3 chain)
- the VM MAC as dicovered from Neutron API (PVP, PVVP chains)

NFVbench does not currently range on the MAC addresses.

IP addresses
............
The source IP address is fixed per chain.
The destination IP address is variable within a distinct range per chain.

UDP ports
.........
The source and destination ports are fixed for all packets and can be set in the configuratoon
file (default is 53).

Payload User Data
.................
The length of the user data is based on the requested L2 frame size and takes into account the
size of the L2 header - including the VLAN tag if applicable.


IMIX Support
------------
In the case of IMIX, each direction is made of 4 streams:

- 1 latency stream
- 1 stream for each IMIX frame size

The IMIX ratio is encoded into the number of consecutive packets sent by each stream in turn.

Service Chains and Streams
--------------------------
A stream identifies one "stream" of packets with same characteristics such as rate and destination address.
NFVbench will create 2 streams per service chain per direction:

- 1 latency stream set to 1000pps
- 1 main traffic stream set to the requested Tx rate less the latency stream rate (1000pps)

For example, a benchmark with 1 chain (fixed rate) will result in a total of 4 streams.
A benchmark with 20 chains will results in a total of 80 streams (fixed rate, it is more with IMIX).

The overall flows are split equally between the number of chains by using the appropriate destination
MAC address.

For example, in the case of 10 chains, 1M flows and fixed rate, there will be a total of 40 streams.
Each of the 20 non-latency stream will generate packets corresponding to 50,000 flows (unique src/dest address tuples).
