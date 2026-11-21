"""Menus over a 3D view that look and behave like graphik's 2D ones.

Button is a screen button for a 3D window: a panel with a centred label, a
hit test with the same edges as Graphik.drawButton's, and the same hover
lift. ScreenRecorder stands in for Graphik so a game's own 2D screens can
run unchanged under a 3D view: they draw into it as usual, and the 3D view
shows what they drew (as Buttons, Labels and Panels) and sends a click to
the 2D button's own function. Pure Python: no pygame, no Strata.

Colours here are 0-255 (r, g, b), as the 2D screens give them to Graphik.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .scene import Panel, rgb255, rgba
from .text import centredLabel, measureText

Color255 = Tuple[int, int, int]


def hoverColor(color):
    """Graphik.drawButton's hover lift for a 0-255 (r, g, b[, a]) colour:
    light colours (an average r/g/b of 128 or more) darken by 25, the rest
    lighten by 35, each channel clamped to 0-255. Returns (r, g, b)."""
    shift = -25 if sum(color[:3]) / 3.0 >= 128 else 35
    return tuple(max(0, min(255, c + shift)) for c in color[:3])


def contains(x, y, width, height, position):
    """True when `position` (x, y) is on the box, with Graphik.drawButton's
    edges: left and top in, right and bottom out, so buttons laid edge to
    edge share no pixel. None is never on it."""
    if position is None:
        return False
    px, py = position
    return x <= px < x + width and y <= py < y + height


@dataclass
class Button:
    """A screen button for a 3D window, in window pixels.

    `color` and `textColor` are 0-255, as Graphik.drawButton takes them;
    `pixelSize` is the label's Strata pixel size. The panel is drawn at
    `alpha`. With `padding`, a label too wide for the box widens it about its
    centre to the label's width plus `padding` a side (Strata's font is
    wider than most pygame fonts). `rise` places the label vertically (see
    centredLabel). `function` is what a click runs (click()).
    """

    x: float
    y: float
    width: float
    height: float
    text: str
    color: Color255 = (200, 200, 200)
    textColor: Color255 = (0, 0, 0)
    pixelSize: float = 16
    function: Optional[Callable] = None
    alpha: float = 1.0
    padding: Optional[float] = None
    rise: float = 0.5

    def rect(self):
        """(x, y, width, height) as drawn and hit."""
        if self.padding is None:
            return self.x, self.y, self.width, self.height
        needed = measureText(self.text, self.pixelSize) + 2 * self.padding
        if needed <= self.width:
            return self.x, self.y, self.width, self.height
        centre = self.x + self.width / 2.0
        return centre - needed / 2.0, self.y, needed, self.height

    def contains(self, position):
        x, y, width, height = self.rect()
        return contains(x, y, width, height, position)

    def draw(self, pointer=None):
        """(Panel, Label) for this frame; the panel takes the hover lift while
        `pointer` is over the button."""
        x, y, width, height = self.rect()
        box = hoverColor(self.color) if contains(x, y, width, height, pointer) else self.color
        panel = Panel(x, y, width, height, rgba(rgb255(box), self.alpha))
        label = centredLabel(self.text, x + width / 2.0, y + height / 2.0, self.pixelSize,
                             rgba(rgb255(self.textColor)), rise=self.rise)
        return panel, label

    def click(self, position):
        """Runs `function` when `position` is on the button; True if it was."""
        if self.function is None or not self.contains(position):
            return False
        self.function()
        return True


def drawButtons(buttons, pointer=None):
    """Labels and panels for several Buttons: ([Label], [Panel])."""
    labels, panels = [], []
    for button in buttons:
        panel, label = button.draw(pointer)
        panels.append(panel)
        labels.append(label)
    return labels, panels


# -- standing in for Graphik


@dataclass
class RecordedText:
    """A drawText call: text centred on (x, y); size is a pygame font size."""

    text: str
    x: float
    y: float
    size: float
    color: Color255


@dataclass
class RecordedRect:
    """A drawRectangle call."""

    x: float
    y: float
    width: float
    height: float
    color: Color255


@dataclass
class RecordedImage:
    """A drawImage call. A 3D view has no way to show a picture yet, so it is
    kept for a game that wants to draw something in its place."""

    filePath: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class RecordedButton:
    """A drawButton call, with the function the 2D screen gave it."""

    x: float
    y: float
    width: float
    height: float
    color: Color255
    textColor: Color255
    textSize: float
    text: str
    function: Callable

    def contains(self, position):
        # exactly the drawn box, as drawButton counts it
        return contains(self.x, self.y, self.width, self.height, position)


class RecordedDisplay:
    """The parts of a pygame Surface that screens ask Graphik's display for."""

    def __init__(self, width, height):
        self.width, self.height = width, height

    def get_size(self):
        return (self.width, self.height)

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def fill(self, color):
        pass


class ScreenRecorder:
    """Stands in for Graphik: keeps, in order, what a screen draws (drawText,
    drawRectangle, drawButton, drawImage) instead of painting it. `items` is
    one frame's worth; reset() starts the next.

    It answers every public call Graphik has, so a screen written against
    Graphik 0.3.0 and later runs unchanged: beginFrame and endFrame (press-only
    clicks) do nothing here, because the 3D view hands a press to click()
    itself, once; getVersion is graphik's; the colour constants are Graphik's."""

    # Graphik's colour constants, so screens that read graphik.red still work
    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (200, 0, 0)
    green = (0, 200, 0)
    blue = (0, 0, 200)

    def __init__(self, width=800, height=600):
        self.gameDisplay = RecordedDisplay(width, height)
        self.items = []

    def beginFrame(self):
        """Graphik.beginFrame: nothing to snapshot, the 3D view sends clicks."""

    def endFrame(self):
        """Graphik.endFrame: nothing to do."""

    def getVersion(self):
        from .._version import __version__

        return __version__

    def resize(self, width, height):
        self.gameDisplay.width, self.gameDisplay.height = width, height

    def getGameDisplay(self):
        return self.gameDisplay

    def reset(self):
        self.items = []

    def drawText(self, text, xpos, ypos, size, color):
        self.items.append(RecordedText(str(text), xpos, ypos, size, tuple(color[:3])))

    def drawRectangle(self, xpos, ypos, width, height, color):
        self.items.append(RecordedRect(xpos, ypos, width, height, tuple(color[:3])))

    def drawButton(self, xpos, ypos, width, height, colorBox, colorText, sizeText, text, function):
        self.items.append(
            RecordedButton(xpos, ypos, width, height, tuple(colorBox[:3]), tuple(colorText[:3]),
                           sizeText, str(text), function)
        )

    def drawImage(self, filePath, xpos, ypos, width, height):
        self.items.append(RecordedImage(str(filePath), xpos, ypos, width, height))

    def images(self):
        return [item for item in self.items if isinstance(item, RecordedImage)]

    def buttons(self):
        return [item for item in self.items if isinstance(item, RecordedButton)]

    def texts(self):
        return [item.text for item in self.items if isinstance(item, RecordedText)]

    def click(self, position):
        """Runs the function of the first recorded button under `position`;
        returns whether one was hit."""
        for button in self.buttons():
            if button.contains(position):
                button.function()
                return True
        return False
