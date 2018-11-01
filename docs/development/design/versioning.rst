
.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

Versioning
==========

NFVbench uses semver compatible git tags such as "1.0.0". These tags are also called project tags and applied at important commits on the master branch exclusively.
Rules for the version numbers follow the semver 2.0 specification (https://semver.org).
These git tags are applied indepently of the OPNFV release tags which are applied only on the stable release branches (e.g. "opnfv-5.0.0").

In general it is recommeneded to always have a project git version tag associated to any OPNFV release tag content obtained from a sync from master.

NFVbench Docker containers will be versioned based on the OPNF release tags or based on NFVbench project tags.
