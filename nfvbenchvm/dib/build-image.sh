#!/bin/bash
#
# A shell script to build the VPP VM image using diskinage-builder
#
# The following packages must be installed prior to using this script:
# sudo apt-get -y install python-virtualenv qemu-utils kpartx

usage() {
    echo "Usage: $0 [-v]"
    echo "   -v    verify only (build but do not push to google storage)"
    exit 1
}

# Takes only 1 optional argument
if [ $# -gt 1 ]; then
   usage
fi
verify_only=0

if [ $# -eq 1 ]; then
   if [ $1 = "-v" ]; then
        verify_only=1
    else
        usage
    fi
fi
set -e

# Artifact URL
gs_url=artifacts.opnfv.org/nfvbench/images

# image version number
__version__=0.11
image_name=nfvbenchvm_centos-$__version__

# if image exists skip building
echo "Checking if image exists in google storage..."
if  command -v gsutil >/dev/null; then
    if gsutil -q stat gs://$gs_url/$image_name.qcow2; then
        echo "Image already exists at http://$gs_url/$image_name.qcow2"
        echo "Build is skipped"
        exit 0
    fi
    echo "Image does not exist in google storage, starting build..."
    echo
else
    echo "Cannot check image availability in OPNFV artifact repository (gsutil not available)"
fi

# check if image is already built locally
if [ -f $image_name.qcow2 ]; then
    echo "Image $image_name.qcow2 already exists locally"
else

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
fi

ls -l $image_name.qcow2


if [ $verify_only -eq 1 ]; then
    echo "Image verification SUCCESS"
    echo "NO upload to google storage (-v)"
else
    if command -v gsutil >/dev/null; then
        echo "Uploading $image_name.qcow2..."
        gsutil cp $image_name.qcow2 gs://$gs_url/$image_name.qcow2
        echo "You can access to image at http://$gs_url/$image_name.qcow2"
    else
        echo "Cannot upload new image to the OPNFV artifact repository (gsutil not available)"
        exit 1
    fi
fi
