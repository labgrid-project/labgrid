# Separating `ClientSession` from the command line

## Implementation

The separation is implemented in `labgrid/remote/session.py` and the
`ClientCommands` adapter in `labgrid/remote/client.py`. The sections below record
the original design and migration rationale. See
[the session API guide](doc/client-session.rst) for the implemented signatures,
lifecycle, events, and integration migration notes. The implementation uses
`Tag` values inside `ReservationFilter`, and a `TargetResource` binding instead
of returning a resource dictionary. CLI command names and presentation remain
in `client.py`.

## Current capabilities

`ClientSession` currently combines several responsibilities:

- It creates and closes the gRPC channel and coordinator stub.
- It runs the bidirectional update stream and keeps local resource and place
  caches synchronized.
- It selects places, validates ownership, and creates labgrid targets.
- It invokes coordinator operations for places, aliases, matches, acquisition,
  release, access permissions, and reservations.
- It implements target operations such as power, digital I/O, console, SSH,
  flashing, storage, video, audio, and test-equipment commands.
- It formats command results and writes progress, warnings, and errors to
  standard output or standard error.

This makes `ClientSession` both a reusable coordinator client and the
implementation of the `labgrid-client` command-line interface.

## Current command-line coupling

The strongest coupling points in `labgrid/remote/client.py` are:

- `ClientSession.args` contains an `argparse.Namespace`. Almost every command
  reads its inputs from `self.args` instead of accepting explicit parameters.
- `get_parser()` assigns bound session methods to `args.func`, for example
  `ClientSession.acquire` and `ClientSession.print_places`.
- Session methods call `print()`, write to `sys.stdout` or `sys.stderr`, call
  `parser.error()`, and format tables, YAML, JSON, and shell output.
- Monitor callbacks print changes while they update the session caches.
- Some methods contain terminal and process behavior, including console I/O,
  signal waiting, `ssh`, `adb`, `scrcpy`, and `xdg-open`.
- `main()` creates the event loop and session, dispatches `args.func`, maps
  exceptions to messages and exit codes, and shuts the session down.

As a result, library users cannot call most operations without constructing a
fake `argparse.Namespace`, and they cannot obtain structured results without
capturing terminal output.

## Proposed separation

Keep three clear layers:

1. `labgrid/remote/session.py` owns `ClientSession`. It handles the channel,
   update stream, synchronized caches, place lookup, and coordinator RPCs. Its
   public methods accept explicit typed parameters and return domain objects,
   primitives, or small result objects. It does not import `argparse` and does
   not print.
2. `labgrid/remote/client.py` owns argument parsing, environment defaults,
   command dispatch, terminal/process interaction, exception presentation, and
   exit codes.
3. CLI presenter functions format returned objects and events into exactly the
   same stdout and stderr text produced today. They may initially remain in
   `client.py` and move to a separate module later if that improves readability.

For example, the session API could change from methods which read `self.args`
and print:

```python
await session.acquire()
await session.print_places()
```

to explicit operations which return data:

```python
places = session.list_places(acquired=acquired, released=released)
acquired_places = await session.acquire_places(
    place_patterns,
    allow_unmatched=allow_unmatched,
)
```

The CLI handlers would retain the existing presentation:

```python
async def command_acquire(session, args, output):
    places = await session.acquire_places(
        resolve_place_patterns(session, args),
        allow_unmatched=args.allow_unmatched,
    )
    for place in places:
        output.stdout(f"acquired place {place.name}")
```

Monitor output should follow the same rule. Cache callbacks should create
structured events such as `ResourceCreated`, `ResourceChanged`, and
`PlaceDeleted`. The CLI subscribes to those events and renders the current
messages. This prevents background session code from writing to a caller's
terminal.

Target commands should also receive explicit values. Interactive behavior can
stay in the CLI layer, while reusable lookup and target operations live in
normal services or existing drivers. For example, the session can return the
selected target or SSH driver, while the CLI decides whether to print status,
wait for Ctrl+C, or launch an external process.

## Public session API design

The separated session should reuse labgrid's existing domain classes whenever
they describe the operation accurately. In particular, place operations should
return or accept `Place`, reservation operations should use `Reservation`, and
resource matching should use `ResourceMatch`. Do not introduce parallel REST-
or CLI-specific models for the same concepts merely to move data between
layers. Add a small typed value or result class only when no existing class has
the required meaning.

Separating the session is an internal refactoring, not a command-line interface
change. Every existing `labgrid-client` command must retain the same result,
stdout and stderr output, output ordering and timing, exit status, prompts,
signal handling, and interactive behavior. Existing scripts and users should
not be able to observe a difference. Any intentional CLI behavior change must
be proposed and reviewed separately from the session separation.

Every public `ClientSession` method should accept explicit primitives or typed
classes. Collections should contain typed values, for example
`Sequence[Place]`, `Sequence[Reservation]`, or `Sequence[ReservationFilter]`.
A public session method must never accept or return a bare `dict`. Dictionaries
make the contract implicit, allow misspelled or missing keys, and force every
caller to understand coordinator wire details. They may still be used inside
the implementation and by explicit serialization helpers such as `asdict()`,
but they must be converted at the session boundary.

The same boundary applies to generated protobuf messages. They are transport
types and should remain inside the coordinator adapter. For example,
`CreateReservationResponse`, `AcquirePlaceResponse`, and
`CancelReservationResponse` should be converted to `Reservation`, `Place`, a
dedicated result class, or `None` before returning to a caller. This keeps REST,
CLI, and test integrations independent of the gRPC schema.

Prefer an existing class over a primitive when the caller already has the
domain object and the operation is about that object. A name, token, priority,
timeout, or boolean option can remain a primitive when it is the complete
concept. If several values form one concept, define a small typed class instead
of passing a dictionary. For example, reservation filters could use a value
class such as:

```python
@attr.frozen
class ReservationFilter:
    name: str
    tags: tuple[tuple[str, str], ...]
```

The exact collection representation can follow the project's supported Python
version, but callers should not need to construct a nested dictionary. Example
session signatures could be:

```python
def list_places(self) -> tuple[Place, ...]: ...
def find_place(self, pattern: str) -> Place: ...
async def create_reservation(
    self,
    filters: Sequence[ReservationFilter],
    priority: float = 0.0,
) -> Reservation: ...
async def list_reservations(self) -> tuple[Reservation, ...]: ...
async def cancel_reservation(self, reservation: Reservation) -> None: ...
async def acquire_place(
    self,
    place: Place,
    allow_unmatched: bool = False,
) -> Place: ...
async def release_place(self, place: Place, kick: bool = False) -> Place: ...
```

Returning the refreshed `Place` after acquisition or release gives callers the
resulting domain state without exposing an empty protobuf acknowledgement. If
the synchronized cache intentionally owns object identity, the method may
instead update and return the cached instance; that behavior should be stated
and tested.

The experimental integration in
`tools/labgrid-rest-api/src/labgrid_rest_api/session.py` demonstrates why this
contract matters. Its `get_places()` and `get_reservations()` methods already
return the existing `Place` and `Reservation` classes and are good patterns to
retain. In contrast, its create, acquire, cancel, release, and keep-alive paths
still expose protobuf objects, while reservation tags arrive as strings and are
assembled into a dictionary. During migration, move that parsing to the REST or
CLI adapter, pass typed filters into the session, and convert all protobuf
responses to existing domain objects or small typed results there.

## Behavior-preserving migration

The refactoring can be done command family by command family:

1. Record the current stdout, stderr, and exit status of representative CLI
   commands in tests.
2. Move the connection lifecycle, stream processing, caches, and coordinator
   RPC wrappers into `session.py` without changing the CLI entry point.
3. Replace each use of `self.args` with explicit primitive or typed-class
   parameters and return existing domain objects or typed results. Do not expose
   dictionaries or generated protobuf messages through the public session API.
4. Move the corresponding formatting and printing into CLI handlers, preserving
   text, ordering, destination stream, and timing.
5. Convert monitor messages to events and keep interactive commands until last,
   since their terminal and subprocess behavior needs dedicated tests.
6. Remove `args`, `prog`, `monitor`, and every `print()`/stdio dependency from
   `ClientSession` once all handlers use the new API.

Existing `pexpect` tests in `tests/test_client.py` should remain the main
compatibility checks. Add unit tests for `ClientSession` return values and
events so the reusable API can be tested without spawning the CLI or capturing
output.

The intended end state is that existing `labgrid-client` commands, output, and
exit codes remain unchanged, while Python callers can use `ClientSession`
without knowing about `argparse` or terminal streams.
