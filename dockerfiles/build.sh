#!/bin/sh

set -ex

export DOCKER_BUILDKIT=1

for t in client exporter coordinator; do
    docker build --target labgrid-${t} -t labgrid-${t} -f dockerfiles/Dockerfile .
done
