from typing import Protocol, runtime_checkable


@runtime_checkable
class SceneRenderer(Protocol):
    """Draws one complete Scene now.

    `scene` is a scene.Scene whose limits the caller has already checked
    (Scene.checkLimits()); `aspect` is the window's width over its height,
    for the camera's projection; `present` shows the frame once drawn (a
    backend that draws on its own frames, like the page's relay, may ignore
    it). Returns nothing. Raises for what the backend refuses (a
    wire.WireError from the relay); an Unavailable never comes from here,
    only from opening. May block for one frame's drawing. Not thread-safe:
    call from the thread that owns the window.
    """

    def draw(self, scene, aspect, present=True):
        ...
