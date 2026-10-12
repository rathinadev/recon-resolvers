#!/usr/bin/env python3
"""
Validate public DNS resolvers — keep only the ones that answer FAST and BEHAVE.

Seeds from a large public candidate pool, then re-checks every resolver itself so
the freshness/quality bar is ours, not inherited on faith:

  1. liveness  — must resolve known-good control domains to a real A record,
  2. anti-hijack — must return NXDOMAIN for random non-existent names (a resolver
     that hands back an address for a domain that doesn't exist is an
     ad-injector / hijacker, not a resolver).

Survivors are written to resolvers.txt. Run on a schedule by CI; the list is what
mass-DNS tooling (puredns / shuffledns / massdns / dnsx) points at.

Self-contained: only dependency is dnspython.
"""
from __future__ import annotations

import concurrent.futures as cf
import random
import string
import sys
import urllib.request

import dns.resolver

# A large, already roughly-curated public pool. We RE-validate it ourselves.
CANDIDATE_URL = "https://raw.githubusercontent.com/trickest/resolvers/main/resolvers.txt"

# Known-good domains that should always resolve to *some* A record.
CONTROL_DOMAINS = ["google.com", "cloudflare.com", "wikipedia.org"]

TIMEOUT = 1.5            # seconds per query
THREADS = 200
LIVE_REQUIRED = 2        # must resolve at least this many control domains
NXDOMAIN_CHECKS = 2      # random non-existent names that must come back NXDOMAIN
MIN_RESULTS = 50         # refuse to overwrite a good list with an implausibly tiny one


def _query_a(server: str, name: str, timeout: float = TIMEOUT) -> set[str]:
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = [server]
    r.lifetime = timeout
    r.timeout = timeout
    try:
        return {rr.address for rr in r.resolve(name, "A")}
    except Exception:
        return set()


def _nxdomain_ok(server: str) -> bool:
    """A good resolver returns NXDOMAIN for a name that doesn't exist.
    A hijacker returns an address. Timeout/SERVFAIL -> don't trust it."""
    rand = "".join(random.choices(string.ascii_lowercase, k=20))
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = [server]
    r.lifetime = TIMEOUT
    r.timeout = TIMEOUT
    try:
        r.resolve(f"{rand}.com", "A")
        return False  # got an answer for a non-existent name => hijacker
    except dns.resolver.NXDOMAIN:
        return True
    except Exception:
        return False


def is_good(server: str) -> bool:
    # Cheap reject first: one quick query kills most dead servers at 1 query, not 5.
    if not _query_a(server, CONTROL_DOMAINS[0]):
        return False
    live = 1
    for d in CONTROL_DOMAINS[1:]:
        if _query_a(server, d):
            live += 1
    if live < LIVE_REQUIRED:
        return False
    for _ in range(NXDOMAIN_CHECKS):
        if not _nxdomain_ok(server):
            return False
    return True


def fetch_candidates() -> list[str]:
    with urllib.request.urlopen(CANDIDATE_URL, timeout=30) as resp:
        text = resp.read().decode("utf-8", "replace")
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return sorted(set(out))


def main() -> int:
    candidates = fetch_candidates()
    print(f"candidates: {len(candidates)}")
    if not candidates:
        print("ERROR: empty candidate pool (network?) — keeping existing list", file=sys.stderr)
        return 1

    good: list[str] = []
    with cf.ThreadPoolExecutor(max_workers=THREADS) as ex:
        futs = {ex.submit(is_good, c): c for c in candidates}
        for fut in cf.as_completed(futs):
            try:
                if fut.result():
                    good.append(futs[fut])
            except Exception:
                pass

    good = sorted(set(good))
    print(f"validated: {len(good)} / {len(candidates)}")

    # Never clobber a working list with a broken (tiny) result — likely a CI/network blip.
    if len(good) < MIN_RESULTS:
        print(f"ERROR: only {len(good)} passed (< {MIN_RESULTS}) — keeping existing list", file=sys.stderr)
        return 1

    with open("resolvers.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(good) + "\n")
    print(f"wrote {len(good)} resolvers to resolvers.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
