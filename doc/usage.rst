Usage
=====

Standalone
------------------

The Labgrid library consists of a set of fixtures which implement the automatic
creation of targets, drivers and synchronisation helpers. The configuration file
`environment.yaml` specifies how the library assembles these fixtures into
working targets. Certain functionality depends upon the availability of a
specific resource or driver, the parser will throw an error and a helpful
message if this is the case.

Scripting usage
~~~~~~~~~~~~~~~

Although the environment creates all the instances by itself, the test editor
still has to create the appropriate fixtures for each device. The environment,
the targets can be extracted by using the function `get_target`.

Example:
::

   from labgrid import Environment

   env = Environment()
   t1 = environment.get_target('target1')
   t2 = environment.get_target('target2')

Pytest Plugin
-------------
Labgrid provides a pytest-plugin as an entry point. It needs the --env-config=
configuration option to be set and creates environment and targets by itself.
