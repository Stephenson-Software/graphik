"""PlatformRelay: the page's grid relay through pygbag's platform.window,
which passes strings, so options go as JSON and messages as base64."""

import base64
import json

from ..errors import Unavailable
from .pygbag_page_objects import PygbagPageObjects


class PlatformRelay:
    """The page's window.StrataGridRelay, through pygbag's platform.window."""

    def __init__(self, relay=None, page=None):
        if relay is None:
            relay = (page or PygbagPageObjects()).get("StrataGridRelay")
            if relay is None:
                raise Unavailable(
                    "this page has no 3D view (grid-relay.js isn't loaded; on graphik's "
                    "template it loads once the 3D toggle is on, when wants3D() turns true)"
                )
        self.js = relay

    def request(self, options):
        return str(self.js.request(json.dumps(options)))

    def state(self):
        return str(self.js.state())

    def send(self, message):
        return int(self.js.send(base64.b64encode(message).decode("ascii")))

    def poll(self):
        return json.loads(str(self.js.poll()))

    def reducedMotion(self):
        return bool(int(self.js.reducedMotion()))

    def close(self):
        self.js.close()
