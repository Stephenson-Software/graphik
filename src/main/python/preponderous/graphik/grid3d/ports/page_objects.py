from typing import Protocol, runtime_checkable


@runtime_checkable
class PageObjects(Protocol):
    """The page's JS objects, by name.

    get(name) returns window.<name> (the template's Graphik3D, the relay's
    StrataGridRelay), or None when there is no page (not in a browser) or no
    such object on it. Never raises, never blocks; asked again on every
    call, so a page that loads a script later is seen.
    """

    def get(self, name):
        ...
