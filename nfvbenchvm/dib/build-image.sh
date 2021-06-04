#!/bin/bash
#
# A shell script to build the VPP VM image or NFVbench+TRex VM image using diskinage-builder
#
# The following packages must be installed prior to using this script:
# sudo apt-get -y install python-virtualenv qemu-utils kpartx

usage() {
    echo "Usage: $0 [-l] [-g] [-v]"
    echo "   -l    build NFVbench loop VM image"
    echo "   -g    build NFVbench generator image"
    echo "   -v    verify only (build but do not push to google storage)"
    exit 1
}

verify_only=0
generator_only=0
loopvm_only=0
__prefix__=""
# ----------------------------------------------------------------------------
# Parse command line options and configure the script
# ----------------------------------------------------------------------------

while getopts ":hglv" opt; do
    case $opt in
        h)
            usage
            exit 0
            ;;
        g)
            generator_only=1
            ;;
        l)
            loopvm_only=1
            ;;
        v)
            verify_only=1
            ;;
        ?)
            usage
            exit 1
            ;;
    esac
done

set -e

# Artifact URL
gs_url=artifacts.opnfv.org/nfvbench/images

# image version number
__version__=0.15
loopvm_image_name=nfvbenchvm_centos-$__version__
generator_image_name=nfvbenchvm_centos-generator-$__version__

function build_image {
    # if image exists skip building
    echo "Checking if image exists in google storage..."
    if  command -v gsutil >/dev/null; then
       if gsutil -q stat gs://$gs_url/$1.qcow2; then
           echo "Image already exists at http://$gs_url/$1.qcow2"
           echo "Build is skipped"
           exit 0
       fi
       echo "Image does not exist in google storage, starting build..."
       echo
    else
       echo "Cannot check image availability in OPNFV artifact repository (gsutil not available)"
    fi

    # check if image is already built locally
    if [ -f $1.qcow2 ]; then
        echo "Image $1.qcow2 already exists locally"
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
        # only for loop vm image
        if [ $1 = $loopvm_image_name ]; then
           export DIB_USE_ELREPO_KERNEL=True
           export DIB_DEV_IMAGE=loopvm
        else
           export DIB_USE_ELREPO_KERNEL=False
           export DIB_DEV_IMAGE=generator
           # get current git branch to build image with current code
           export GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
           # retrieve TREX_VER from Dockerfile
           export TREX_VER=$(awk '/ENV TREX_VER/ {print $3}' ../../docker/Dockerfile | sed 's/"//g' | sed 's/\r//g')
        fi

        echo "Building $1.qcow2..."
        time disk-image-create -o $1 centos7 nfvbenchvm
    fi

    ls -l $1.qcow2

    if [ $verify_only -eq 1 ]; then
        echo "Image verification SUCCESS"
        echo "NO upload to google storage (-v)"
    else
        if command -v gsutil >/dev/null; then
            echo "Uploading $1.qcow2..."
            gsutil cp $1.qcow2 gs://$gs_url/$1.qcow2
            echo "You can access to image at http://$gs_url/$1.qcow2"
        else
            echo "Cannot upload new image to the OPNFV artifact repository (gsutil not available)"
            exit 1
        fi
    fi
}


if [ ! $generator_only -eq 1 ] && [ ! $loopvm_only -eq 1 ]; then
   echo "Build loop VM image"
   build_image $loopvm_image_name
   echo "Build generator image"
   build_image $generator_image_name
else
    if [ $loopvm_only -eq 1 ]; then
       echo "Build loop VM image"
       build_image $loopvm_image_name
    fi
    if [ $generator_only -eq 1 ]; then
       echo "Build generator image"
       build_image $generator_image_name
    fi
fi