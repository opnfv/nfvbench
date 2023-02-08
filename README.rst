NFVbench: A Network Performance Benchmarking Tool for NFVi Full Stacks
**********************************************************************

The NFVbench tool provides an automated way to measure the network performance for the most common data plane packet flows
on any NFVi system viewed as a black box (NFVi Full Stack).
An NFVi full stack exposes the following interfaces:
- an OpenStack API for those NFVi platforms based on OpenStack
- an interface to send and receive packets on the data plane (typically through top of rack switches
  while simpler direct wiring to a looping device would also work)

The NFVi full stack does not have to be supported by the OPNFV ecosystem and can be any functional OpenStack system that provides
the above interfaces.
NFVbench can also be used without OpenStack on any networking device that can handle L2 forwarding or L3 routing.

NFVbench can be installed standalone (in the form of a single Docker container) and is fully functional without
the need to install any other OPNFV framework.

It is designed to be easy to install and easy to use by non experts (no need to be an expert in traffic generators and data plane
performance benchmarking).

Online Documentation
--------------------
The latest version of the NFVbench documentation is available online at:

https://docs.anuket.io/projects/nfvbench/en/latest/index.html

Contact Information
-------------------
Inquiries and questions: send an email to anuket-tech-discuss@lists.anuket.io with a Subject line starting with "#nfvbench"

Open issues or submit an issue or enhancement request: https://jira-old.opnfv.org/projects/NFVBENCH/issues (this requires an OPNFV Linux Foundation login).
