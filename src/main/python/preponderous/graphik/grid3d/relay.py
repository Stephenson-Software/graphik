"""Fetch Strata's prebuilt grid relay for a game's pygbag build.

A browser can't download GitHub release assets cross-origin, so the relay
has to be served with the game. Strata's release tarball
(strata-<version>-wasm32-emscripten.tar.gz) carries it prebuilt under
kit/grid-relay/dist/: the relay scene's .js and .wasm, strata-kit.js,
strata-loader.js, grid-relay.js and its page files. At build time, after
`pygbag --build`, run:

    python -m preponderous.graphik.grid3d.relay --strata 0.9.0 --dest src/build/web

It downloads the tarball and the release's SHA256SUMS, checks the tarball
against it, and copies kit/grid-relay/dist/ into `--dest`, next to the
page pygbag built from grid3d's template (web.templatePath()). Files that
already exist there (pygbag's own index.html, say) are left alone, so the
relay's test page never replaces the game's. Nothing of the relay is
downloaded by a player until the page's 3D toggle asks for it.

Standard library only.
"""

import argparse
import hashlib
import io
import os
import posixpath
import shutil
import sys
import tarfile
import urllib.request

RELEASES = "https://github.com/Preponderous-Software/strata/releases/download"
DIST = "kit/grid-relay/dist/"


class RelayFetchError(Exception):
    """The relay couldn't be fetched, verified or unpacked."""


def tarballName(version):
    return "strata-%s-wasm32-emscripten.tar.gz" % version


def _download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "graphik-grid3d-relay"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def expectedDigest(sums, name):
    """The SHA-256 a SHA256SUMS text gives for `name`."""
    for line in sums.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*").split("/")[-1] == name:
            return parts[0].lower()
    raise RelayFetchError("SHA256SUMS has no line for %s" % name)


def verify(data, sums, name):
    digest = hashlib.sha256(data).hexdigest()
    expected = expectedDigest(sums, name)
    if digest != expected:
        raise RelayFetchError("%s's SHA-256 is %s, SHA256SUMS says %s" % (name, digest, expected))


def extractDist(data, dest, prefix=DIST):
    """Copy the tarball's `prefix` tree into `dest`; returns (copied,
    skipped) relative paths. Existing files are skipped, and members that
    aren't plain files and directories, or would land outside `dest`, are
    refused."""
    copied, skipped = [], []
    dest = os.path.abspath(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name[2:] if member.name.startswith("./") else member.name
            if prefix in name + "/" and (".." in name.split("/") or name.startswith("/")):
                raise RelayFetchError("refusing %s: outside the relay's folder" % member.name)
            name = posixpath.normpath(name)
            # the tarball may keep everything under a top-level folder
            at = (name + "/").find(prefix)
            if at < 0 or (at and not name[:at].endswith("/")):
                continue
            relative = name[at + len(prefix):]
            if not relative:
                continue
            if relative.startswith("../") or os.path.isabs(relative) or "/../" in "/" + relative:
                raise RelayFetchError("refusing %s: outside the relay's folder" % member.name)
            target = os.path.abspath(os.path.join(dest, relative))
            if not target.startswith(dest + os.sep):
                raise RelayFetchError("refusing %s: outside %s" % (member.name, dest))
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            if not member.isfile():
                raise RelayFetchError("refusing %s: not a plain file" % member.name)
            if os.path.exists(target):
                skipped.append(relative)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.extractfile(member) as source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
            copied.append(relative)
    if not copied and not skipped:
        raise RelayFetchError("the tarball has nothing under %s" % prefix)
    return copied, skipped


def fetchRelay(version, dest, base=RELEASES, download=None):
    """Download, verify and unpack Strata `version`'s grid relay into
    `dest`. Returns (copied, skipped)."""
    download = download or _download
    name = tarballName(version)
    root = "%s/v%s/" % (base.rstrip("/"), version)
    try:
        sums = download(root + "SHA256SUMS").decode("utf-8")
        data = download(root + name)
    except OSError as error:
        raise RelayFetchError("couldn't download Strata %s's release: %s" % (version, error))
    verify(data, sums, name)
    os.makedirs(dest, exist_ok=True)
    return extractDist(data, dest)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m preponderous.graphik.grid3d.relay",
        description="Copy Strata's prebuilt grid relay next to a pygbag build.")
    parser.add_argument("--strata", required=True, help="Strata release version, e.g. 0.9.0")
    parser.add_argument("--dest", required=True, help="the pygbag output folder (build/web)")
    parser.add_argument("--base", default=RELEASES, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        copied, skipped = fetchRelay(args.strata, args.dest, args.base)
    except RelayFetchError as error:
        print("grid relay: %s" % error, file=sys.stderr)
        return 1
    print("grid relay: Strata %s, %d files copied to %s" % (args.strata, len(copied), args.dest))
    for path in skipped:
        print("grid relay: kept the existing %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
