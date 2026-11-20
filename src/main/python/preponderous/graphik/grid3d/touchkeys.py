"""On-screen keys for touch screens: a bar of labelled buttons that press keys.

A phone has no keyboard, so a game's keyboard-only actions (pause, a shop,
restart) can't be reached there. TouchKeys lays out a bar of buttons along
the bottom of the screen, one per key, and a tap on one posts the same
pygame KEYDOWN and KEYUP events the keyboard would, so the game's own key
handling does the work, whichever view shows: the 2D view draws the bar
with Graphik, the 3D view as screen Buttons (Labels and Panels), from one
layout, with one hit test.

The layout is worked out in CSS pixels (where a touch target is at least
MIN_TARGET, 44, pixels each way, as phones' guidelines ask) and handed back
in the pixels of the surface it is drawn on: the 3D view's are CSS pixels
already (`scale` 1); a 2D canvas the browser scales to fit the page has
`scale` CSS pixels per canvas pixel. Keys fill rows of equal buttons, at
most `portraitRows` rows on a portrait screen and `landscapeRows` on a
landscape one; when they don't all fit, the last button is "More", which
pages through the rest (a compact menu that never covers the board).

The bar takes bandHeight() pixels at the bottom of the screen. A 3D view
keeps them clear of the board (Grid3DView.setInsets(bottom=...)); a 2D game
makes its window that much taller (below()) and draws its board above it.

Show the keys only on touch screens: web.touchScreen() says whether the page
sees one. Pure Python: pygame and a Graphik are passed in.
"""

import math
from dataclasses import dataclass
from typing import Optional

from .scene import Panel, rgb255, rgba
from .text import measureText
from .ui import Button, contains, hoverColor

MIN_TARGET = 44  # CSS pixels: the smallest button a finger is sure to hit
MORE = "more"  # what press() returns for the More button


# key names (pygame.key.name's spellings) and the character a key types
_UNICODE = {"space": " ", "return": "\r", "escape": "\x1b", "tab": "\t", "backspace": "\b"}


@dataclass(frozen=True)
class TouchKey:
    """One on-screen key: its `label` and the key it presses, by pygame's
    name for it ("p", "space", "[", "up", "return", "escape", "f11")."""

    label: str
    key: str

    def unicode(self):
        """The character the key types, as a KEYDOWN's `unicode` ("" for
        keys that type none, such as the arrows)."""
        if len(self.key) == 1:
            return self.key
        return _UNICODE.get(self.key, "")


@dataclass
class KeySlot:
    """A button of the bar as laid out: its box in the surface's pixels, its
    label, and its TouchKey (None for the More button)."""

    x: float
    y: float
    width: float
    height: float
    label: str
    key: Optional[TouchKey]

    def contains(self, position):
        # the drawn box exactly, with Graphik.drawButton's edges
        return contains(self.x, self.y, self.width, self.height, position)


class TouchKeys:
    """A bar of on-screen keys (see the module's notes).

    `keys` are TouchKeys (or (label, key) pairs). Sizes are CSS pixels:
    each button is at least `minTarget` each way and wide enough for its
    label at `pixelSize` plus `padding` a side, with `gap` between buttons
    and `margin` around the bar. Colours are 0-255 (r, g, b), as Graphik
    takes them; the 3D view draws the buttons at `alpha` and the bar behind
    them in `barColor` at `barAlpha`.
    """

    def __init__(self, keys=(), minTarget=MIN_TARGET, gap=6, margin=8, pixelSize=11, padding=6,
                 portraitRows=3, landscapeRows=1, color=(34, 34, 34), textColor=(238, 238, 238),
                 barColor=(10, 10, 14), alpha=0.9, barAlpha=0.55, moreLabel="More", backLabel="Back"):
        self.minTarget, self.gap, self.margin = minTarget, gap, margin
        self.pixelSize, self.padding = pixelSize, padding
        self.portraitRows, self.landscapeRows = portraitRows, landscapeRows
        self.color, self.textColor, self.barColor = color, textColor, barColor
        self.alpha, self.barAlpha = alpha, barAlpha
        self.moreLabel, self.backLabel = moreLabel, backLabel
        self.keys = ()
        self.page = 0
        self._pages = 1
        self.setKeys(keys)

    def setKeys(self, keys):
        """Changes the keys on offer (a game's shop has others than its
        board); back to the first page when they change."""
        keys = tuple(k if isinstance(k, TouchKey) else TouchKey(*k) for k in keys)
        if keys != self.keys:
            self.keys = keys
            self.page = 0

    # -- the layout

    def _grid(self, cssWidth, cssHeight, portrait):
        """(columns, rows, pages, perPage) for a screen this size in CSS
        pixels."""
        if not self.keys:
            return 0, 0, 0, 0
        widest = max(measureText(k.label, self.pixelSize) for k in self.keys)
        widest = max(widest, measureText(self.moreLabel, self.pixelSize),
                     measureText(self.backLabel, self.pixelSize))
        cell = max(self.minTarget, widest + 2 * self.padding)
        room = cssWidth - 2 * self.margin + self.gap
        columns = max(1, int(room // (cell + self.gap)))
        if portrait is None:
            portrait = cssHeight > cssWidth
        maxRows = max(1, self.portraitRows if portrait else self.landscapeRows)
        count = len(self.keys)
        if count <= columns * maxRows:
            columns = min(columns, count)
            return columns, int(math.ceil(count / float(columns))), 1, count
        perPage = columns * maxRows - 1  # the last button is More
        if perPage < 1:
            perPage = 1
        return columns, maxRows, int(math.ceil(count / float(perPage))), perPage

    def bandHeight(self, width, height, scale=1.0, portrait=None):
        """How many of the surface's pixels the bar takes at the bottom of a
        `width` x `height` surface (0 with no keys)."""
        _, rows, _, _ = self._grid(width * scale, height * scale, portrait)
        if not rows:
            return 0
        css = rows * self.minTarget + (rows - 1) * self.gap + 2 * self.margin
        return css / float(scale)

    def layout(self, width, height, scale=1.0, portrait=None):
        """The buttons on show (this page's), as KeySlots in the surface's
        pixels, in rows along the bottom of a `width` x `height` surface.
        `portrait` says how many rows the bar may take (default: the
        surface's own shape)."""
        cssWidth, cssHeight = width * scale, height * scale
        columns, rows, pages, perPage = self._grid(cssWidth, cssHeight, portrait)
        self._pages = pages
        if not columns:
            return []
        self.page %= pages
        shown = list(self.keys[self.page * perPage:(self.page + 1) * perPage])
        if pages > 1:
            shown.append(None)
        cellWidth = (cssWidth - 2 * self.margin - (columns - 1) * self.gap) / float(columns)
        top = cssHeight - self.margin - rows * self.minTarget - (rows - 1) * self.gap
        slots = []
        for index, key in enumerate(shown):
            row, column = divmod(index, columns)
            x = self.margin + column * (cellWidth + self.gap)
            y = top + row * (self.minTarget + self.gap)
            if key is None:
                label = self.backLabel if self.page == pages - 1 else self.moreLabel
            else:
                label = key.label
            slots.append(KeySlot(x / scale, y / scale, cellWidth / scale, self.minTarget / scale,
                                 label, key))
        return slots

    def below(self, width, height, pageWidth, pageHeight):
        """For a 2D game: (band, scale) for a `width` x `height` board with
        the bar below it, the whole (width x height + band) canvas fitted to
        a `pageWidth` x `pageHeight` page as the browser does (`scale` is
        its CSS pixels per canvas pixel). The bar's buttons are then at
        least `minTarget` CSS pixels each way."""
        portrait = pageHeight > pageWidth
        scale = min(pageWidth / float(width), pageHeight / float(height))
        for _ in range(4):
            bandCss = self.bandHeight(width, height, scale, portrait) * scale
            # the canvas is fitted by its width, or by its height with the
            # band's CSS pixels below the board's
            scale = min(pageWidth / float(width), max(pageHeight - bandCss, 1.0) / float(height))
        band = int(math.ceil(bandCss / scale)) if bandCss else 0
        return band, min(pageWidth / float(width), pageHeight / float(height + band))

    # -- presses

    def slotAt(self, position, width, height, scale=1.0, portrait=None):
        """The KeySlot under `position`, or None."""
        for slot in self.layout(width, height, scale, portrait):
            if slot.contains(position):
                return slot
        return None

    def press(self, position, width, height, pygame=None, scale=1.0, portrait=None):
        """A press at `position`: on a key, its KEYDOWN and KEYUP are posted
        to pygame's queue (when `pygame` is given) and its TouchKey
        returned; on More, the next page shows and MORE is returned; off
        the bar, None (the press is the game's)."""
        slot = self.slotAt(position, width, height, scale, portrait)
        if slot is None:
            return None
        if slot.key is None:
            self.page = (self.page + 1) % max(1, self._pages)
            return MORE
        if pygame is not None:
            for event in self.keyEvents(slot.key, pygame):
                pygame.event.post(event)
        return slot.key

    @staticmethod
    def keyEvents(key, pygame):
        """The KEYDOWN and KEYUP a keyboard sends for `key` (a TouchKey),
        marked touchKey=True."""
        code = pygame.key.key_code(key.key)
        down = pygame.event.Event(pygame.KEYDOWN, key=code, mod=0, scancode=0,
                                  unicode=key.unicode(), touchKey=True)
        up = pygame.event.Event(pygame.KEYUP, key=code, mod=0, scancode=0, touchKey=True)
        return [down, up]

    # -- drawing

    def draw(self, graphik, width, height, scale=1.0, portrait=None, pointer=None):
        """The bar in a 2D view, drawn with `graphik` (a Graphik) on its
        surface: the band, then each button, lifted under `pointer`."""
        slots = self.layout(width, height, scale, portrait)
        if not slots:
            return slots
        band = self.bandHeight(width, height, scale, portrait)
        top = int(math.floor(height - band))  # to the last row of pixels
        graphik.drawRectangle(0, top, int(math.ceil(width)), int(math.ceil(height)) - top,
                              self.barColor)
        size = max(8, int(round(self.pixelSize * 1.15 / scale)))
        for slot in slots:
            box = hoverColor(self.color) if slot.contains(pointer) else self.color
            graphik.drawRectangle(slot.x, slot.y, slot.width, slot.height, box)
            graphik.drawText(slot.label, slot.x + slot.width / 2.0, slot.y + slot.height / 2.0,
                             size, self.textColor)
        return slots

    def buttons(self, width, height, portrait=None):
        """The bar's buttons in a 3D view (CSS pixels), as ui.Buttons."""
        return [Button(s.x, s.y, s.width, s.height, s.label, color=self.color,
                       textColor=self.textColor, pixelSize=self.pixelSize, alpha=self.alpha)
                for s in self.layout(width, height, 1.0, portrait)]

    def overlay(self, width, height, portrait=None, pointer=None):
        """The bar in a 3D view: (labels, panels) to add to its HUD, the
        band's panel first."""
        buttons = self.buttons(width, height, portrait)
        if not buttons:
            return [], []
        band = self.bandHeight(width, height, 1.0, portrait)
        labels, panels = [], [Panel(0, height - band, width, band,
                                    rgba(rgb255(self.barColor), self.barAlpha))]
        for button in buttons:
            panel, label = button.draw(pointer)
            panels.append(panel)
            labels.append(label)
        return labels, panels
