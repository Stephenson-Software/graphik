"""Screen text in Strata's built-in font: measuring, cutting, wrapping and
centring it.

Strata draws screen text in an 8 x 8 bitmap font scaled to a Label's
`pixelSize`: every character is a square cell exactly pixelSize wide and
tall (strata.h, StrataText), so a line of n characters is n * pixelSize
pixels wide. A character outside printable ASCII shows as one '?', still one
cell, and a newline starts the next line pixelSize lower. Pure Python.
"""

from .scene import TEXT_COLOR, Label, fitText

__all__ = ["measureText", "fitText", "wrapText", "centredLabel"]


def measureText(text, pixelSize):
    """How wide `text` is drawn at `pixelSize`, in pixels: its longest line's
    characters times pixelSize."""
    # a NUL draws nothing: both backends drop it (view.labelBytes, web._labelText)
    return max(len(line) for line in str(text).replace("\0", "").split("\n")) * pixelSize


def wrapText(text, maxWidth, pixelSize):
    """Word-wrap `text` (a string, or a list of lines) to lines no wider
    than `maxWidth` pixels at `pixelSize`. Words are split on single spaces
    and packed greedily; an empty line stays an empty line, and a word too
    wide for any line is left whole on a line of its own rather than cut or
    dropped. Newlines in a string start new lines. Returns the lines."""
    lines = text.split("\n") if isinstance(text, str) else list(text)
    wrapped = []
    for line in lines:
        if not line:
            wrapped.append(line)
            continue
        current = ""
        for word in line.split(" "):
            candidate = word if not current else current + " " + word
            if current and measureText(candidate, pixelSize) > maxWidth:
                wrapped.append(current)
                current = word
            else:
                current = candidate
        wrapped.append(current)
    return wrapped


def centredLabel(text, x, y, pixelSize, color=TEXT_COLOR, rise=0.5):
    """A Label centred across x, as graphik's 2D drawText centres its text.
    `rise` places it vertically: its top is `rise * pixelSize` above y, so
    0.5 centres its cells on y, 0.45 centres the ink of most glyphs on y
    (capitals fill the top seven of the font's eight rows), and 0 puts its
    top at y."""
    return Label(text, x - measureText(text, pixelSize) / 2.0, y - pixelSize * rise,
                 pixelSize, color)
