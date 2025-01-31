================
 labgrid-pytest
================

labgrid-pytest labgrid integration for pytest
=============================================

:Author: Rouven Czerwinski <r.czerwinski@pengutronix.de>
:organization: Labgrid-Project
:Copyright: Copyright (C) 2016-2025 Pengutronix. This library is free software;
            you can redistribute it and/or modify it under the terms of the GNU
            Lesser General Public License as published by the Free Software
            Foundation; either version 2.1 of the License, or (at your option)
            any later version.
:Version: 0.0.1
:Manual section: 7
:Manual group: embedded testing

SYNOPSIS
--------

``pytest --lg-env`` ``*.yaml``

DESCRIPTION
-----------
Labgrid ships a pytest plugin to integrate with the pytest infrastructure. It is
activated if the `--lg-env` parameter is supplied to the pytest command.

The labgrid plugin parses the supplied configuration yaml file as described in
``labgrid-device-config``\(5) and allows the usage of the target and environment
fixtures.
The complete documentation is available at
https://labgrid.readthedocs.io/en/latest/usage.html#pytest-plugin.

EXAMPLES
--------

Start tests with ``myconfig.yaml`` and directory ``tests``:

.. code-block:: bash

   $ pytest --lg-env myconfig.yaml tests


SEE ALSO
--------

``labgrid-device-config``\(5)
