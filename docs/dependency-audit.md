# Dependency Supply-Chain Audit

Audit date: 2026-07-13

This audit was completed before the new packages were installed. Versions are locked in
`uv.lock` and `web/package-lock.json`.

## Sources and checks

- Package identity and release metadata came from PyPI and the npm registry.
- Repository ownership, maintainers, license, engine support, and release age were checked.
- Direct packages and every resolved PyPI package were queried against OSV.
- The complete npm lockfile was checked with `npm audit`.
- npm integrity hashes and available SLSA provenance attestations were verified in registry
  metadata.
- npm lifecycle scripts were disabled during installation.
- Current usage guidance came from Context7's official-library sources.

## Python additions

| Package | Version | License | Upstream | OSV findings |
|---|---:|---|---|---:|
| Psycopg | 3.3.4 | LGPL-3.0-only | `psycopg/psycopg` | 0 |
| Psycopg Binary | 3.3.4 | LGPL-3.0-only | `psycopg/psycopg` | 0 |
| croniter | 6.2.4 | MIT | `pallets-eco/croniter` | 0 |
| HTTPX2 | 2.5.0 | BSD-3-Clause | `pydantic/httpx2` | 0 |
| pytest | 9.1.1 | MIT | `pytest-dev/pytest` | 0 |
| Pygments | 2.20.0 | BSD-2-Clause | `pygments/pygments` | 0 |

The resolved lock contains 30 PyPI packages and returned no OSV findings. Pygments is constrained to
`>=2.20.0` because the prospective `2.19.2` release had
`GHSA-5239-wwwm-4pmq`; that vulnerable version was rejected before installation.

HTTPX2 replaces the deprecated HTTPX integration used by Starlette 1.2's current `TestClient`.
Context7 confirmed that HTTPX2 is the Pydantic-maintained successor and preserves the public client
API under the new package name.

## Frontend additions

| Package | Version | License | Upstream | OSV findings |
|---|---:|---|---|---:|
| React | 19.2.7 | MIT | `facebook/react` | 0 |
| React DOM | 19.2.7 | MIT | `facebook/react` | 0 |
| TypeScript | 6.0.2 | Apache-2.0 | `microsoft/TypeScript` | 0 |
| Vite | 8.1.4 | MIT | `vitejs/vite` | 0 |
| Vite React plugin | 6.0.3 | MIT | `vitejs/vite-plugin-react` | 0 |
| Playwright Test | 1.61.1 | Apache-2.0 | `microsoft/playwright` | 0 |
| React type definitions | 19.2.17 | MIT | `DefinitelyTyped` | 0 |
| React DOM type definitions | 19.2.3 | MIT | `DefinitelyTyped` | 0 |

The npm lock contains 58 cross-platform package entries. `npm audit` returned zero vulnerabilities.
Every artifact resolves from `registry.npmjs.org`. The only declared install scripts belong to the
optional macOS-only `fsevents` packages. Installation used `--ignore-scripts`, and WSL does not
select those packages.

## PostgreSQL image

The Compose service uses the Docker Official Image and is pinned to the multi-platform digest:

```text
postgres:18.2-alpine
sha256:035b9ab53cfa147d7202b61f5f7782b939ae815b7d6bc81c96b7b42ff1fca950
```

OCI metadata links the image to `docker-library/postgres` revision
`2c9ee2611e4988031a207ec97b69ab213b20b95c`. The image includes registry attestation manifests.
Docker Scout could not perform an authenticated vulnerability query in this environment, so the
immutable official-image digest and upstream PostgreSQL security notices remain the control for the
container itself.
