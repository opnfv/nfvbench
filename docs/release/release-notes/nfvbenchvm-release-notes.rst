.. This work is licensed under a Creative Commons Attribution 4.0 International License.
.. http://creativecommons.org/licenses/by/4.0


NFVbench Loop VM Image Release Notes
++++++++++++++++++++++++++++++++++++

As explained in :ref:`nfvbench-artefact-versioning`, NFVbench loop VM image has
its own version numbering scheme.  Starting from version 0.11, this page
summarizes the news of each release.


Release 0.16 (2022-11-15)
=========================

Fixes:

- Increase wait for VPP service from 10 to 30 seconds (10s is not enough on some
  setups) and poll every second instead of sleeping 10s.

- Set the MTU of the management interface to 1500 by default (to reduce the risk
  to get an unmanageable VM).  A different value can be set using the
  ``INTF_MGMT_MTU`` variable in ``/etc/nfvbenchvm.conf``.

Changes for developers:

- Add 2 debug features to ``build-image.sh``:

  - The new option ``-t`` (enable debug traces) allows to show in the build log
    the commands run in the shell scripts, including the commands defined in the
    disk image builder elements.

  - The new option ``-d`` (debug) instructs ``disk-image-create`` to drop the
    developer in a shell inside the chroot in case an error occurs.  This makes
    troubleshooting of the image possible (inspect files, run commands, ...)

- Abort build on error: make sure a VM image build fails if any step fails.
  Else we can end up with a bad image not containing all that we want, and we
  discover this later at run time.

- Fix build with diskimage_builder (dib) 3.16.0.

- Switch VPP package repository to packagecloud.io instead of nexus.fd.io.  This
  fixes intermittent access issues with nexus.fd.io and this will make it
  possible to get vpp releases higher than 19.08.

- Separate loop VM and generator VM version numbers (a first step towards using
  nfvbench version number for the generator VM).


Release 0.15 (2021-06-04)
=========================

- NFVBENCH-211 Fix VPP driver for loop VM (switch UIO driver for VPP forwarder:
  use ``uio_pci_generic`` instead of ``igb_uio``).


Release 0.14 (2021-05-21)
=========================

- NFVBENCH-209 Fix NFVbench loopvm build failed on testpmd step (includes switch
  UIO driver for testmpd forwarder: use ``uio_pci_generic`` instead of
  ``igb_uio``).


Release 0.13 (2021-04-28)
=========================

- NFVBENCH-196: New NFVbench image for generator part (nfvbench and TRex codes inside VM)
- Change Linux kernel boot-time configuration (kernel CLI parameters):

  - Extend CPU isolation (``isolcpus=1-7`` instead of ``isolcpus=1``)
  - Increase the number of 1GB huge pages (``hugepages=4`` instead of ``hugepages=2``)
  - Enable IOMMU (``intel_iommu=on iommu=pt``)

- Load the ``vfio-pci`` kernel module with the ``enable_unsafe_noiommu_mode=1`` option.


Release 0.12 (2020-01-23)
=========================

- NFVBENCH-157 Add possibility to not use the ARP static configuration for VPP loop VM


Release 0.11 (2019-11-26)
=========================

- NFVBENCH-156 Add management interface and ssh config in NFVBench image


Earlier releases
================

See NFVbench commit history.
