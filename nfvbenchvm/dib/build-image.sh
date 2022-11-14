#!/bin/bash
#
# A shell script to build the VPP VM image or NFVbench+TRex VM image using diskinage-builder
#
# The following packages must be installed prior to using this script:
# Ubuntu: sudo apt-get -y install python3 python3-venv qemu-utils kpartx
# CentOS: sudo yum install -y python3 qemu-img kpartx

# Stop on error (see https://wizardzines.com/comics/bash-errors/)
set -euo pipefail

DEBUG=no
verify_only=0
build_generator=0
build_loopvm=0
__prefix__=""

# Artifact URL
gs_url=artifacts.opnfv.org/nfvbench/images

# image version number
__loopvm_version__=0.16
__generator_version__=0.15
loopvm_image_name=nfvbenchvm_centos-$__loopvm_version__
generator_image_name=nfvbenchvm_centos-generator-$__generator_version__

# Default values for nfvbenchvm dib element variables
export DIB_NFVBENCH_CODE_ORIGIN=opnfv-gerrit


# ----------------------------------------------------------------------------
# Parse command line options and configure the script
# ----------------------------------------------------------------------------

usage() {
    cat <<EOF
$(basename $0) - build NFVbench VM images
Usage:
    $(basename $0) [OPTIONS]

OPTIONS
    -l: build NFVbench loop VM image
    -g: build NFVbench generator image
    -v: verify only (build but do not push to google storage)
    -s: use local nfvbench code instead of cloning from OPNFV gerrit
        (only relevant for NFVbench generator image)

    -t: enable debug trace (set -x + DIB_DEBUG_TRACE=1)
    -d: start debug shell in image chroot in case of build error
    -h: show this help message
EOF
    exit 1
}

while getopts ":lgvstdh" opt; do
    case $opt in
        l)
            build_loopvm=1
            ;;
        g)
            build_generator=1
            ;;
        v)
            verify_only=1
            ;;
        s)
            export DIB_NFVBENCH_CODE_ORIGIN=static
            ;;
        t)
            set -x
            export DIB_DEBUG_TRACE=1
            ;;
        d)
            DEBUG=yes
            ;;
        h)
            usage
            exit 0
            ;;
        ?)
            usage
            exit 1
            ;;
    esac
done


# Build all VM images if the image to build is not specified on the CLI
if [[ $build_generator -eq 0 ]] && [[ $build_loopvm -eq 0 ]]; then
    build_generator=1
    build_loopvm=1
fi

if [[ "${DIB_NFVBENCH_CODE_ORIGIN}" == "static" ]] && [[ $build_generator -eq 0 ]]; then
    echo "Error: option -s is only relevant to the build of the generator image"
    exit 1
fi


# ----------------------------------------------------------------------------
# Copy local nfvbench code to elements/nfvbenchvm/static/opt/nfvbench
# ----------------------------------------------------------------------------

function copy_local_nfvbench_code_to_static_dir {
    echo "Copy local nfvbench code to elements/nfvbenchvm/static/opt"
    # Create elements/nfvbenchvm/static/opt/ directory if it does not exist and
    # move there
    pushd $(dirname $0)/elements/nfvbenchvm/static
    [ -d opt ] || mkdir opt
    cd opt

    # Remove nfvbench code if it is already there
    [ -d nfvbench ] && rm -rf nfvbench

    # Use git to "copy" the local nfvbench code.
    # This will include all the committed changes of the current branch.
    git clone ../../../../../.. nfvbench

    # Go back to the current directory when this function was called
    popd
}


# ----------------------------------------------------------------------------
# Configure and start the nfvbenchvm image build
# ----------------------------------------------------------------------------

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
           python3 -m venv dib-venv
           . dib-venv/bin/activate
           pip install diskimage-builder==3.16.0
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

        # Specify CentOS version
        export DIB_RELEASE=7

        # Debug on error: if an error occurs during the build, disk-image-create
        # will drop us in a Bash inside the chroot, and we will be able to inspect
        # the current state of the image.
        if [[ "${DEBUG}" == "yes" ]]; then
            export break=after-error
        fi

        echo "Building $1.qcow2..."
        time disk-image-create -o $1 centos nfvbenchvm
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


# ----------------------------------------------------------------------------
# Main program
# ----------------------------------------------------------------------------

if [ $build_loopvm -eq 1 ]; then
    echo "Build loop VM image"
    build_image $loopvm_image_name
fi

if [ $build_generator -eq 1 ]; then
    echo "Build generator image"

    if [[ "${DIB_NFVBENCH_CODE_ORIGIN}" == "static" ]]; then
        echo "Use local nfvbench code"
        copy_local_nfvbench_code_to_static_dir

        # Append nfvbench version number to the image name:
        # during development, this is useful to distinguish the development
        # images from the latest published image.
        #
        # To avoid confusion, we use the same versioning as nfvbench (see
        # nfvbench/__init__.py), although "git describe" would give us a better
        # number with respect to uniqueness.  So we will typically get something
        # like "5.0.4.dev31" where "5.0.4" is the latest annotated tag ("5.0.3")
        # plus one and where dev31 indicates the number of commits (31) since
        # that tag.
        nfvbench_version=$(python -c 'import pbr.version; print(pbr.version.VersionInfo("nfvbench").version_string_with_vcs())')
        generator_image_name="${generator_image_name}-${nfvbench_version}"
    fi

    build_image $generator_image_name
fi
