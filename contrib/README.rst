labgrid-webapp
==============

labgrid-webapp implements a browser interface to access some of labgrid's
information.

Quick Start
-----------

.. code-block:: bash

   $ cd labgrid/
   $ source venv/bin/activate
   venv $ pip install -r contrib/requirements-webapp.txt
   venv $ ./contrib/labgrid-webapp --help
   usage: labgrid-webapp [-h] [--coordinator ADDRESS] [--port PORT] [--proxy PROXY]

   Labgrid webapp

   options:
     -h, --help            show this help message and exit
     --coordinator ADDRESS, -x ADDRESS
                           Coordinator address as HOST[:PORT] (default: 127.0.0.1:20408)
     --port PORT           Port to serve on
     --proxy PROXY, -P PROXY

   venv $ ./contrib/labgrid-webapp
   INFO:     Available routes:
   INFO:       - /labgrid/graph
   INFO:     Started server process [2378028]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8800 (Press CTRL+C to quit)
   ...

Please note that the graph feature relies on a valid `graphviz` system
installation. See http://graphviz.org/download/

By default the application will start on port 8800.

To see the graph, go to http://0.0.0.0:8800/labgrid/graph

See http://0.0.0.0:8800/docs for more information on available endpoints.
