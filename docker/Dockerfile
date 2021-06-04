# docker file for creating a container that has nfvbench installed and ready to use
FROM ubuntu:20.04

ENV TREX_VER "v2.89"
ENV VM_IMAGE_VER "0.15"
ENV PYTHONIOENCODING "utf8"

RUN apt-get update && apt-get install -y \
       git \
       kmod \
       pciutils \
       python3.8 \
       vim \
       wget \
       net-tools \
       iproute2 \
       libelf1 \
       python3-dev \
       libpython3.8-dev \
       python3-distutils \
       gcc \
       && ln -s /usr/bin/python3.8 /usr/local/bin/python3 \
       && mkdir -p /opt/trex \
       && mkdir /var/log/nfvbench \
       && wget --no-cache --no-check-certificate https://trex-tgn.cisco.com/trex/release/$TREX_VER.tar.gz \
       && tar xzf $TREX_VER.tar.gz -C /opt/trex \
       && rm -f /$TREX_VER.tar.gz \
       && rm -f /opt/trex/$TREX_VER/trex_client_$TREX_VER.tar.gz \
       && cp -a /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex /usr/local/lib/python3.8/dist-packages/ \
       && rm -rf /opt/trex/$TREX_VER/automation/trex_control_plane/interactive/trex \
       && wget https://bootstrap.pypa.io/get-pip.py \
       && python3 get-pip.py \
       && pip3 install -U pbr \
       && pip3 install -U setuptools \
       && cd /opt \
       # Note: do not clone with --depth 1 as it will cause pbr to fail extracting the nfvbench version
       # from the git tag
       && git clone https://gerrit.opnfv.org/gerrit/nfvbench \
       && cd nfvbench && pip3 install -e . \
       && wget -O nfvbenchvm-$VM_IMAGE_VER.qcow2 http://artifacts.opnfv.org/nfvbench/images/nfvbenchvm_centos-$VM_IMAGE_VER.qcow2 \
       # Override Xtesting testcases.yaml file by NFVbench default one
       && cp xtesting/testcases.yaml /usr/local/lib/python3.8/dist-packages/xtesting/ci/testcases.yaml \
       && python3 ./docker/cleanup_generators.py \
       && rm -rf /opt/nfvbench/.git \
       # Symlink for retrocompatibility 4.x
       && ln -s /opt/nfvbench /nfvbench \
       && apt-get remove -y wget git python3-dev libpython3.8-dev gcc \
       && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TREX_EXT_LIBS "/opt/trex/$TREX_VER/external_libs"


ENTRYPOINT ["/opt/nfvbench/docker/nfvbench-entrypoint.sh"]
