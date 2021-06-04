#!/bin/bash

set -e

NFVBENCH_CONF=/etc/nfvbenchvm.conf
E2E_CFG=/etc/nfvbench/e2e.cfg
LOOPBACK_CFG=/etc/nfvbench/loopback.cfg
NFVBENCH_CFG=/etc/nfvbench/nfvbench.cfg

# Parse and obtain all configurations
eval $(cat $NFVBENCH_CONF)

# WE assume there are at least 2 cores available for the VM
CPU_CORES=$(grep -c ^processor /proc/cpuinfo)

# We need at least 2 admin cores (one master and another latency).
if [ $CPU_CORES -le 3 ]; then
    ADMIN_CORES=2
else
    # If the number of cores is even we
    # reserve 3 cores for admin (third being idle) so the number of
    # workers is either 1 (if CPU_CORES is 4) or always even
    if (( $CPU_CORES % 2 )); then
        ADMIN_CORES=2
    else
        ADMIN_CORES=3
    fi
fi
# 2 vcpus: AW (core 0: Admin, core 1: Worker)
# 3 vcpus: AWW (core 0: Admin, core 1,2: Worker)
# 4 vcpus: AWWU (core 0: Admin, core 1,2: Worker, core 3: Unused)
# 5 vcpus: AWWWW
# 6 vcpus: AWWWWU
WORKER_CORES=$(expr $CPU_CORES - $ADMIN_CORES)
# worker cores are all cores except the admin core (core 0) and the eventual unused core
# AW -> 1
# AWW -> 1,2
# AWWU -> 1,2
WORKER_CORE_LIST=$(seq -s, $ADMIN_CORES $WORKER_CORES)
# always use all cores
CORE_MASK=0x$(echo "obase=16; 2 ^ $CPU_CORES - 1" | bc)

logger "NFVBENCHVM: CPU_CORES=$CPU_CORES, ADMIN_CORES=$ADMIN_CORES, WORKER_CORES=$WORKER_CORES ($WORKER_CORE_LIST)"

# Isolate all cores that are reserved for workers
tuna -c $WORKER_CORE_LIST --isolate

NET_PATH=/sys/class/net

get_pci_address() {
    # device mapping for CentOS Linux 7:
    # lspci:
    #   00.03.0 Ethernet controller: Red Hat, Inc. Virtio network device
    #   00.04.0 Ethernet controller: Red Hat, Inc. Virtio network device
    # /sys/class/net:
    # /sys/class/net/eth0 -> ../../devices/pci0000:00/0000:00:03.0/virtio0/net/eth0
    # /sys/class/net/eth1 -> ../../devices/pci0000:00/0000:00:04.0/virtio1/net/eth1

    mac=$1
    for f in $(ls $NET_PATH/); do
        if grep -q "$mac" $NET_PATH/$f/address; then
            pci_addr=$(readlink $NET_PATH/$f | cut -d "/" -f5)
            # some virtual interfaces match on MAC and do not have a PCI address
            if [ "$pci_addr" -a "$pci_addr" != "N/A" ]; then
                # Found matching interface
                logger "NFVBENCHVM: found interface $f ($pci_addr) matching $mac"
                break
            else
                pci_addr=""
            fi
        fi;
    done
    if [ -z "$pci_addr" ]; then
        echo "ERROR: Cannot find pci address for MAC $mac" >&2
        logger "NFVBENCHVM ERROR: Cannot find pci address for MAC $mac"
        return 1
    fi
    echo $pci_addr
    return 0
}

get_interfaces_mac_values(){
    # Set dynamically interfaces mac values, if VM is spawn with SRIOV PF ports
    # and openstack API are accessible
    if [ -z "$LOOPBACK_INTF_MAC1" ] && [ -z "$LOOPBACK_INTF_MAC2" ]; then
        if [ "$CLOUD_DETAIL" ] && [ "$LOOPBACK_PORT_NAME1" ] && [ "$LOOPBACK_PORT_NAME2" ]; then
            LOOPBACK_INTF_MAC1=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $LOOPBACK_PORT_NAME1 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
            LOOPBACK_INTF_MAC2=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $LOOPBACK_PORT_NAME2 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
        fi
    fi
    if [ -z "$E2E_INTF_MAC1" ] && [ -z "$E2E_INTF_MAC2" ]; then
        if [ "$CLOUD_DETAIL" ] && [ "$E2E_PORT_NAME1" ] && [ "$E2E_PORT_NAME2" ]; then
            E2E_INTF_MAC1=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $E2E_PORT_NAME1 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
            E2E_INTF_MAC2=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $E2E_PORT_NAME2 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
        fi
    fi
    if [ -z "$INTF_MAC1" ] && [ -z "$INTF_MAC2" ]; then
        if [ "$CLOUD_DETAIL" ] && [ "$PORT_NAME1" ] && [ "$PORT_NAME2" ]; then
            INTF_MAC1=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $PORT_NAME1 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
            INTF_MAC2=$(openstack --os-cloud $CLOUD_DETAIL port list | grep $PORT_NAME2 | grep -o -Ei '([a-fA-F0-9:]{17}|[a-fA-F0-9]{12}$)' | head -1)
        fi
    fi
}

get_interfaces_pci_address(){
    # Sometimes the interfaces on the generator VM will use different physical networks. In this case,
    # we have to make sure the generator uses them in the right order.
    if [ $LOOPBACK_INTF_MAC1 ] && [ $LOOPBACK_INTF_MAC2 ]; then
        LOOPBACK_PCI_ADDRESS_1=$(get_pci_address $LOOPBACK_INTF_MAC1)
        LOOPBACK_PCI_ADDRESS_2=$(get_pci_address $LOOPBACK_INTF_MAC2)

        echo LOOPBACK_PCI_ADDRESS_1=$LOOPBACK_PCI_ADDRESS_1 >> $NFVBENCH_CONF
        echo LOOPBACK_PCI_ADDRESS_2=$LOOPBACK_PCI_ADDRESS_2 >> $NFVBENCH_CONF
    fi
    if [ $E2E_INTF_MAC1 ] && [ $E2E_INTF_MAC2 ]; then
        E2E_PCI_ADDRESS_1=$(get_pci_address $E2E_INTF_MAC1)
        E2E_PCI_ADDRESS_2=$(get_pci_address $E2E_INTF_MAC2)

        echo E2E_PCI_ADDRESS_1=$E2E_PCI_ADDRESS_1 >> $NFVBENCH_CONF
        echo E2E_PCI_ADDRESS_2=$E2E_PCI_ADDRESS_2 >> $NFVBENCH_CONF
    fi
    if [ $INTF_MAC1 ] && [ $INTF_MAC2 ]; then
        PCI_ADDRESS_1=$(get_pci_address $INTF_MAC1)
        PCI_ADDRESS_2=$(get_pci_address $INTF_MAC2)

        echo PCI_ADDRESS_1=$PCI_ADDRESS_1 >> $NFVBENCH_CONF
        echo PCI_ADDRESS_2=$PCI_ADDRESS_2 >> $NFVBENCH_CONF
    fi
}

bind_interfaces(){
    if [ $LOOPBACK_PCI_ADDRESS_1 ]; then
        dpdk-devbind -b vfio-pci $LOOPBACK_PCI_ADDRESS_1
    fi
    if [ $LOOPBACK_PCI_ADDRESS_2 ]; then
        dpdk-devbind -b vfio-pci $LOOPBACK_PCI_ADDRESS_2
    fi
    if [ $E2E_PCI_ADDRESS_1 ]; then
        dpdk-devbind -b vfio-pci $E2E_PCI_ADDRESS_1
    fi
    if [ $E2E_PCI_ADDRESS_2 ]; then
        dpdk-devbind -b vfio-pci $E2E_PCI_ADDRESS_2
    fi
    if [ $PCI_ADDRESS_1 ]; then
        dpdk-devbind -b vfio-pci $PCI_ADDRESS_1
    fi
    if [ $PCI_ADDRESS_2 ]; then
        dpdk-devbind -b vfio-pci $PCI_ADDRESS_2
    fi
}

configure_loopback_mode(){
    if [ $LOOPBACK_PCI_ADDRESS_1 ] && [ $LOOPBACK_PCI_ADDRESS_2 ]; then
        logger "NFVBENCHVM: loopback - Using pci $LOOPBACK_PCI_ADDRESS_1 ($LOOPBACK_INTF_MAC1)"
        logger "NFVBENCHVM: loopback - Using pci $LOOPBACK_PCI_ADDRESS_2 ($LOOPBACK_INTF_MAC2)"

        echo "Configuring nfvbench and TRex for loopback mode..."
        # execute env script to avoid no ENV in screen and a nfvbench error
        source /etc/profile.d/nfvbench.sh
        sed -i "s/{{PCI_ADDRESS_1}}/$LOOPBACK_PCI_ADDRESS_1/g" /etc/nfvbench/loopback.cfg
        sed -i "s/{{PCI_ADDRESS_2}}/$LOOPBACK_PCI_ADDRESS_2/g" /etc/nfvbench/loopback.cfg
        sed -i "s/{{CORES}}/$WORKER_CORES/g" /etc/nfvbench/loopback.cfg
        CORE_THREADS=$(seq -s, 2 $((2+$WORKER_CORES)))
        sed -i "s/{{CORE_THREADS}}/$CORE_THREADS/g" /etc/nfvbench/loopback.cfg
    else
        echo "ERROR: Cannot find PCI Address from MAC"
        echo "$LOOPBACK_INTF_MAC1: $LOOPBACK_PCI_ADDRESS_1"
        echo "$LOOPBACK_INTF_MAC2: $LOOPBACK_PCI_ADDRESS_2"
        logger "NFVBENCHVM ERROR: Cannot find PCI Address from MAC (loopback mode)"
    fi

}

configure_e2e_mode(){
    if [ $E2E_PCI_ADDRESS_1 ] && [ $E2E_PCI_ADDRESS_2 ]; then
        logger "NFVBENCHVM: e2e - Using pci $E2E_PCI_ADDRESS_1 ($E2E_INTF_MAC1)"
        logger "NFVBENCHVM: e2e - Using pci $E2E_PCI_ADDRESS_2 ($E2E_INTF_MAC2)"

        echo "Configuring nfvbench and TRex for e2e mode..."
        # execute env script to avoid no ENV in screen and a nfvbench error
        source /etc/profile.d/nfvbench.sh
        sed -i "s/{{PCI_ADDRESS_1}}/$E2E_PCI_ADDRESS_1/g" /etc/nfvbench/e2e.cfg
        sed -i "s/{{PCI_ADDRESS_2}}/$E2E_PCI_ADDRESS_2/g" /etc/nfvbench/e2e.cfg
        sed -i "s/{{CORES}}/$WORKER_CORES/g" /etc/nfvbench/e2e.cfg
        CORE_THREADS=$(seq -s, 2 $((2+$WORKER_CORES)))
        sed -i "s/{{CORE_THREADS}}/$CORE_THREADS/g" /etc/nfvbench/e2e.cfg
    else
        echo "ERROR: Cannot find PCI Address from MAC"
        echo "$E2E_INTF_MAC1: $E2E_PCI_ADDRESS_1"
        echo "$E2E_INTF_MAC2: $E2E_PCI_ADDRESS_2"
        logger "NFVBENCHVM ERROR: Cannot find PCI Address from MAC (e2e mode)"
    fi
}

configure_nfvbench(){
    if [ $PCI_ADDRESS_1 ] && [ $PCI_ADDRESS_2 ]; then
        logger "NFVBENCHVM: Using pci $PCI_ADDRESS_1 ($INTF_MAC1)"
        logger "NFVBENCHVM: Using pci $PCI_ADDRESS_2 ($INTF_MAC2)"

        echo "Configuring nfvbench and TRex..."
        # execute env script to avoid no ENV in screen and a nfvbench error
        source /etc/profile.d/nfvbench.sh

        if [ $DEFAULT ]; then
            cp /nfvbench/nfvbench.conf /etc/nfvbench/nfvbench.cfg
        fi
        sed -i "s/{{PCI_ADDRESS_1}}/$PCI_ADDRESS_1/g" /etc/nfvbench/nfvbench.cfg
        sed -i "s/{{PCI_ADDRESS_2}}/$PCI_ADDRESS_2/g" /etc/nfvbench/nfvbench.cfg
        sed -i "s/{{CORES}}/$WORKER_CORES/g" /etc/nfvbench/nfvbench.cfg
        CORE_THREADS=$(seq -s, 2 $((2+$WORKER_CORES)))
        sed -i "s/{{CORE_THREADS}}/$CORE_THREADS/g" /etc/nfvbench/nfvbench.cfg

    else
        echo "ERROR: Cannot find PCI Address from MAC"
        echo "$INTF_MAC1: $PCI_ADDRESS_1"
        echo "$INTF_MAC2: $PCI_ADDRESS_2"
        logger "NFVBENCHVM ERROR: Cannot find PCI Address from MAC"
    fi
}

# Check if config files are provided by config drive (CLI command) or Ansible script
# and configure NFVbench accordingly to these files
if [ -f $E2E_CFG ]; then
    if [ -z $E2E_PCI_ADDRESS_1 ] && [ -z $E2E_PCI_ADDRESS_2 ]; then
        get_interfaces_mac_values
        get_interfaces_pci_address
        bind_interfaces
    fi
    configure_e2e_mode
fi
if [ -f $LOOPBACK_CFG ]; then
    if [ -z $LOOPBACK_PCI_ADDRESS_1 ] && [ -z $LOOPBACK_PCI_ADDRESS_2 ]; then
        get_interfaces_mac_values
        get_interfaces_pci_address
        bind_interfaces
    fi
    configure_loopback_mode
fi
# if nfvbench.cfg is provided by config drive (CLI command) or Ansible script
# configure nfvbench using this file otherwise untemplate default config if no file exists
if [ -f $NFVBENCH_CFG ]; then
    if [ -z $PCI_ADDRESS_1 ] && [ -z $PCI_ADDRESS_2 ]; then
        get_interfaces_mac_values
        get_interfaces_pci_address
        bind_interfaces
    fi
    configure_nfvbench
elif [ ! -f $E2E_CFG ] && [ ! -f $LOOPBACK_CFG ]; then
    if [ -z $PCI_ADDRESS_1 ] && [ -z $PCI_ADDRESS_2 ]; then
        get_interfaces_mac_values
        get_interfaces_pci_address
        bind_interfaces
    fi
    DEFAULT=true
    configure_nfvbench
fi

exit 0