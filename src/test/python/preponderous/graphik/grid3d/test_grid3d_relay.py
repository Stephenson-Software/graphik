"""Fetching Strata's prebuilt grid relay for a pygbag build (relay.py),
against tarballs made here: no network."""

import hashlib
import io
import os
import tarfile

import pytest

from preponderous.graphik.grid3d import relay

DIST_FILES = {
    "grid-relay-scene.js": b"// scene",
    "grid-relay-scene.wasm": b"\0asm",
    "grid-relay.js": b"// relay",
    "strata-kit.js": b"// kit",
    "strata-loader.js": b"// loader",
    "index.html": b"<html>relay test page</html>",
}


def tarball(files, top="strata-0.9.0-wasm32-emscripten/", extra=()):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        def add(name, data):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        add(top + "lib/libstrata.a", b"not the relay")
        add(top + "kit/grid-relay/main.cpp", b"// source")
        for name, data in files.items():
            add(top + relay.DIST + name, data)
        for name, data in extra:
            add(name, data)
    return buffer.getvalue()


def release(data, version="0.9.0", digest=None):
    name = relay.tarballName(version)
    sums = "%s  %s\n%s  other.zip\n" % (digest or hashlib.sha256(data).hexdigest(), name, "0" * 64)
    files = {"SHA256SUMS": sums.encode(), name: data}
    calls = []

    def download(url):
        calls.append(url)
        return files[url.rsplit("/", 1)[1]]

    return download, calls


def test_the_relay_is_downloaded_verified_and_copied_next_to_the_page(tmp_path):
    download, calls = release(tarball(DIST_FILES))
    web = tmp_path / "build" / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_bytes(b"<html>the game</html>")
    copied, skipped = relay.fetchRelay("0.9.0", str(web), download=download)
    assert calls == [relay.RELEASES + "/v0.9.0/SHA256SUMS",
                     relay.RELEASES + "/v0.9.0/strata-0.9.0-wasm32-emscripten.tar.gz"]
    assert sorted(copied) == sorted(n for n in DIST_FILES if n != "index.html")
    assert skipped == ["index.html"]
    # the game's page is kept; only the relay's files are added
    assert (web / "index.html").read_bytes() == b"<html>the game</html>"
    assert (web / "grid-relay-scene.wasm").read_bytes() == b"\0asm"
    assert not (web / "main.cpp").exists() and not (web / "libstrata.a").exists()


def test_a_tarball_that_doesnt_match_sha256sums_is_refused(tmp_path):
    download, _ = release(tarball(DIST_FILES), digest="ab" * 32)
    with pytest.raises(relay.RelayFetchError, match="SHA-256"):
        relay.fetchRelay("0.9.0", str(tmp_path), download=download)
    assert os.listdir(tmp_path) == []


def test_sha256sums_without_the_tarball_is_refused():
    with pytest.raises(relay.RelayFetchError, match="no line"):
        relay.expectedDigest("00  something-else.tar.gz\n", relay.tarballName("0.9.0"))


def test_a_tarball_without_the_relay_is_refused(tmp_path):
    download, _ = release(tarball({}))
    with pytest.raises(relay.RelayFetchError, match="nothing under"):
        relay.fetchRelay("0.9.0", str(tmp_path), download=download)


def test_members_escaping_the_destination_are_refused(tmp_path):
    evil = tarball(DIST_FILES, extra=[("x/" + relay.DIST + "../../../../escape.js", b"bad")])
    download, _ = release(evil)
    with pytest.raises(relay.RelayFetchError, match="refusing"):
        relay.fetchRelay("0.9.0", str(tmp_path / "web"), download=download)
    assert not (tmp_path / "escape.js").exists()


def test_the_command_line_copies_the_relay_and_reports_failures_plainly(tmp_path, capsys, monkeypatch):
    download, _ = release(tarball(DIST_FILES))
    monkeypatch.setattr(relay, "_download", download)
    assert relay.main(["--strata", "0.9.0", "--dest", str(tmp_path)]) == 0
    assert "6 files copied" in capsys.readouterr().out
    assert relay.main(["--strata", "0.9.0", "--dest", str(tmp_path)]) == 0
    assert "kept the existing grid-relay.js" in capsys.readouterr().out

    def offline(url):
        raise OSError("no network")

    monkeypatch.setattr(relay, "_download", offline)
    assert relay.main(["--strata", "0.9.0", "--dest", str(tmp_path)]) == 1
    assert "no network" in capsys.readouterr().err
