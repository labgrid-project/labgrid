#!/bin/sh

set -e

if [ -f /opt/conf/ser2net.conf ]; then
    ser2net -c /opt/conf/ser2net.conf
fi
labgrid-exporter "$@" /opt/conf/exporter.yaml
