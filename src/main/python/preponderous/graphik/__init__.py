from ._version import __version__

__all__ = ["Graphik", "__version__"]


# Lazily import Graphik (which pulls in pygame) only when it is actually
# accessed, so that merely importing this package -- e.g. when setuptools
# resolves the dynamic version from `_version.__version__` during an isolated
# build -- does not require pygame to be installed.
def __getattr__(name):
    if name == "Graphik":
        from .graphik import Graphik

        return Graphik
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
