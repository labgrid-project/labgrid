#!/bin/sh -ex
docker build -t labgrid-client -f docker/client/Dockerfile .
docker build -t labgrid-exporter -f docker/exporter/Dockerfile .
docker build -t labgrid-coordinator -f docker/coordinator/Dockerfile .
