"""Errors a grid3d view raises for a reason a player can act on."""


class Unavailable(Exception):
    """The 3D view can't run here. The message says why, in plain words."""
