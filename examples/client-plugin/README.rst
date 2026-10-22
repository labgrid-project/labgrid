REST client command
===================

This example adds a lab-specific REST driver and a ``rest`` client command
without modifying labgrid. ``env.yaml`` imports ``rest.py`` to register the
resource, driver and command together.

With labgrid installed, start the simulated device and a local coordinator in
separate terminals::

    python examples/client-plugin/server.py
    labgrid-coordinator -l 127.0.0.1:20499

Run the following from the repository root (no exporter or hardware is needed)::

    labgrid-client -x 127.0.0.1:20499 -p rest-example create
    labgrid-client -x 127.0.0.1:20499 -p rest-example acquire
    labgrid-client -x 127.0.0.1:20499 -c examples/client-plugin/env.yaml rest get /status
    labgrid-client -x 127.0.0.1:20499 -c examples/client-plugin/env.yaml rest post /echo --data '{"hello": "world"}'
    labgrid-client -x 127.0.0.1:20499 -p rest-example release
    labgrid-client -x 127.0.0.1:20499 -p rest-example delete
