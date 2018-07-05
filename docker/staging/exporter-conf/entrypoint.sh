#!/bin/bash
SCRIPTPATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ser2net -c ${SCRIPTPATH}/ser2net.conf
# wait-for-it is a simple script that waits until the coordinator service is up before starting the exporter
/opt/wait-for-it/wait-for-it.sh coordinator:20408 -- labgrid-exporter -n default -x ws://coordinator:20408/ws ${SCRIPTPATH}/config.yaml
