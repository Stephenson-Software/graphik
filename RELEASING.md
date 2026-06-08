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
   - smoke-tests the built wheel (install + canonical import + version check),
   - publishes to PyPI via Trusted Publishing.

The tag must equal `v` + `__version__` (e.g. `__version__ = "0.2.0"` → tag
`v0.2.0`), or the build fails fast before anything is published.

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
