#!/usr/bin/env -S uv run --script
#
# When updating the below metadata, refresh the lockfile with:
#   uv lock --script generate-proto.py --upgrade
#
# /// script
# requires-python = "==3.12.*"
# dependencies = ["grpcio-tools==1.62.2"]
# ///

import sys
from pathlib import Path

from grpc_tools import protoc

here = Path(__file__).resolve().parent
proto_dir = here.parent / "proto"

result = protoc.main(
    [
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={here}",
        f"--pyi_out={here}",
        f"--grpc_python_out={here}",
        str(proto_dir / "labgrid-coordinator.proto"),
    ]
)
if result != 0:
    sys.exit(result)

# fix import for use inside the labgrid.remote.generated package
grpc_py = here / "labgrid_coordinator_pb2_grpc.py"
grpc_py.write_text(grpc_py.read_text().replace("import labgrid", "from . import labgrid"))
