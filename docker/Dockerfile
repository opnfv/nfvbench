# docker file for creating a container that has nfvbench installed and ready to use
FROM ubuntu:16.04

ENV TREX_VER "v2.32"
ENV NFVBENCH_TAG "1.2.5"
ENV VM_IMAGE_VER "0.5"

RUN apt-get update && apt-get install -y \
       git \
       kmod \
       pciutils \
       python \
       python-pip \
       vim \
       wget \
       net-tools \
       libelf1 \
       && mkdir /tmp/http_root \
       && mkdir -p /opt/trex \
       && mkdir /var/log/nfvbench \
       && wget --no-cache https://trex-tgn.cisco.com/trex/release/$TREX_VER.tar.gz \
       && tar xzf $TREX_VER.tar.gz -C /opt/trex \
       && rm -f /$TREX_VER.tar.gz \
       && rm -f /opt/trex/$TREX_VER/trex_client_$TREX_VER.tar.gz \
       && cp -a /opt/trex/$TREX_VER/automation/trex_control_plane/stl/trex_stl_lib /usr/local/lib/python2.7/dist-packages/ \
       && rm -rf /opt/trex/$TREX_VER/automation/trex_control_plane/stl/trex_stl_lib \
       && sed -i -e "s/2048 /512 /" -e "s/2048\"/512\"/" /opt/trex/$TREX_VER/trex-cfg \
       && pip install -U pip pbr \
       && pip install -U setuptools \
       && cd / \
       && git clone --depth 1 -b $NFVBENCH_TAG https://gerrit.opnfv.org/gerrit/nfvbench \
       && cd /nfvbench && pip install -e . \
       && wget -O nfvbenchvm-$VM_IMAGE_VER.qcow2 http://artifacts.opnfv.org/nfvbench/images/nfvbenchvm_centos-$VM_IMAGE_VER.qcow2 \
       && python ./docker/cleanup_generators.py \
       && rm -rf /nfvbench/.git \
       && apt-get remove -y wget git \
       && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TREX_STL_EXT_PATH "/opt/trex/$TREX_VER/external_libs"

ENTRYPOINT ["/nfvbench/docker/nfvbench-entrypoint.sh"]

