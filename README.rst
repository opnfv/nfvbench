NFVbench: A Network Performance Benchmarking Tool for NFVi Full Stacks
**********************************************************************

The NFVbench tool provides an automated way to measure the network performance for the most common data plane packet flows on any OpenStack based NFVi system viewed as a black box (NFVi Full Stack).
An NFVi full stack exposes the following interfaces:
- an OpenStack API
- an interface to send and receive packets on the data plane (typically through top of rack switches)

The NFVi full stack does not have to be supported by the OPNFV ecosystem and can be any functional OpenStack system that provides the aboce interfaces. NFVbench can be installed standalone (in the form of a single Docker container) and is fully functional without the need to install any other OPNFV framework.

It is designed to be easy to install and easy to use by non experts (no need to be an expert in traffic generators and data plane performance testing).






