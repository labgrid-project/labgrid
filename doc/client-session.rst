Using the coordinator session from Python
========================================

``labgrid.remote.session`` owns the coordinator connection,
synchronized place and resource caches, and coordinator operations.
``labgrid.remote.client`` owns argument parsing, presenters,
interactive commands, and process exit handling.
Use the session for integrations and existing labgrid drivers for device operations.

Connection lifecycle
--------------------

In asynchronous code, supply the running loop and manage the session explicitly:

.. code-block:: python

   import asyncio
   from labgrid.remote.session import ClientSession

   async def list_available_places(address):
       session = ClientSession(address, asyncio.get_running_loop())
       try:
           await session.start()
           return session.list_places(released=True)
       finally:
           await session.stop()
           await session.close()

``ClientSession`` accepts an explicit address (including the port),
optional gRPC ``credentials``, ``env``, ``role``, ``username``, ``hostname``,
and reservation ``token``.
Identity defaults to the local OS user and hostname.
It does not read CLI environment defaults such as ``LG_TOKEN`` or ``LG_USERNAME``;
applications should resolve their settings and pass the values explicitly.
TLS credentials can be constructed with ``labgrid.remote.common.get_client_credentials``.

For synchronous code,
``labgrid.remote.session.start_session(address, ...)`` creates and starts a session,
applies proxy address resolution, and defaults the port to 20408.
Use ``session.loop.run_until_complete(...)`` for subsequent async calls
and for ``stop()`` and ``close()``.
The helper must not be called from an already running event loop.
The caller owns the loop and closes it when finished.

Domain operations
-----------------

Session methods accept primitives and domain classes,
and return domain objects, typed collections, or ``None``.
They never require a dictionary or return a generated protobuf response.
Existing classes include ``Place``, ``Reservation``, ``ResourceMatch``, and ``Target``.
``Tag`` and ``ReservationFilter`` describe structured inputs that previously required nested maps:

.. code-block:: python

   from labgrid.remote.session import ReservationFilter, Tag

   reservation = await session.create_reservation(
       (ReservationFilter("main", (Tag("board", "example"),)),),
       priority=0.0,
   )
   reservation = await session.wait_reservation(reservation)
   # Inspect reservation.state and allocations before acquiring a place.
   place = session.get_place("+" + reservation.token)
   place = await session.acquire_place(place, allow_unmatched=False)
   try:
       target = session.get_target(place)
       # Use configured target drivers here.
   finally:
       await session.release_place(place)
       await session.cancel_reservation(reservation)

``poll_reservation`` refreshes the reservation's timeout and returns its latest state;
``wait_reservation`` polls until it leaves the waiting state.
Waiting can also finish with an expired or invalid reservation,
so callers must inspect the returned state.
Before returning, it synchronizes the place cache
so an allocated reservation can be looked up by token immediately.
Synchronization failure raises ``ServerError``.
Wrap waiting in ``asyncio.wait_for`` when a deadline is needed.

Place lookup and mutation methods return live cached ``Place`` instances.
Passing a ``Place`` resolves its exact name in the cache without alias or substring matching;
a removed place raises ``PlaceNotFoundError``.
Acquisition and release synchronize the cache before returning.
Do not mutate these objects yourself.
Place mutations raise ``ServerError`` if synchronization fails.
The coordinator may already have applied the mutation,
so check its state after reconnecting before retrying.
Reservation responses are separate snapshots.
``get_target_resources(place)`` returns a tuple of ``TargetResource`` bindings;
each binding has a local ``name`` and a live ``ResourceEntry`` in ``resource``.
The existing domain objects retain their internal maps (such as ``Place.tags``);
serialization belongs in the application's REST, CLI, or other adapter.

Events and errors
-----------------

Register a synchronous callback with ``session.subscribe(callback)``
and remove it with ``session.unsubscribe(callback)``.
``ResourceChanged`` and ``PlaceChanged`` carry independent before/after snapshots
in ``previous`` and ``current``.
``previous is None`` means creation and ``current is None`` means deletion.
Resource events also identify the exporter, group, and resource name.
Callbacks run in update order; keep them short.
Callback exceptions are logged without stopping the update stream,
except ``BrokenPipeError``, which stops the stream
so CLI monitoring terminates when its output pipe closes.
A ``PlaceChanged.description`` string preserves the original creation description used by the CLI monitor.

The session raises ``UserError`` for invalid operations
and ``ServerError`` for coordinator RPC failures.
The CLI formats these errors and maps them to exit codes.
Library callers handle the exceptions directly.
Configure logging in the application;
the session does not install terminal handlers or print results.

Catch specific ``UserError`` subclasses to distinguish causes without parsing messages.
These include ``MissingPlaceNameError``, ``MissingPlacePatternError``,
``PlaceNotFoundError``, ``AmbiguousPlaceError``, ``PlaceNotAcquiredError``,
``PlaceNotIdleError``, and ``PlaceAlreadyAcquiredError``.
Ownership conflicts use ``PlaceUserMismatchError``, ``PlaceHostMismatchError``,
or ``PlaceReleasePermissionError``;
their ``PlaceOwnershipError`` base captures ``place_name``, ``owner_host``, and ``owner_user``
independently of later cache updates.
Invalid inputs use ``InvalidTagError``, ``InvalidReservationFilterError``,
``InvalidResourceMatchError``, or ``InvalidClientIdentityError``;
an unresolved resource match raises ``UnmatchedResourceError``.
All remain catchable as ``UserError``.
CLI handlers catch only the types requiring additional command-line guidance
and leave other errors unchanged.

Migrating integrations
----------------------

Import ``ClientSession`` from ``labgrid.remote.session``.
A compatibility import remains in ``labgrid.remote.client``,
along with its legacy ``start_session`` helper for existing connection callers.
The legacy helper still accepts ``extra`` for connection settings
and resolves the CLI environment defaults.
New integrations should use explicit parameters with the session module helper.

Replace fake ``argparse.Namespace`` objects and CLI method overrides with calls
such as ``acquire_place(place, allow_unmatched=False)``,
``release_place(place, kick=False)``, and ``list_reservations()``.
CLI-only methods now belong to ``ClientCommands``.
In particular, integrations extending the old class must migrate overridden command signatures
and dictionary-based resource iteration to the new API.
Environment selection and strategy progress messages remain in the CLI;
library callers perform strategy transitions through their target's strategy driver.
