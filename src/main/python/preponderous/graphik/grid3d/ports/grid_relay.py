from typing import Protocol, runtime_checkable


@runtime_checkable
class GridRelay(Protocol):
    """The page's Strata grid relay (window.StrataGridRelay).

    Its own JS API is the contract, as Strata's web/kit/grid-relay
    (WIRE.md, grid-relay.js) defines it, so this port keeps all six calls:

    - request(options) asks for the 3D view with a dict of options
      ("canvas", "maxBytes", "title") and returns the relay's state;
    - state() is "loading", "ready" or "failed:<reason>";
    - send(message) takes one wire.py message (bytes) and returns 0, or the
      relay's negative status for a refused one (wire.STATUS);
    - poll() returns the events since the last poll as dicts of
      events.Event's fields, oldest first;
    - reducedMotion() is whether the page asks for reduced motion;
    - close() stops the relay drawing.

    None of them block. Expected refusals are values (a state string, a
    status); exceptions mean a broken page or bridge. Call from the game's
    one thread.
    """

    def request(self, options):
        ...

    def state(self):
        ...

    def send(self, message):
        ...

    def poll(self):
        ...

    def reducedMotion(self):
        ...

    def close(self):
        ...
