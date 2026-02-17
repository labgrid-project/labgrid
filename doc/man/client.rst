.. _labgrid-client:

labgrid-client CLI
==================

Labgrid is a scalable infrastructure and test architecture for embedded (linux) systems.

This is the client to control a boards status and interface with it on remote machines.

.. currentmodule:: labgrid.remote.client


.. autoprogram:: labgrid.remote.client:get_parser(auto_doc_mode=True)
   :prog: labgrid-client

Configuration File
------------------
The configuration file follows the description in ``labgrid-device-config``\(5).

Environment Variables
---------------------
Various labgrid-client commands use the following environment variable:

LG_PLACE
~~~~~~~~
This variable can be used to specify a place without using the ``-p`` option, the ``-p`` option overrides it.

LG_TOKEN
~~~~~~~~
This variable can be used to specify a reservation for the ``wait`` command and
for the ``+`` place expansion.

LG_STATE
~~~~~~~~
This variable can be used to specify a state which the device transitions into
before executing a command. Requires a configuration file and a Strategy
specified for the device.

LG_INITIAL_STATE
~~~~~~~~~~~~~~~~
This variable can be used to specify an initial state the device is known to
be in.
This is useful during development. The Strategy used must implement the
``force()`` method.
A desired state must be set using ``LG_STATE`` or ``-s``/``--state``.

LG_ENV
~~~~~~
This variable can be used to specify the configuration file to use without
using the ``--config`` option, the ``--config`` option overrides it.

LG_COORDINATOR
~~~~~~~~~~~~~~
This variable can be used to set the default coordinator in the format
``HOST[:PORT]`` (instead of using the ``-x`` option).

LG_PROXY
~~~~~~~~
This variable can be used to specify a SSH proxy hostname which should be used
to connect to the coordinator and any resources which are normally accessed
directly.

LG_HOSTNAME
~~~~~~~~~~~
Override the hostname used when accessing a resource. Typically only useful for
CI pipelines where the hostname may not be consistent between pipeline stages.

LG_USERNAME
~~~~~~~~~~~
Override the username used when accessing a resource. Typically only useful for
CI pipelines where the username may not be consistent between pipeline stages.

LG_SSH_CONNECT_TIMEOUT
~~~~~~~~~~~~~~~~~~~~~~
Set the connection timeout when using SSH (The ``ConnectTimeout`` option). If
unspecified, defaults to 30 seconds.

LG_AGENT_PREFIX
~~~~~~~~~~~~~~~~~~~~~~
Add a prefix to ``.labgrid_agent_{agent_hash}.py`` allowing specification for
where on the exporter it should be uploaded to. 

LG_AGENT_PYTHON
~~~~~~~~~~~~~~~
Specify python executable other the the default ``python3``. By pointing
to an executable in a particular virtual environment, use this environment
and its packages to run the agent and any agent-wrapped code.

Matches
-------
Match patterns are used to assign a resource to a specific place. The format is:
exporter/group/cls/name, exporter is the name of the exporting machine, group is
a name defined within the exporter, cls is the class of the exported resource
and name is its name. Wild cards in match patterns are explicitly allowed, *
matches anything.

Adding Named Resources
----------------------
If a target contains multiple Resources of the same type, named matches need to
be used to address the individual resources. In addition to the *match* taken by
``add-match``, ``add-named-match`` also takes a name for the resource. The other
client commands support the name as an optional parameter and will inform the
user that a name is required if multiple resources are found, but no name is
given.

If one of the resources should be used by default when no resource name is
explicitly specified, it can be named ``default``.

Examples
--------

To retrieve a list of places run:

.. code-block:: bash

   $ labgrid-client places

To access a place, it needs to be acquired first, this can be done by running
the ``acquire command`` and passing the placename as a -p parameter:

.. code-block:: bash

   $ labgrid-client -p <placename> acquire

Open a console to the acquired place:

.. code-block:: bash

   $ labgrid-client -p <placename> console

Add all resources with the group "example-group" to the place example-place:

.. code-block:: bash

   $ labgrid-client -p example-place add-match */example-group/*/*

See Also
--------

``labgrid-exporter``\(1)
