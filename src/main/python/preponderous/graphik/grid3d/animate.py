"""Smooth piece movement between game ticks.

A game moves pieces a whole cell per tick; the screen redraws many times in
between. Animator remembers where each piece was drawn and slides it to its
new cell over one tick, so motion is smooth at any frame rate while the game
only reports cell positions. Pure Python: positions are world (x, z) pairs.
"""


def lerp(a, b, t):
    return a + (b - a) * t


def interpolatePosition(start, end, alpha):
    """World (x, z) a fraction `alpha` (clamped to 0-1) of the way from start
    to end."""
    alpha = 0.0 if alpha < 0.0 else 1.0 if alpha > 1.0 else alpha
    return (lerp(start[0], end[0], alpha), lerp(start[1], end[1], alpha))


class Animator:
    """Tracks pieces by id and gives each one's position at a given time.

    A piece slides from where it was last drawn to the centre of its new cell
    over `tickSeconds`. It jumps instead when it is new, when it opted out
    (Piece.interpolate is False), when it moved further than `maxSlideCells`
    in one tick (a teleport or wrap-around would otherwise slide across the
    board), when reducedMotion is on, or when the whole tick is a snap (a
    restart or a new level, where nothing should slide from the old board).
    """

    def __init__(self, cellCenter, reducedMotion=False, maxSlideCells=1.5):
        self.cellCenter = cellCenter
        self.reducedMotion = reducedMotion
        self.maxSlideCells = maxSlideCells
        self.tracks = {}  # id -> (start, end)
        self.startedAt = 0.0
        self.tickSeconds = 0.0

    def update(self, pieces, now, tickSeconds, snap=False):
        """Take this tick's pieces; `now` is a monotonic time in seconds.
        `snap=True` puts every piece straight on its cell."""
        current = {} if snap else self.positions(now)
        tracks = {}
        for piece in pieces:
            end = self.cellCenter(piece.column, piece.row)
            start = current.get(piece.id)
            # how far it moved is measured cell to cell, not from where it is
            # drawn: a tick that comes before the last slide finished is
            # still a one-cell step, and still slides
            previous = self.tracks.get(piece.id, (None, None))[1]
            if (
                start is None
                or self.reducedMotion
                or not piece.interpolate
                or abs(end[0] - previous[0]) + abs(end[1] - previous[1])
                > self.maxSlideCells
            ):
                start = end
            tracks[piece.id] = (start, end)
        self.tracks = tracks
        self.startedAt = now
        self.tickSeconds = max(0.0, tickSeconds)

    def alpha(self, now):
        if self.tickSeconds <= 0.0:
            return 1.0
        return (now - self.startedAt) / self.tickSeconds

    def positions(self, now):
        """id -> world (x, z) of every tracked piece at time `now`."""
        alpha = self.alpha(now)
        return {
            pieceId: interpolatePosition(start, end, alpha)
            for pieceId, (start, end) in self.tracks.items()
        }

    def settled(self, now):
        """True once every piece has reached its cell."""
        return self.alpha(now) >= 1.0
