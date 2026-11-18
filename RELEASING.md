# Releasing graphik

graphik is published to [PyPI](https://pypi.org/) via **Trusted Publishing**
(OIDC) — no API token is stored in this repository. Publishing is automated by
[`.github/workflows/publish.yml`](.github/workflows/publish.yml), which runs
when a version tag (`vX.Y.Z`) is pushed.

## One-time setup (maintainer)

These steps are prerequisites for the workflow to succeed and are done outside
this repository:

1. **Claim the project name on PyPI.** Register `graphik` (the
   [`pyproject.toml`](pyproject.toml) `name`). `preponderous-graphik` is the
   namespaced fallback if the name is unavailable.
2. **Configure a Trusted Publisher** on the PyPI project pointing at this repo:
   - Owner: `Stephenson-Software`
   - Repository: `graphik`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`
3. **Create a GitHub environment** named `pypi` (Settings → Environments). An
   optional required-reviewer rule can be added there to gate each release.

## Cutting a release

1. Bump the single version source —
   [`src/main/python/preponderous/graphik/_version.py`](src/main/python/preponderous/graphik/_version.py)
   (`__version__`). Every other version reference is derived from it.
2. Commit the bump and merge it to `main`.
3. Tag the release commit and push the tag:

   ````bash
   git tag v0.2.0
   git push origin v0.2.0
   ````

4. The `Publish to PyPI` workflow then:
   - verifies the tag matches `__version__` (a mismatch fails the build),
   - builds the sdist and wheel,
   - smoke-tests the built wheel: installs it, runs `import preponderous.graphik`,
     and checks `__version__` against the tag. `Graphik` itself is imported
     lazily on first access, so this step never loads `graphik.py` or
     `pygame` — a wheel with a missing or broken `graphik.py`, or without a
     working `pygame` dependency, would still pass it
     (tracked in
     [#46](https://github.com/Stephenson-Software/graphik/issues/46)),
   - publishes to PyPI via Trusted Publishing.

The tag must equal `v` + `__version__` (e.g. `__version__ = "0.2.0"` → tag
`v0.2.0`), and `__version__` must have at least three dot-separated parts,
because the trigger in `publish.yml` is the glob `v*.*.*`, which needs two dots
after the `v`. A tag that matches the trigger but whose version does not match
`__version__` fails the build before anything is published. A tag that does
not match the trigger fails silently instead: the workflow never runs and
nothing reports the missed release. That covers a tag **without** the `v`
prefix, and also a `v`-prefixed tag with fewer than three parts such as
`v1.0` — even when it equals `v` + `__version__`. (The `v0.1` tag on this
repository is of that shape, and would not trigger the workflow either.) The `0.2.0` and
`0.3.0.dev20260808` tags were pushed that way, so the publish workflow has never
run (tracked in
[#34](https://github.com/Stephenson-Software/graphik/issues/34)).

## Installing (after the first publish)

Once the package is live on PyPI, consumers can replace their vendored copies
with a versioned dependency:

````bash
pip install graphik
````

```python
from preponderous.graphik import Graphik
```

Migrating the existing consumers (Roam, Apex, Ophidian, Patchwork, Tic-Tak-Toe)
off their vendored copies is tracked as follow-up work in the consumer repos.
