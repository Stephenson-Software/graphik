from typing import Protocol, runtime_checkable


@runtime_checkable
class WindowChrome(Protocol):
    """The window around the drawing: fullscreen and its title.

    setFullscreen(enabled) switches to desktop fullscreen (True) or back;
    setTitle(title) names the window. Each returns True when done and False
    when this backend can't (a Strata library older than the call, a closed
    engine, the browser's page, whose window is the browser's). Never
    raises for "can't", except fullscreen on a headless Strata engine,
    which the binding refuses with an error, so Grid3DView doesn't ask a
    headless one. May block for the window system's round trip. Call from
    the thread that owns the window.
    """

    def setFullscreen(self, enabled):
        ...

    def setTitle(self, title):
        ...
