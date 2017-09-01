#!/bin/bash
if [ -z "$1" ] ||  [ $1 != 'start_rest_server' ];then
	tail -f /dev/null
else
	 nfvbench --server /tmp/http_root --host 127.0.0.1 --port 7556
fi
