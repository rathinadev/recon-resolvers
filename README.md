# recon-resolvers

A continuously-validated list of public **DNS resolvers** — the ones that answer
**fast** and **behave correctly** (dead, poisoned, and hijacking/ad-injecting
servers removed).

[`resolvers.txt`](resolvers.txt) is regenerated on an **hourly** CI schedule and
committed automatically — in practice every few hours, since GitHub Actions scheduling
is best-effort (which is plenty; resolvers don't go stale that fast). Point your mass-DNS tooling
(`puredns`, `shuffledns`, `massdns`, `dnsx`, …) at the raw file:

```
https://raw.githubusercontent.com/rathinadev/recon-resolvers/main/resolvers.txt
```

## Why

A mass-DNS run is only as good as its resolver list. Dead resolvers silently drop
answers and poisoned ones return garbage, so a stale list quietly corrupts your
results. This repo keeps a known-good set fresh automatically.

## How it works

[`validate.py`](validate.py):

1. pulls a large candidate pool from a public source,
2. keeps only resolvers that resolve known-good control domains to a real answer
   (**liveness**),
3. drops any resolver that returns an address for a random non-existent domain —
   the tell of a hijacking / ad-injecting resolver (**anti-hijack**),
4. refuses to overwrite a good list with an implausibly small result (CI/network
   blip protection), and writes the survivors to `resolvers.txt`.

The scheduled commit is made by `github-actions[bot]`, not a person.

## Use it

Free to use — see [`LICENSE`](LICENSE). No warranty; validate for your own use case.

## Hardening (optional)

For supply-chain-pinned CI, pin the GitHub Actions to commit SHAs instead of the
`@v4` / `@v5` major tags.
