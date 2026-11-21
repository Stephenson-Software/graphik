from typing import Protocol, runtime_checkable


@runtime_checkable
class Surface(Protocol):
    """The drawing surface's own life: its size, a snapshot of it, its end.

    resize(width, height) follows a new window size (the camera is the
    view's business, not the surface's). savePng(path) writes the last frame
    as a PNG, or raises errors.Unavailable where the backend can't (the
    browser, whose page takes its own screenshots). close() ends the
    surface; whether a second close() does anything is the backend's (the
    desktop engine closes once, the page is told every time).
    """

    def resize(self, width, height):
        ...

    def savePng(self, path):
        ...

    def close(self):
        ...
