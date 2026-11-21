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
relay's test page never replaces the game's; with --replace (after moving to
a newer Strata into a folder an older relay was copied to) the relay's own
files are replaced, and only index.html is still kept. Nothing of the relay
is downloaded by a player until the page's 3D toggle asks for it.

Standard library only.
"""

import argparse
import hashlib
import io
import os
import posixpath
import re
import shutil
import sys
import tarfile
import urllib.request

RELEASES = "https://github.com/Preponderous-Software/strata/releases/download"
DIST = "kit/grid-relay/dist/"
# A Strata release version as its tags spell them (0.9.0, 1.0.0-rc.1): it goes
# into the download URL, so nothing else is taken.
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$")
# Never replaced, even with replace=True: the game's own page.
KEEP = ("index.html",)
# The relay's dist/ is about 1.5 MB; anything far bigger is not a relay.
MAX_DIST_BYTES = 64 * 1000 * 1000


class RelayFetchError(Exception):
    """The relay couldn't be fetched, verified or unpacked."""


def tarballName(version):
    if not VERSION.match(str(version)):
        raise RelayFetchError("%r is not a Strata release version (like 0.9.0)" % (version,))
    return "strata-%s-wasm32-emscripten.tar.gz" % version


def _download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "graphik-grid3d-relay"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def expectedDigest(sums, name):
    """The SHA-256 a SHA256SUMS text gives for `name`: refused when it has
    none, more than one that disagree, or one that isn't a SHA-256."""
    found = set()
    for line in sums.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*").split("/")[-1] == name:
            found.add(parts[0].lower())
    if not found:
        raise RelayFetchError("SHA256SUMS has no line for %s" % name)
    if len(found) > 1:
        raise RelayFetchError("SHA256SUMS has different digests for %s" % name)
    digest = found.pop()
    if not re.match(r"^[0-9a-f]{64}$", digest):
        raise RelayFetchError("SHA256SUMS's digest for %s isn't a SHA-256: %r" % (name, digest))
    return digest


def verify(data, sums, name):
    digest = hashlib.sha256(data).hexdigest()
    expected = expectedDigest(sums, name)
    if digest != expected:
        raise RelayFetchError("%s's SHA-256 is %s, SHA256SUMS says %s" % (name, digest, expected))


def extractDist(data, dest, prefix=DIST, replace=False):
    """Copy the tarball's `prefix` tree into `dest`; returns (copied,
    skipped) relative paths. Existing files are skipped (with `replace`, only
    index.html is), and members that aren't plain files and directories, or
    would land outside `dest`, are refused. Every member is checked before
    anything is written, so a refused tarball leaves `dest` as it was."""
    dest = os.path.abspath(dest)
    realDest = os.path.realpath(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        plan, total = [], 0
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
            # resolved too, so a folder in `dest` that is a link elsewhere
            # can't carry a file out of it
            if not target.startswith(dest + os.sep) or not os.path.realpath(target).startswith(realDest + os.sep):
                raise RelayFetchError("refusing %s: outside %s" % (member.name, dest))
            if not member.isdir() and not member.isfile():
                raise RelayFetchError("refusing %s: not a plain file" % member.name)
            total += member.size
            if total > MAX_DIST_BYTES:
                raise RelayFetchError("refusing the tarball: over %d MB under %s"
                                      % (MAX_DIST_BYTES // 1000000, prefix))
            plan.append((member, relative, target))
        if not plan or all(member.isdir() for member, _, _ in plan):
            raise RelayFetchError("the tarball has nothing under %s" % prefix)
        copied, skipped = [], []
        for member, relative, target in plan:
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            if os.path.lexists(target) and (not replace or relative in KEEP
                                              or not os.path.isfile(target) or os.path.islink(target)):
                # with replace, only a plain file is written over: never a
                # link (which could point anywhere) or a folder
                skipped.append(relative)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.extractfile(member) as source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
            copied.append(relative)
    return copied, skipped


def fetchRelay(version, dest, base=RELEASES, download=None, replace=False):
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
    return extractDist(data, dest, replace=replace)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m preponderous.graphik.grid3d.relay",
        description="Copy Strata's prebuilt grid relay next to a pygbag build.")
    parser.add_argument("--strata", required=True, help="Strata release version, e.g. 0.9.0")
    parser.add_argument("--dest", required=True, help="the pygbag output folder (build/web)")
    parser.add_argument("--replace", action="store_true",
                        help="replace relay files already in --dest (never index.html)")
    parser.add_argument("--base", default=RELEASES, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        copied, skipped = fetchRelay(args.strata, args.dest, args.base, replace=args.replace)
    except RelayFetchError as error:
        print("grid relay: %s" % error, file=sys.stderr)
        return 1
    print("grid relay: Strata %s, %d files copied to %s" % (args.strata, len(copied), args.dest))
    for path in skipped:
        print("grid relay: kept the existing %s" % path)
    if any(path not in KEEP for path in skipped):
        print("grid relay: files of an earlier relay were kept; --replace replaces them", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
