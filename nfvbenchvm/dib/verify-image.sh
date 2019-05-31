#!/bin/bash
#
# A shell script to verify that a VM image is present in google storage
# If not present in google storage, verify it is present locally
# If not present locally, build it but do not uplaod to google storage

bash build-image.sh -v
