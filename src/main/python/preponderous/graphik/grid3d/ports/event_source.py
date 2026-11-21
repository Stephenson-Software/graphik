from typing import Protocol, runtime_checkable


@runtime_checkable
class EventSource(Protocol):
    """The input that has arrived since the last poll.

    Returns a list, oldest first, empty when nothing came; never blocks.
    The events keep their backend's shape (the desktop binding's own event
    objects; the relay's events.Event): both carry Strata's `type` numbers
    and fields, which is what games and events.toPygameEvents read.
    """

    def poll(self):
        ...
