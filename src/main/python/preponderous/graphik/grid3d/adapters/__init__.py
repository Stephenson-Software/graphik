"""The adapters of grid3d's ports, one implementation per file.

| Port | Adapters |
|---|---|
| StrataLoader | BindingStrataLoader |
| SceneRenderer, EventSource, Surface | StrataEngine (desktop), RelayDisplay (browser) |
| GridRelay | PlatformRelay (pygbag), RecordingRelay (tests, recordings) |
| PageObjects | PygbagPageObjects |

Importing this package loads neither Strata, pygame nor pygbag: they are
imported when an adapter is used.
"""

from .binding_strata_loader import BindingStrataLoader
from .platform_relay import PlatformRelay
from .pygbag_page_objects import PygbagPageObjects
from .recording_relay import RecordingRelay
from .relay_display import RelayDisplay
from .strata_engine import StrataEngine

__all__ = ["BindingStrataLoader", "PlatformRelay", "PygbagPageObjects", "RecordingRelay",
           "RelayDisplay", "StrataEngine"]
