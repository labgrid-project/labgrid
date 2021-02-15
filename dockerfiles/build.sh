#!/bin/sh

set -ex

export DOCKER_BUILDKIT=1

VERSION="$(./setup.py --version | tail -1)"

for t in client exporter coordinator; do
    docker build --build-arg VERSION="$VERSION" \
        --target labgrid-${t} -t labgrid-${t} -f dockerfiles/Dockerfile .
done
