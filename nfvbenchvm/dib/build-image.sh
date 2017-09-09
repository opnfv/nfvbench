#!/bin/bash
#
# A shell script to build the VPP VM image using diskinage-builder
#
# The following packages must be installed prior to using this script:
# sudo apt-get -y install python-virtualenv qemu-utils kpartx

set -e

# Artifact URL
gs_url=artifacts.opnfv.org/nfvbench/images

# image version number
__version__=0.4
image_name=nfvbenchvm_centos-$__version__

# if image exists skip building
if  gsutil -q stat gs://$gs_url/$image_name.qcow2; then
	echo "Image already exists at http://$gs_url/$image_name.qcow2"
	exit 0
fi

# install diskimage-builder
if [ -d dib-venv ]; then
    . dib-venv/bin/activate
else
    virtualenv dib-venv
    . dib-venv/bin/activate
    pip install diskimage-builder
fi

# Add nfvbenchvm_centos elements directory to the DIB elements path
export ELEMENTS_PATH=`pwd`/elements

# canned user/password for direct login
export DIB_DEV_USER_USERNAME=nfvbench
export DIB_DEV_USER_PASSWORD=nfvbench
export DIB_DEV_USER_PWDLESS_SUDO=Y

# Set the data sources to have ConfigDrive only
export DIB_CLOUD_INIT_DATASOURCES="ConfigDrive"

# Configure VPP REPO
export DIB_YUM_REPO_CONF=$ELEMENTS_PATH/nfvbenchvm/fdio-release.repo

# Use ELRepo to have latest kernel
export DIB_USE_ELREPO_KERNEL=True

echo "Building $image_name.qcow2..."
time disk-image-create -o $image_name centos7 nfvbenchvm
ls -l $image_name.qcow2

echo "Uploading $image_name.qcow2..."
gsutil cp $image_name.qcow2 gs://$gs_url/$image_name.qcow2
echo "You can access to image at http://$gs_url/$image_name.qcow2"
