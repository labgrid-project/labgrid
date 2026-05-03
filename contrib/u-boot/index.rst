
.. _u-boot-integration:

Here is a list of the available scripts:

ub-int
    Build and boot on a target, starting an interactive session

ub-cli
    Build and boot on a target, ensure U-Boot starts and provide an interactive
    session from there

ub-smoke
    Smoke test U-Boot to check that it boots to a prompt on a target

ub-bisect
    Bisect a git tree to locate a failure on a particular target

ub-pyt
    Run U-Boot pytests on a target

Terminology
^^^^^^^^^^^

target / role
    A board / DUT which is the target of the script. This is one of the targets
    mentioned in the environment file and typically corresponds to a place,
    although sometimes multiple targets may use the same place.

lg-env
^^^^^^
Usage:
    .. code-block:: bash

        . lg-env

Purpose:
    Sets the environment variables for your lab, so you can run labgrid-client,
    labgrid-exporter, etc.

lg-client
^^^^^^^^^
Usage:
    .. code-block:: bash

        lg-client ...

Purpose:
    Runs labgrid-client with the environment variables for your lab, so you can
    use the tool without worrying about all the extra arguments.

Example:
    .. code-block:: bash

        lg-client places

ub-int
^^^^^^

Usage:
    .. code-block:: bash

        ub-int [-BcdDehLRsTv] [-d <dir>] [-e <file> ] [-l <file>] *target*

====== ====================================================
Flag   Meaning
====== ====================================================
-B     Don't build U-Boot
-c     Run 'make mrproper' before building
-d     <dir> Set build directory
-D     Enable debugging
-e     <file> Log Dediprog EM100-Pro trace to a file
-h     Help
-l     <file> Log console output to file
-L     Listen-only mode (do not send input from stdin)
-R     Don't reset the board, just connect as is
-s     Send over USB (instead of writing to boot media)
-T     Don't bootstrap U-Boot
-v     Verbose mode
====== ====================================================

Purpose:
    Invoke this in the U-Boot source tree. It builds U-Boot for the given target
    and starts it on the target, bringing up an interactive U-Boot prompt. Any
    build errors are reported and abort the process. If U-Boot fails to boot,
    this will be visible on the an error is reported.


ub-cli
^^^^^^

Usage:
    .. code-block:: bash

        ub-cli [-BcdDehLsTv] [-d <dir>] [-e <file> ] [-l <file>] *target*

====== ====================================================
Flag   Meaning
====== ====================================================
-B     Don't build U-Boot
-c     Run 'make mrproper' before building
-d     <dir> Set build directory
-D     Enable debugging
-e     <file> Log Dediprog EM100-Pro trace to a file
-h     Help
-l     <file> Log console output to file
-s     Send over USB (instead of writing to boot media)
-T     Don't bootstrap U-Boot
-v     Verbose mode
====== ====================================================

Purpose:
    Invoke this in the U-Boot source tree. It builds U-Boot for the given
    target, starts it on the target, ensures that U-Boot starts correctly, then
    brings up an interactive U-Boot prompt. Any build errors are reported and
    abort the process. If U-Boot fails to boot, an error is reported.

ub-bisect
^^^^^^^^^

Usage:
    .. code-block:: bash

        ub-bisect [-cdDs] [-d <dir>] *target* [*commit*]

====== ====================================================
Flag   Meaning
====== ====================================================
-c     Run 'make mrproper' before building
-d     <dir> Set build directory
-D     Enable debugging
-h     Help
-s     Send over USB (instead of writing to boot media)
-v     Verbose mode
====== ====================================================

commit:
    Optional commit to cherry-pick before trying each bisect commit

Purpose:
    Invoke this in the U-Boot source tree once you have set the 'good and 'bad'
    commits for a bisect.

    It runs a bisect on the target to identify the commit which broke it.

    For cases where you have a 'fixup' commit that needs to be applied to each
    source tree before testing it, add the *commit* argument, which is then
    cherry-picked to the tree before each attempt.

    It is recommended to make sure the tree is clean before running a bisect.

    Internally, `ub-bisect` uses `_ub-bisect-try` to perform each step (the
    underscore being a signal to not run it directly).

    Note that a bisect may take many minutes, since it must build and load new
    software onto the board in each step, then run the smoke test.

Example:
    .. code-block:: bash

        good v2022.04      # Commit at which target bbb is known to work
        bad origin/master  # Commit at which bbb is broken
        ub-bisect bbb      # Locate the commit which broke it

ub-smoke
^^^^^^^^

Usage:
    .. code-block:: bash

        ut-smoke [-BchRsT] [-d <dir>] [-e <file> ] [-l <file>] *target*

====== ====================================================
Flag   Meaning
====== ====================================================
-B     Don't build U-Boot
-c     Run 'make mrproper' before building
-d     <dir> Set build directory
-D     Enable debugging
-e     <file> Log Dediprog EM100-Pro trace to a file
-h     Help
-l     <file> Log console output to file
-R     Don't reset the board, just connect as is
-s     Send over USB (instead of writing to boot media)
-T     Don't bootstrap U-Boot
-v     Verbose mode
====== ====================================================

Purpose:
    Invoke this in the U-Boot source tree. It builds U-Boot for the given target
    and starts it on the target, ensuring that U-Boot starts correctly. If
    U-Boot fails to boot, the test fails.

ub-pyt
^^^^^^

Usage:
    .. code-block:: bash

        ub-pyt [-BchRsT] [-e <file> ] [-l <file>] *target* [*test_spec*]

====== ====================================================
Flag   Meaning
====== ====================================================
-B     Don't build U-Boot
-c     Run 'make mrproper' before building
-e     <file> Log Dediprog EM100-Pro trace to a file
-h     Help
-l     <file> Log console output to file
-R     Don't reset the board, just connect as is
-s     Send over USB (instead of writing to boot media)
-T     Don't bootstrap U-Boot
====== ====================================================

*test_spec*
    Describes the tests to run or not run. This is passed to pytest using the
    `-k` argument. For example, `"not tpm"` means to run all tests except those
    containing the word `tpm`.

Purpose:
    Invoke this in the U-Boot source tree. It builds U-Boot for the given target
    and starts it on the target, ensures that U-Boot starts correctly, then
    runs the tests according *test_spec*. If that is not provided, it runs all
    tests that are enabled for the board.

    You may find it helpful to use this script with `git bisect`.

Examples:
    .. code-block:: bash

        ub-pyt bbb help
        git bisect run ub-pyt bbb


Remote access via tailscale
---------------------------

The sjg-lab is exposed over a self-hosted `headscale
<https://github.com/juanfont/headscale>`_ control server (the open-source
Tailscale coordination server) at ``headscale.u-boot.org``.  Once you
join the tailnet, the lab coordinator and exporter are reachable from
anywhere as if you were on the same LAN, with no SSH key distribution
or port forwarding required.

Joining the tailnet
^^^^^^^^^^^^^^^^^^^

1. Install the `tailscale client <https://tailscale.com/download>`_ on
   your machine.

2. Email the lab admin at ``sjg@u-boot.org`` with the username you
   would like to use.  You will be sent a one-time preauth key.

3. Connect your machine to the tailnet:

   .. code-block:: bash

      sudo tailscale up --login-server=https://headscale.u-boot.org --auth-key=<key>

4. Verify connectivity to the coordinator:

   .. code-block:: bash

      tailscale status     # should list 'kea'
      ping 100.64.0.1      # kea's tailnet address

Configuring labgrid for remote use
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``ub-xxx`` scripts source ``lg-env`` for their lab-specific
settings.  The defaults assume you are running on the lab host (``kea``)
itself.  When running from a remote machine, set the following
environment variables before sourcing ``lg-env`` (or in a separate file
that you source first):

.. code-block:: bash

   export PATH=$HOME/.local/bin:$HOME/u/tools/buildman:$HOME/dev/labgrid/contrib/u-boot:$PATH
   export LG_COORDINATOR=100.64.0.1:20408
   export LG_ENV=$HOME/u/test/hooks/labgrid-sjg/kea_env.cfg
   export UB_TEST_HOOKS=$HOME/u/test/hooks
   export LG_LOG_DIR=$HOME/labgrid-logs
   export U_BOOT_SOURCE_DIR=$HOME/u
   export U_BOOT_BUILD_DIR=/tmp/b
   mkdir -p $LG_LOG_DIR $U_BOOT_BUILD_DIR

Adjust the paths to match your local checkout.  The U-Boot source tree
must be available locally because building happens client-side.

After this you can run ``ub-int bbb``, ``ub-cli bbb`` etc. from any
machine joined to the tailnet, and the connection to the lab is
transparent.

Lightweight read-only access (no U-Boot tree)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you only want to interact with whatever is already running on a
board (e.g. for triage or quick debugging) and not build/flash a new
U-Boot, you do not need a U-Boot source tree on the client machine.
``ub-int -T <board>`` skips the build and bootstrap steps entirely.

Minimal client setup:

1. Install tailscale and join the tailnet (as above).
2. Install labgrid from the U-Boot integration branch (this PR) —
   the env config below uses drivers (``UBootStrategy``,
   ``UBootProviderDriver``, ``UBootWriterDriver``, etc.) that are
   not yet in upstream labgrid:

   .. code-block:: bash

      git clone https://github.com/labgrid-project/labgrid.git
      cd labgrid
      gh pr checkout 1411          # or the tip of this PR's branch
      pip install --user .

3. Add an SSH alias for kea (as above).
4. Use the example env config shipped with the labgrid checkout:
   ``contrib/u-boot/example_env.cfg``.  It defines all the lab
   targets and drivers and works as-is for read-only use.
5. Set just two environment variables:

   .. code-block:: bash

      export PATH=$HOME/.local/bin:$PATH
      export LG_COORDINATOR=100.64.0.1:20408
      export LG_ENV=$HOME/labgrid/contrib/u-boot/example_env.cfg

6. Run ``labgrid-client console -p <board>`` to connect, or — if you
   have the ``ub-xxx`` scripts checked out locally (under
   ``contrib/u-boot/`` in the same labgrid checkout) — ``ub-int -T
   <board>`` for the full strategy without building.

This setup needs no U-Boot tree, no ``UB_TEST_HOOKS``, and no
``buildman`` — only the labgrid checkout and the env config.

Notes
^^^^^

- Access is currently manual rather than self-service; this may change
  if there is enough interest to set up OIDC.
- Tailscale only handles the network transport.  Resource locking,
  reservations and per-board permissions are still handled by the
  labgrid coordinator.
- All operations that involve running commands on the exporter (SDWire
  switching, USB power control, file copies) still SSH from your
  machine to the exporter, but over the tailnet rather than the public
  Internet.
