#!/usr/bin/env bash
set -ex
python3 -m grpc_tools.protoc -I../proto --python_out=. --pyi_out=. --grpc_python_out=. ../proto/labgrid-coordinator.proto
sed -i "s/import labgrid/from . import labgrid/g" labgrid_coordinator_pb2_grpc.py
