#!/bin/bash


restart_nfvbench_service(){
    service nfvbench restart
    echo "NFVbench running in screen 'nfvbench'"
    logger "NFVBENCHVM: NFVbench running in screen 'nfvbench'"
}

start_nfvbench(){
    ln -sfn /etc/nfvbench/nfvbench.cfg /etc/nfvbench/nfvbench.conf
    restart_nfvbench_service
}

start_nfvbench_e2e_mode(){
    ln -sfn /etc/nfvbench/e2e.cfg /etc/nfvbench/nfvbench.conf
    restart_nfvbench_service
}

start_nfvbench_loopback_mode(){
    ln -sfn /etc/nfvbench/loopback.cfg /etc/nfvbench/nfvbench.conf
    restart_nfvbench_service
}

usage() {
    echo "Usage: $0 action"
    echo "action (optional):"
    echo "e2e       start NFVbench with E2E config file"
    echo "loopback  start NFVbench with loopback config file"
    echo ""
    echo "If no action is given NFVbench will start with default config file"
    exit 1
}

# ----------------------------------------------------------------------------
# Parse command line options and configure the script
# ----------------------------------------------------------------------------
if [ "$#" -lt 1 ]; then
    start_nfvbench
    exit 0
else
    if [ $1 = "e2e" ]; then
        start_nfvbench_e2e_mode
        exit 0
    elif [ $1 = "loopback" ]; then
        start_nfvbench_loopback_mode
        exit 0
    else
        usage
    fi
fi
