"""Input events: Strata's event types, the relay's Event, and pygame
events made from either, so a game's 2D input handling works unchanged in
3D. Pure Python; pygame is passed in, never imported. web.py re-exports
every name.
"""

from types import SimpleNamespace

# Strata's event types (strata.h) and the web relay's additions.
EVENT_QUIT, EVENT_KEY_DOWN, EVENT_KEY_UP = 1, 2, 3
EVENT_MOUSE_MOTION, EVENT_MOUSE_BUTTON_DOWN, EVENT_MOUSE_BUTTON_UP = 4, 5, 6
EVENT_MOUSE_WHEEL, EVENT_RESIZED, EVENT_TEXT_INPUT = 7, 8, 9
EVENT_FINGER_DOWN, EVENT_FINGER_UP, EVENT_FINGER_MOTION, EVENT_FINGER_CANCELED = 16, 17, 18, 19

# Stands in for the strata module where games read event types from it
# (view.strata.EVENT_QUIT), so the same loop reads desktop and web events.
EVENTS = SimpleNamespace(
    EVENT_QUIT=EVENT_QUIT, EVENT_KEY_DOWN=EVENT_KEY_DOWN, EVENT_KEY_UP=EVENT_KEY_UP,
    EVENT_MOUSE_MOTION=EVENT_MOUSE_MOTION, EVENT_MOUSE_BUTTON_DOWN=EVENT_MOUSE_BUTTON_DOWN,
    EVENT_MOUSE_BUTTON_UP=EVENT_MOUSE_BUTTON_UP, EVENT_MOUSE_WHEEL=EVENT_MOUSE_WHEEL,
    EVENT_RESIZED=EVENT_RESIZED, EVENT_TEXT_INPUT=EVENT_TEXT_INPUT,
    EVENT_FINGER_DOWN=EVENT_FINGER_DOWN, EVENT_FINGER_UP=EVENT_FINGER_UP,
    EVENT_FINGER_MOTION=EVENT_FINGER_MOTION, EVENT_FINGER_CANCELED=EVENT_FINGER_CANCELED,
)

class Event:
    """A Strata-style event (the fields of strata.h's StrataEvent, plus the
    web's pointer, id, nx, ny for touch and the browser's key)."""

    __slots__ = ("type", "scancode", "modifiers", "repeat", "button", "width", "height",
                 "x", "y", "dx", "dy", "text", "pointer", "id", "nx", "ny", "key", "pressure")

    def __init__(self, d):
        for name in self.__slots__:
            setattr(self, name, d.get(name, "" if name in ("text", "pointer", "key") else 0))

    def __repr__(self):
        return "Event(%s)" % ", ".join(
            "%s=%r" % (n, getattr(self, n)) for n in self.__slots__ if getattr(self, n))

# -- pygame events, so a game's 2D handlers work in 3D

# USB HID usage id -> pygame key name (pygame.key.key_code takes these).
_KEY_NAMES = {40: "return", 41: "escape", 42: "backspace", 43: "tab", 44: "space", 45: "-", 46: "=",
              47: "[", 48: "]", 49: "\\", 51: ";", 52: "'", 53: "`", 54: ",", 55: ".", 56: "/",
              74: "home", 75: "page up", 76: "delete", 77: "end", 78: "page down",
              79: "right", 80: "left", 81: "down", 82: "up",
              224: "left ctrl", 225: "left shift", 226: "left alt", 227: "left meta",
              228: "right ctrl", 229: "right shift", 230: "right alt", 231: "right meta"}
_KEY_NAMES.update({4 + i: chr(97 + i) for i in range(26)})
_KEY_NAMES.update({30 + i: str((i + 1) % 10) for i in range(10)})
_KEY_NAMES.update({58 + i: "f%d" % (i + 1) for i in range(12)})
# SDL3 modifier bits; pygame's KMOD_* (SDL2's) use the same bits for these.
_MODS = (0x1, 0x2, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000)


def pygameKey(scancode, pygame):
    """The pygame key constant for a Strata (USB HID) scancode, or 0."""
    name = _KEY_NAMES.get(scancode)
    try:
        return pygame.key.key_code(name) if name else 0
    except (ValueError, AttributeError):
        return 0


def toPygameEvents(events, pygame, keys=False, pointer=True, fingers=True):
    """pygame events for relay (or desktop Strata) events: KEYDOWN, KEYUP and
    TEXTINPUT; MOUSEBUTTONDOWN/UP, MOUSEMOTION and MOUSEWHEEL; FINGERDOWN,
    FINGERUP and FINGERMOTION (a cancelled finger is a FINGERUP); and
    VIDEORESIZE. Keys are off by default: under pygbag, pygame's own SDL
    already gets them (it listens on the whole page), so posting them too
    would double every key. The pointer is on: the relay's canvas covers
    pygame's, so its mouse and touch never reach SDL."""
    out = []
    for e in events:
        t = e.type
        kind = getattr(e, "pointer", "") or ""
        if keys and t in (EVENT_KEY_DOWN, EVENT_KEY_UP):
            mod = 0
            for bit in _MODS:
                if getattr(e, "modifiers", 0) & bit:
                    mod |= bit
            key = getattr(e, "key", "") or ""
            out.append(pygame.event.Event(
                pygame.KEYDOWN if t == EVENT_KEY_DOWN else pygame.KEYUP,
                key=pygameKey(e.scancode, pygame), scancode=e.scancode, mod=mod,
                unicode=key if len(key) == 1 else ""))
        elif keys and t == EVENT_TEXT_INPUT:
            out.append(pygame.event.Event(pygame.TEXTINPUT, text=e.text))
        elif pointer and t in (EVENT_MOUSE_BUTTON_DOWN, EVENT_MOUSE_BUTTON_UP):
            out.append(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN if t == EVENT_MOUSE_BUTTON_DOWN else pygame.MOUSEBUTTONUP,
                pos=(int(e.x), int(e.y)), button=e.button, touch=kind == "touch"))
        elif pointer and t == EVENT_MOUSE_MOTION:
            out.append(pygame.event.Event(
                pygame.MOUSEMOTION, pos=(int(e.x), int(e.y)),
                rel=(int(getattr(e, "dx", 0)), int(getattr(e, "dy", 0))),
                buttons=(0, 0, 0), touch=kind == "touch"))
        elif pointer and t == EVENT_MOUSE_WHEEL:
            out.append(pygame.event.Event(pygame.MOUSEWHEEL, x=e.x, y=e.y, flipped=False))
        elif fingers and t in (EVENT_FINGER_DOWN, EVENT_FINGER_UP, EVENT_FINGER_MOTION,
                               EVENT_FINGER_CANCELED):
            fingerKind = {EVENT_FINGER_DOWN: pygame.FINGERDOWN,
                          EVENT_FINGER_MOTION: pygame.FINGERMOTION}.get(t, pygame.FINGERUP)
            out.append(pygame.event.Event(
                fingerKind, x=e.nx, y=e.ny, dx=getattr(e, "dx", 0), dy=getattr(e, "dy", 0),
                finger_id=e.id, touch_id=0, pressure=getattr(e, "pressure", 0) or 1.0))
        elif t == EVENT_RESIZED:
            out.append(pygame.event.Event(pygame.VIDEORESIZE, size=(e.width, e.height),
                                          w=e.width, h=e.height))
    return out
