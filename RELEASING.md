# Releasing graphik

graphik is released as **git tags**. It isn't published to PyPI. Consumers
install a release from the tag's source archive on GitHub:

```
graphik @ https://github.com/Stephenson-Software/graphik/archive/refs/tags/v0.3.0.zip
```

pip downloads the archive and builds the wheel locally with setuptools, using
[`pyproject.toml`](pyproject.toml). This needs access to GitHub but not `git`,
which matters for players installing a game from source on Windows. (The
`git+https://...@v0.3.0` form also works where `git` is installed.)

## Cutting a release

1. Bump the single version source,
   [`src/main/python/preponderous/graphik/_version.py`](src/main/python/preponderous/graphik/_version.py)
   (`__version__`). Every other version reference is derived from it. Use three
   dot-separated parts (`0.3.0`), with no `.dev` suffix for a release.
2. Merge the bump to `main`, with green CI. The *Install from a release
   archive* job in `test.yml` has already installed and drawn with an archive
   built the same way as the tag's.
3. Tag the merge commit as `v` + `__version__`, push the tag, and create a
   GitHub release for it:

   ````bash
   git tag -a v0.3.0 -m "graphik 0.3.0" <merge-sha>
   git push origin v0.3.0
   gh release create v0.3.0 --verify-tag --notes "<changes>"
   ````

4. Check that the tag installs and imports in a clean environment:

   ````bash
   python -m venv /tmp/g && /tmp/g/bin/pip install "graphik @ https://github.com/Stephenson-Software/graphik/archive/refs/tags/v0.3.0.zip"
   SDL_VIDEODRIVER=dummy /tmp/g/bin/python -c "from preponderous.graphik import Graphik, __version__; print(__version__)"
   ````

5. Open a pull request in each repository in the README's
   [Dependents](README.md#dependents) list that bumps the tag in its
   `requirements.txt`.

A released tag must never be moved or deleted: consumers' installs resolve it
by name, so moving it would change what they install without any change on
their side.

## Earlier tags

`v0.1`, `0.2.0` and `0.3.0.dev20260808` were pushed before this process. The
last two have no `v` prefix. `v0.3.0` is the first release under it.

## PyPI (not in use)

[`.github/workflows/publish.yml`](.github/workflows/publish.yml) can build and
publish to PyPI with Trusted Publishing, but it runs only when started by hand
(`workflow_dispatch`). No PyPI project is set up. To turn it on: claim the
`graphik` name on PyPI (`preponderous-graphik` as a fallback), add a Trusted
Publisher for owner `Stephenson-Software`, repository `graphik`, workflow
`publish.yml`, environment `pypi`, create the `pypi` environment in this
repository's settings, then run the workflow against a `v` tag.
