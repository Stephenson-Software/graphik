"""BindingStrataLoader: opens a StrataEngine through the strata-engine
binding (`graphik[strata]`), which loads libstrata: a released build,
downloaded once, checked against its pinned SHA-256 and cached, or the
local build STRATA_LIBRARY points at."""

import os
import sys

from ..errors import Unavailable
from ..geometry import SUN_DIRECTION
from .strata_engine import StrataEngine

STRATA_VERSION = "0.8.0"
STRATA_PLATFORMS = ("linux", "win32")
INSTALL_HINT = "pip install 'graphik[strata]'"


def loadStrata(platform=None):
    """Import the binding and load libstrata; raise Unavailable if either fails."""
    platform = sys.platform if platform is None else platform
    if platform not in STRATA_PLATFORMS and not os.environ.get("STRATA_LIBRARY"):
        raise Unavailable("Strata has no library for this system (%s)" % platform)
    # Headless rendering without a GPU driver (CI, WSL) goes through Mesa's
    # software rasteriser; harmless where a GPU exists.
    os.environ.setdefault("GALLIUM_DRIVER", "llvmpipe")
    try:
        import strata
    except ImportError:
        raise Unavailable(
            "the strata-engine package isn't installed (%s)" % INSTALL_HINT
        )
    try:
        if os.environ.get("STRATA_LIBRARY"):
            return strata, strata.load()
        return strata, strata.load_release(STRATA_VERSION)
    except Exception as error:  # download failed, checksum mismatch, bad library
        raise Unavailable("the Strata library couldn't be loaded: %s" % error)


class BindingStrataLoader:
    """The desktop's StrataLoader."""

    def open(self, width, height, title, headless):
        if headless and sys.platform.startswith("linux"):
            # Linux renders headless through EGL with no window. On Windows the
            # headless engine is a hidden SDL window, which the dummy driver
            # can't create, so it is only forced here.
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        strata, lib = loadStrata()
        surface = strata.SURFACE_HEADLESS if headless else strata.SURFACE_WINDOW
        try:
            engine = strata.Engine(
                lib, width, height, surface=surface, title=None if headless else title
            )
        except Exception as error:  # no display, no GPU driver
            raise Unavailable("no Strata window could be opened: %s" % error)
        lighting = lib.lighting_defaults(strata.LIGHTING_SUN)
        lighting.shadow_distance = 40.0
        lighting.fog = 0
        engine.set_lighting(lighting)
        engine.set_sun_direction(SUN_DIRECTION)
        return StrataEngine(strata, lib, engine)
