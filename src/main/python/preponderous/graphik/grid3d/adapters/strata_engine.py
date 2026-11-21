"""StrataEngine: a desktop Strata engine as a SceneRenderer, an
EventSource and a Surface, through the strata-engine binding (ctypes)."""

import ctypes
import struct

from ..geometry import FAR_PLANE, NEAR_PLANE

# Strata's StrataRenderItem: int32 kind, float3 position, float3 scale,
# float4 colour (44 bytes)
_RENDER_ITEM = struct.Struct("<i3f3f4f")


def renderItems(strata, shapes):
    """The shapes as the binding's RenderItems: a ctypes array, which
    submit_primitives takes without a copy, packed in one pass. Building a
    RenderItem object per shape costs about eight times as much, and a board
    of a few thousand tiles is drawn every frame. A shape the fast path
    can't pack (a 3-part colour), or a binding whose RenderItem isn't the
    44-byte structure, gets a list of RenderItem objects as before."""
    shapes = list(shapes)
    item = strata.RenderItem
    if isinstance(item, type) and issubclass(item, ctypes.Structure) \
            and ctypes.sizeof(item) == _RENDER_ITEM.size:
        pack = _RENDER_ITEM.pack
        try:
            data = b"".join([pack(sh.kind, *sh.position, *sh.scale, *sh.color) for sh in shapes])
        except (struct.error, TypeError):
            pass
        else:
            return (item * len(shapes)).from_buffer_copy(data)
    return [item(sh.kind, sh.position, sh.scale, sh.color) for sh in shapes]


def labelBytes(text):
    """A label's text as Strata takes it: UTF-8 with no NUL (a C string would
    end there; the browser backend drops them too), a lone surrogate as '?'
    (what Strata draws for any character outside its font)."""
    return str(text).replace("\0", "").encode("utf-8", "replace")


class StrataEngine:
    """A SceneRenderer, EventSource, Surface and WindowChrome over one
    engine of the binding: `strata` (the module), `lib` (the loaded
    libstrata) and `engine` (a window or a headless surface), all three
    shown, since games call the binding directly too."""

    def __init__(self, strata, lib, engine):
        self.strata, self.lib, self.engine = strata, lib, engine

    def draw(self, scene, aspect, present=True):
        s, engine = self.strata, self.engine
        camera = scene.camera
        if camera is not None:
            engine.set_camera(
                self.lib.look_at(
                    camera.eye,
                    camera.target,
                    fov_y_degrees=camera.fovDegrees,
                    aspect=aspect,
                    near_plane=NEAR_PLANE,
                    far_plane=FAR_PLANE,
                )
            )
        lights = []
        for light in scene.lights:
            point = s.PointLight()
            point.position = light.position
            point.color = light.color
            point.range = light.radius
            point.intensity = light.intensity
            point.flags = s.POINT_LIGHT_CAST_SHADOWS if light.castShadows else 0
            lights.append(point)
        engine.set_point_lights(lights)
        engine.begin_frame(clear_color=scene.clearColor)
        engine.submit_primitives(renderItems(s, scene.shapes))
        if scene.panels:
            engine.submit_rects(
                [s.Rect(p.x, p.y, p.width, p.height, p.color) for p in scene.panels]
            )
        if scene.labels:
            engine.submit_text(
                [
                    s.Text(l.x, l.y, l.pixelSize, s.TEXT_SHADOW, l.color, labelBytes(l.text))
                    for l in scene.labels
                ]
            )
        engine.end_frame()
        if present:
            engine.present()

    def poll(self):
        """Every pending Strata event (EVENT_QUIT, EVENT_KEY_DOWN, ...)."""
        events = []
        while True:
            event = self.engine.poll_event()
            if event is None:
                return events
            events.append(event)

    def resize(self, width, height):
        self.engine.resize(width, height)

    def setFullscreen(self, enabled):
        """Desktop fullscreen, or back; False when the loaded Strata has no
        strata_set_fullscreen (0.7.0 hasn't) or the engine is closed."""
        setter = getattr(self.engine, "set_fullscreen", None)
        if setter is None or not self.lib.has("strata_set_fullscreen"):
            return False
        setter(bool(enabled))
        return True

    def setTitle(self, title):
        """The window's title; False when the loaded Strata can't (0.7.0
        sets it only when the window opens) or the engine is closed."""
        setter = getattr(self.engine, "set_title", None)
        if setter is None or not self.lib.has("strata_set_title"):
            return False
        setter(title)
        return True

    def savePng(self, path):
        """The last frame as a PNG (headless or windowed)."""
        self.engine.save_screenshot_png(path)

    def close(self):
        if self.engine is not None:
            self.engine.close()
            self.engine = None
