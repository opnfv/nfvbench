# docker file for creating a container that has nfvbench installed and ready to use
FROM ubuntu:16.04

ENV TREX_VER "v2.54"
ENV VM_IMAGE_VER "0.6"

# Note: do not clone with --depth 1 as it will cause pbr to fail extracting the nfvbench version
# from the git tag

# Trex v2.54:
# workaround a problem when using --unbind-unused-ports with t-rex-64
# instead patch t-rex-64 directly to add --unbind-unused-ports when calling ./trex-cfg
# so that the new arg is not passed to _t-rex-64 
# 
RUN apt-get update && apt-get install -y \
       git \
       kmod \
       pciutils \
       python \
       python-pip \
       vim \
       wget \
       net-tools \
       iproute2 \
       libelf1 \
       && mkdir -p /opt/trex \
       && mkdir /var/log/nfvbench \
       && wget --no-cache https://trex-tgn.cisco.com/trex/release/$TREX_VER.tar.gz \
       && tar xzf $TREX_VER.tar.gz -C /opt/trex \
       && rm -f /$TREX_VER.tar.gz \
       && rm -f /opt/trex/$TREX_VER/trex_client_$TREX_VER.tar.gz \
       && cp -a /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex /usr/local/lib/python2.7/dist-packages/ \
       && rm -rf /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex \
       && sed -i -e "s/2048 /512 /" -e "s/2048\"/512\"/" /opt/trex/$TREX_VER/trex-cfg \
       && sed -i -e "s/trex-cfg/trex-cfg --unbind-unused-ports/" /opt/trex/$TREX_VER/t-rex-64 \
       && apt-get remove -y python-pip \
       && wget https://bootstrap.pypa.io/get-pip.py \
       && python get-pip.py \
       && pip install -U pbr \
       && pip install -U setuptools \
       && cd / \
       && git clone https://gerrit.opnfv.org/gerrit/nfvbench \
       && cd /nfvbench && pip install -e . \
       && wget -O nfvbenchvm-$VM_IMAGE_VER.qcow2 http://artifacts.opnfv.org/nfvbench/images/nfvbenchvm_centos-$VM_IMAGE_VER.qcow2 \
       && python ./docker/cleanup_generators.py \
       && rm -rf /nfvbench/.git \
       && apt-get remove -y wget git \
       && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TREX_EXT_LIBS "/opt/trex/$TREX_VER/external_libs"


ENTRYPOINT ["/nfvbench/docker/nfvbench-entrypoint.sh"]
