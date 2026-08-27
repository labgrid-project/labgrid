Use Cases
=========

labgrid can be used in very different ways depending on who uses the boards,
where the hardware is connected, and how much configuration and operational
knowledge must be shared between users.

The four common patterns below are:

* one developer with one board
* one tester with many boards
* multiple users sharing boards in one location
* multiple users sharing boards across locations

The last case is the most demanding one and deserves special attention. It is
also the case where the gap between "technically possible" and "pleasant to
operate" becomes most visible.

One Developer with One Board
----------------------------

This is the simplest labgrid setup. One developer works with a board connected
directly to a PC.

Typical characteristics are:

* the user usually knows the board well
* serial ports, USB devices, power switches, and images are local
* environment files live next to the project or test code
* there is little or no separation between board owner, board user, and test
  author

The same person who needs the board also controls the local tools, file paths,
and board specific details. A local environment file is usually acceptable
because it is close to the code which needs it and does not need to be
distributed to a large audience. It can include personal details and local
conventions.

The operational overhead is low compared to the shared cases below, but it is
not zero. Users may still need to install the Python package manually, set up
systemd services, add udev rules, create a dedicated user, configure the
required permissions, and learn the relevant labgrid concepts. This setup is
technically very capable, but the amount of software and abstraction can still
feel heavy when the goal is simply to automate testing on hardware at your
desk, a workflow explored further in `this talk
<https://www.youtube.com/watch?v=_QQmoT5rQOA>`_.

An example would be an embedded Linux developer with a laptop, a
serial adapter, and a single board used for daily bring-up and debugging.

One Tester with Many Boards
---------------------------

In this model, the boards are remote, but they are still effectively owned and
operated by one person or a very small group. The hardware may be in a rack, in
another room, or in another site, but the user is still close to the setup from
an ownership point of view.

Typical characteristics are:

* boards are exported from one or more remote lab hosts
* one primary user, or a very small group, maintains the board setup and uses
  it daily
* places are often mapped 1:1 to physical boards
* board specific knowledge stays within the owning team

Here, the current workflow is still workable. Exporters publish the resources.
Places are created and matched to those resources. Environment files are stored
with the user's own automation or project code.

This setup is already less convenient than the purely local case, but the pain
is usually manageable because the people maintaining the setup are also the
people using it. Knowledge is not widely distributed, onboarding is limited,
and local conventions can remain informal. This is also the use case that best
fits labgrid's current architecture, and it is the original and primary use
case for labgrid.

An example would be a tester with a rack of boards in a nearby lab, maintained
and used by the same person every day.

Multiple Users Sharing Boards in One Location
---------------------------------------------

This use case is different in an important way. The boards are now shared
infrastructure, but the users are many, varied, and often not labgrid experts.
That changes the cost model significantly.

Typical examples include internal hardware labs where development, validation,
bring-up, debugging, issue reproduction, and CI all rely on the same board
inventory. Users may include embedded Linux engineers, application developers,
electrical engineers, support engineers, validation teams, and automation
maintainers.

In such a setup, a board often looks physically simple. One serial console, one
debug probe, and one power switch may already be enough for most workflows:

.. code-block:: text

   lab/board-01/NetworkSerialPort
   lab/board-01/NetworkUSBDebugger
   lab/board-01/NetworkPowerPort

At first glance, this appears to map naturally to one place:

.. code-block:: shell

   labgrid-client -p board-01 add-match lab/board-01/*

From there, a user can run common commands such as:

.. code-block:: shell

   labgrid-client -p board-01 acquire
   labgrid-client -p board-01 console
   labgrid-client -p board-01 power cycle

For a narrow set of interactive tasks, this is enough. The problem is that
shared labs rarely stay within that narrow set for long.

Current Recommended Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The currently recommended workflow for a shared board farm is usually:

#. create places and map exporter resources to them
#. let users acquire places instead of interacting with raw resources
#. let interactive users call :command:`labgrid-client` directly for console,
   power, and similar operations
#. keep environment files with the user's own automation when strategies,
   drivers, tool paths, images, or debug configuration are needed
#. manage exporter access with normal SSH, DNS, and host-side account
   management

This workflow is as flexible as labgrid itself. It supports dynamic labs,
resource aggregation across exporters, and test suites which need to control
their own target description.

That flexibility is valuable, but in a large, mostly static board lab it can
also become a poor default. Even though labgrid is intentionally flexible, it
should still support simpler ways of working when the infrastructure is already
well understood. Otherwise, the workflow keeps exposing infrastructure details
to every user even when most users are simply trying to "use board-01".

Why This Becomes Heavy
~~~~~~~~~~~~~~~~~~~~~~

In a shared board lab, the difficulty is not that the hardware is impossible to
control. The difficulty is that the same board description and the same
operational knowledge are reconstructed again and again in slightly different
places.

Several aspects contribute to this:

* the exporter group often already represents a board, while the place is used
  to represent that same board again from the user side
* the user still needs to understand places, matches, resources, drivers,
  strategies, and environments to do more than a few basic actions
* board-specific configuration remains client-side even when it is effectively
  shared infrastructure knowledge
* infrastructure changes must be communicated outward instead of being absorbed
  centrally
* direct client to exporter access pushes access management, permissions,
  cleanup, and audit concerns down to every host

None of these points is fatal on its own. Together, they create a workflow that
works, but asks the organization to repeatedly pay for the same understanding.

An example would be a central validation lab used by firmware,
application, and test teams in the same office, all competing for the same
inventory of boards.

Multiple Users Sharing Boards Across Locations
----------------------------------------------

This is the same shared infrastructure problem, but with the added complexity
that users, operators, and hardware are no longer in the same place. The lab
may span multiple offices, multiple time zones, or even external partners. At
that point, the distance between "someone can make this work" and "this is
pleasant to operate" becomes much larger.

Typical characteristics are:

* users may not know who physically manages a given board
* recovery often depends on someone in another room, site, or time zone
* access policies and audit requirements are usually stricter
* local conventions stop scaling because the audience is broader and less
  connected

Observed friction in practice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following situations tend to come up repeatedly in large shared labs:

Board identity is split across concepts
  The physical board is already obvious to the operator and to the exporter
  layout, but users still have to reason about resources, exporter groups,
  places, and separate client-side target descriptions. For a mostly static
  1:1 board setup, this can feel like modeling the same thing multiple times.

Interactive usage and full usage diverge
  Console access or power control may work directly through the place, but more
  realistic tasks often need OpenOCD configuration, image paths, strategies,
  helper scripts, or custom drivers. The result is that the "simple" workflow
  only covers the shallow end, while normal engineering work falls back to
  extra local setup.

Shared knowledge is distributed as per-user configuration
  If many users need the same board-specific OpenOCD setup, the same flash
  layout, or the same boot strategy, that knowledge is no longer really
  personal configuration. Treating it as such makes updates and consistency
  harder than they need to be.

Infrastructure changes propagate poorly
  When tool paths, images, server names, or debug settings change, the change
  is not absorbed once at the infrastructure boundary. Instead, it tends to
  trigger a documentation, support, and synchronization exercise across users,
  repositories, or wrapper scripts.

Access management becomes part of the user workflow
  Shared Unix users reduce friction but weaken isolation and traceability.
  Per-user Unix accounts improve traceability but increase provisioning,
  revocation, SSH key management, and host-side permissions work. Neither
  choice is attractive when the goal is simply safe, shared board access.

SSH access becomes a scaling problem of its own
  When labs span multiple hosts or locations, SSH setup and lifecycle
  management can become a visible part of daily operations. Teams may benefit
  from stronger centralized approaches for authentication and short-lived
  access. One option worth evaluating is `OpenPubkey SSH (opkssh)
  <https://github.com/openpubkey/opkssh>`_.

CI and human users compete through the same abstractions
  The same board inventory must serve automation and interactive work, but the
  current model often leaves teams building local conventions on top of places,
  locks, scripts, and documentation to make that coexistence understandable.

Why The Current Model Feels Mismatched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The core issue is not that the present model is wrong. It is that it is
optimized for flexibility and configurability first, while large shared board
farms usually need operational simplicity first.

For dynamic setups, custom test suites, and project-owned environments, the
separation between resources, places, and client-side target descriptions makes
sense.

For large shared labs, however, this same separation can have unfortunate side
effects:

* the board looks simple at the hardware level, but complicated at the user
  interface level
* the infrastructure already knows most of the board description, but the user
  must still assemble the rest
* routine lab maintenance turns into user facing migration work
* support effort grows faster than the apparent complexity of the board itself

In other words, the model remains powerful, but the user experience can become
heavier than the actual task being performed.

Possible Improvements
~~~~~~~~~~~~~~~~~~~~~

Large shared labs may benefit from an additional workflow which keeps the
current flexible model intact, but offers a more infrastructure-provided path
for common static deployments.

Possible improvements include:

* allow a board-oriented definition to be served centrally, so users can
  consume a ready-to-use target instead of rebuilding it locally
* make 1:1 exporter-group-to-board mappings first-class, so the common static
  case needs less manual place modeling
* allow exporters or the coordinator to provide environment fragments or merged
  target descriptions for interactive users
* reduce the amount of board-specific knowledge that must be duplicated across
  user repositories and local wrapper scripts
* provide a cleaner access model where users interact with shared boards without
  needing direct exposure to host-level account management details
* define a clearer workflow for mixed CI and interactive usage in the same
  shared board inventory

An example would be a company with teams in different offices using
the same lab through a shared coordinator, while a smaller operations group
maintains the hardware and access policies.
