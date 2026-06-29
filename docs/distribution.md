# Distributing agent-core (making emission always-on)

Today the loops emit agent-core records **optionally**: they import `agent_core` via
`importlib` only when `HYRULE_*_AGENT_CORE_TRACE` is set, and `agent-core` is **not** a
declared dependency. That means zero CI/auth changes, but emission is off until both the
flag and the package are present.

To make emission **always-on**, a loop must declare `agent-core` as a real dependency. The
only real obstacle is **auth**: `AS215932/agent-core` is private, so any consumer (and its
CI) must be able to fetch it. The options below trade off effort vs. infra.

## The release artifact

`.github/workflows/release.yml` builds an sdist + wheel and publishes a **GitHub Release**
on any `v*` tag (e.g. `v0.1.0`). This gives every version a versioned, downloadable
artifact without standing up a server.

## Adoption options (pick one)

### A. uv git source pin — *recommended first step*
In a loop's `pyproject.toml`:
```toml
dependencies = ["agent-core"]

[tool.uv.sources]
agent-core = { git = "https://github.com/AS215932/agent-core", tag = "v0.1.0" }
```
- Pros: no index server; version-pinned; reproducible via `uv.lock`.
- Cons: private repo → CI must authenticate the git fetch. On the **self-hosted
  `hyrule-public-pr` runners** this is a GitHub App/token with **read-only** access to
  `agent-core`; on GitHub-hosted runners (e.g. knowledge `validate`) it needs a secret
  (a fine-grained PAT or App token) exposed to `uv`.

### B. GitHub Release wheel + `--find-links`
Install the published wheel directly:
```
uv pip install --find-links https://github.com/AS215932/agent-core/releases/download/v0.1.0 agent-core
```
- Same private-repo auth requirement as A; less reproducible than a locked git source.

### C. Hosted private index (pypiserver / devpi) on internal infra
A real PyPI-compatible index behind the AS215932 network.
- Pros: the "always-on internal index" model; clean `index-url`.
- Cons: provisioning + hosting + auth + CI network access. Defer unless several private
  packages need it.

### D. Make `agent-core` public — *simplest if acceptable*
`agent-core` contains only generic framework contracts and adapters — **no secrets, no
infra topology** (fixtures use placeholder hosts). Making the repo public removes the auth
problem entirely; options A/B then need no tokens, and a future PyPI publish becomes trivial.
- Decision for the owner: is publishing the framework scaffolding publicly acceptable?

## Recommendation

1. Tag `v0.1.0` now (this PR adds the release workflow) so a versioned artifact exists.
2. Keep loops on **optional** emission until a distribution choice is made.
3. Choose **D (public)** if acceptable — then adopt **A (uv git source)** in each loop with
   zero CI-auth work. Otherwise adopt **A** with a read-only deploy token. Revisit **C**
   only when multiple private packages justify an index.

Adoption is per-loop and reversible: flip a loop to a hard dependency in its own PR, run its
gate, and the flag-gated emission becomes always-on for that loop.
