#!/bin/sh

set -ex

for dir in base client exporter coordinator; do
    docker build -t labgrid-${dir} -f docker/${dir}/Dockerfile .
done
