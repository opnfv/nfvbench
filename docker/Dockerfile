# docker file for creating a container that has nfvbench installed and ready to use
FROM ubuntu:16.04

ENV TREX_VER "v2.61"
ENV VM_IMAGE_VER "0.11"
ENV PYTHONIOENCODING "utf8"

# Note: do not clone with --depth 1 as it will cause pbr to fail extracting the nfvbench version
# from the git tag

RUN apt-get update && apt-get install -y software-properties-common

RUN add-apt-repository -y ppa:deadsnakes/ppa

RUN apt-get update && apt-get install -y \
       git \
       kmod \
       pciutils \
       python3.6 \
       vim \
       wget \
       net-tools \
       iproute2 \
       libelf1 \
       && ln -s /usr/bin/python3.6 /usr/local/bin/python3 \
       && mkdir -p /opt/trex \
       && mkdir /var/log/nfvbench \
       && wget --no-cache https://trex-tgn.cisco.com/trex/release/$TREX_VER.tar.gz \
       && tar xzf $TREX_VER.tar.gz -C /opt/trex \
       && rm -f /$TREX_VER.tar.gz \
       && rm -f /opt/trex/$TREX_VER/trex_client_$TREX_VER.tar.gz \
       && cp -a /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex /usr/local/lib/python3.6/dist-packages/ \
       && rm -rf /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex \
       && wget https://bootstrap.pypa.io/get-pip.py \
       && python3 get-pip.py \
       && pip3 install -U pbr \
       && pip3 install -U setuptools \
       && cd / \
       && git clone https://gerrit.opnfv.org/gerrit/nfvbench \
       && cd /nfvbench && pip3 install -e . \
       && wget -O nfvbenchvm-$VM_IMAGE_VER.qcow2 http://artifacts.opnfv.org/nfvbench/images/nfvbenchvm_centos-$VM_IMAGE_VER.qcow2 \
       && python3 ./docker/cleanup_generators.py \
       && rm -rf /nfvbench/.git \
       && apt-get remove -y wget git \
       && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TREX_EXT_LIBS "/opt/trex/$TREX_VER/external_libs"


ENTRYPOINT ["/nfvbench/docker/nfvbench-entrypoint.sh"]
