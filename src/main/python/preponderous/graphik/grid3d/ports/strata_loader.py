from typing import Protocol, runtime_checkable


@runtime_checkable
class StrataLoader(Protocol):
    """Opens a Strata engine here, or says in plain words why it can't.

    open(width, height, title, headless) returns a display that is a
    SceneRenderer, an EventSource and a Surface at once, with the sun and
    lighting the desktop view draws with already set, and with its
    binding's `strata`, `lib` and `engine` showing (games read them). It
    raises errors.Unavailable with a reason a player can act on: no library
    for this system, the binding not installed, the library not loading, no
    window or GPU. May block while the binding downloads its library the
    first time. Call from the thread that will draw.
    """

    def open(self, width, height, title, headless):
        ...
