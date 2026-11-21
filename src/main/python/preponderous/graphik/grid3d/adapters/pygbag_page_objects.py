"""PygbagPageObjects: the page's JS objects through pygbag's
platform.window, asked again on every call."""

import sys


class PygbagPageObjects:
    """window.<name> under pygbag, or None (not in a browser, or no such
    object on the page)."""

    def get(self, name):
        if sys.platform != "emscripten":
            return None
        import platform  # pygbag's, not the standard library's

        return getattr(platform.window, name, None)
