"""RecordingRelay: a GridRelay that keeps what it is sent."""

import base64
import json

from ..wire import WireError, readHeader


class RecordingRelay:
    """A relay that keeps what it is sent: for tests, and for recording a
    game to play into the relay's test page (index.html?wire=...)."""

    def __init__(self, reducedMotion=False, state="ready"):
        self.messages, self.events, self.motion = [], [], reducedMotion
        self.status = state
        self.closed = False

    def request(self, options):
        self.options = options
        return self.status

    def state(self):
        return self.status

    def send(self, message):
        try:
            readHeader(message)
        except WireError as error:
            return error.status
        self.messages.append(bytes(message))
        return 0

    def poll(self):
        events, self.events = self.events, []
        return events

    def reducedMotion(self):
        return self.motion

    def close(self):
        self.closed = True

    def wireJson(self):
        return json.dumps([base64.b64encode(m).decode("ascii") for m in self.messages])
