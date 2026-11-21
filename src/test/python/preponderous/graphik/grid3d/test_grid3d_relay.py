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


# -- hardening


def test_a_refused_tarball_writes_nothing(tmp_path):
    # the escaping member comes last: nothing before it may have been written
    evil = tarball(DIST_FILES, extra=[("x/" + relay.DIST + "../../../../escape.js", b"bad")])
    download, _ = release(evil)
    web = tmp_path / "web"
    with pytest.raises(relay.RelayFetchError, match="refusing"):
        relay.fetchRelay("0.9.0", str(web), download=download)
    assert not web.exists() or os.listdir(web) == []


def test_links_and_devices_in_the_relay_folder_are_refused(tmp_path):
    for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            info = tarfile.TarInfo(relay.DIST + "grid-relay.js")
            info.type = kind
            info.linkname = "/etc/passwd"
            archive.addfile(info)
        with pytest.raises(relay.RelayFetchError, match="not a plain file"):
            relay.extractDist(buffer.getvalue(), str(tmp_path / "web"))


def test_a_folder_in_dest_that_links_elsewhere_cant_carry_a_file_out(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    web = tmp_path / "web"
    web.mkdir()
    os.symlink(str(elsewhere), str(web / "sub"))
    data = tarball({"sub/x.js": b"x"})
    with pytest.raises(relay.RelayFetchError, match="outside"):
        relay.extractDist(data, str(web))
    assert os.listdir(elsewhere) == []


def test_an_oversized_relay_folder_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(relay, "MAX_DIST_BYTES", 10)
    with pytest.raises(relay.RelayFetchError, match="over"):
        relay.extractDist(tarball(DIST_FILES), str(tmp_path))


def test_replace_updates_an_earlier_relay_but_never_the_games_page(tmp_path, capsys, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_bytes(b"<html>the game</html>")
    (web / "grid-relay.js").write_bytes(b"// an older relay")
    download, _ = release(tarball(DIST_FILES))
    monkeypatch.setattr(relay, "_download", download)
    assert relay.main(["--strata", "0.9.0", "--dest", str(web)]) == 0
    assert (web / "grid-relay.js").read_bytes() == b"// an older relay"
    assert "--replace replaces them" in capsys.readouterr().err
    assert relay.main(["--strata", "0.9.0", "--dest", str(web), "--replace"]) == 0
    assert (web / "grid-relay.js").read_bytes() == b"// relay"
    assert (web / "index.html").read_bytes() == b"<html>the game</html>"


@pytest.mark.parametrize("version", ["../../evil", "0.9", "v0.9.0", "0.9.0/../x", "", "0.9.0 "])
def test_only_a_release_version_goes_into_the_download_url(version):
    with pytest.raises(relay.RelayFetchError, match="not a Strata release version"):
        relay.fetchRelay(version, "unused", download=lambda url: pytest.fail("downloaded %s" % url))


def test_sha256sums_that_disagree_or_arent_digests_are_refused():
    name = relay.tarballName("0.9.0")
    with pytest.raises(relay.RelayFetchError, match="different digests"):
        relay.expectedDigest("%s  %s\n%s  dist/%s\n" % ("a" * 64, name, "b" * 64, name), name)
    with pytest.raises(relay.RelayFetchError, match="isn't a SHA-256"):
        relay.expectedDigest("abc  %s\n" % name, name)
    assert relay.expectedDigest("%s *%s\n" % ("A" * 64, name), name) == "a" * 64
