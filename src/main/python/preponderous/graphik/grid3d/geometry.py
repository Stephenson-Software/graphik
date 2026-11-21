"""Where things are on screen for a 3D grid view: insets, the camera that
fits the board between them, picking and projection. Shared by Grid3DView
and Grid3DWebView, with the projection and sun both send to Strata. Pure
Python: no Strata, no pygame.
"""

from .pick import cellScreenPosition, pickCell, projectToScreen

# Grid3DView's lighting and projection, sent with every VIEW so the relay
# draws what the desktop draws.
SUN_DIRECTION = (-0.45, 0.85, 0.35)
NEAR_PLANE, FAR_PLANE = 0.3, 200.0


class ViewGeometry:
    """Where things are on screen, for a view with `board`, `width` and
    `height` (Grid3DView and Grid3DWebView)."""

    # pixels at the top and bottom of the window kept clear of the board
    # (setInsets); None for fitCamera's own framing
    insets = None

    def setInsets(self, top=None, bottom=None):
        """Keeps `top` pixels at the top of the window (a HUD) and `bottom`
        at the bottom (a bar of touch keys) clear of the board: the camera
        fits the board in the space between. None for both (the default)
        frames the board as fitCamera does for the window's shape. Returns
        whether anything changed."""
        insets = None if top is None and bottom is None else (top or 0, bottom or 0)
        if insets == self.insets:
            return False
        self.insets = insets
        return True

    def insetFractions(self):
        """(top, bottom) as fractions of the window's height, or (None,
        None) when no insets are set."""
        if self.insets is None or not self.height:
            return None, None
        top, bottom = self.insets
        return top / float(self.height), bottom / float(self.height)

    def camera(self):
        """The camera the current board is drawn with at this window size."""
        if self.board is None:
            raise RuntimeError("setBoard() must come before the camera")
        top, bottom = self.insetFractions()
        return self.board.camera(self.width / float(self.height), top=top, bottom=bottom)

    def pickCell(self, x, y):
        """The board (column, row) under window pixel (x, y), or None."""
        if self.board is None:
            return None
        return pickCell(self.camera(), self.board, x, y, self.width, self.height)

    def projectToScreen(self, point):
        """Where world point (x, y, z) lands in the window, or None."""
        return projectToScreen(self.camera(), point, self.width, self.height)

    def cellScreenPosition(self, column, row, y=0.0):
        """Where the middle of a cell, `y` above the bed, lands in the window."""
        return cellScreenPosition(self.camera(), self.board, column, row,
                                  self.width, self.height, y)
