
.. This work is licensed under a Creative Commons Attribution 4.0 International
.. License.
.. http://creativecommons.org/licenses/by/4.0
.. (c) Cisco Systems, Inc

Building containers and VM images
=================================

NFVbench is delivered as Docker container which is built using the Dockerfile under the docker directory.
This container includes the following parts:

- TRex traffic generator
- NFVbench orchestration
- NFVbench test VM (qcow2)

Versioning
----------
These 3 parts are versioned independently and the Dockerfile will determine the combination of versions that
are packaged in the container for the version associated to the Dockerfile.

The NFVbench version is controlled by the git tag that conforms to the semver version (e.g. "3.3.0").
This tag controls the version of the Dockerfile used for building the container.

The TRex version is controlled by the TREX_VER variable in Dockerfile (e.g. ENV TREX_VER "v2.56").
TRex is installed in container from https://github.com/cisco-system-traffic-generator/trex-core/releases

The Test VM version is controlled by the VM_IMAGE_VER variable in Dockerfile (e.g. ENV VM_IMAGE_VER "0.8").
The VM is extracted from google storage (http://artifacts.opnfv.org)

Updating the VM image
---------------------

When the VM image is changed, its version must be increased in order to distinguish from previous image versions.
The version strings to change are located in 2 files:

- docker/Dockerfile
- nfvbench/nfvbenchvm/dib/build-image.sh

Building and uploading the VM image
-----------------------------------
The VM image is built on gerrit verify when the image is not present in google storage.
It is not uploaded yet on google storage.

The build + upload of the new VM image is done after the review is merged.

For details on how this is done, refer to ./jjb/nfvbench/nfvbench.yaml in the opnfv releng repository.

Building a new NFVbench container image
---------------------------------------
A new container image can be built and published to Dockerhub by CI/CD by applying a new semver tag to the
nfvbench repository.


Workflow summary
----------------

NFVbench code has changed:

- commit with gerrit
- apply a new semver tag to trigger the container image build/publication

VM code has changed:

- update VM version in the 2 locations
- commit VM changes with gerrit to trigger VM build and publication to google storage
- IMPORTANT! wait for the VM image to be pushed to google storage before going to the next step
  (otherwise the container build will fail as it will not find the VM image)
- apply a new semver tag to trigger the container image build/publication

To increase the TRex version:

- change the Trex version in Dockerfile
- commit with gerrit
- apply a new semver tag to trigger the container image build/publication
