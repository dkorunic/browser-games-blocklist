#!/usr/bin/env python3
"""Maintainer for the AdGuard browser-game blocklist (stdlib only, no deps).

Subcommands:
  validate        parse + lint: syntax, cross-tier dupes, PaaS-apex collateral,
                  non-normalized lines. Exit non-zero if hard errors found.
  normalize       idempotent rewrite: global dedup + coerce every block rule to
                  ||domain^ + version bump. Preserves comments and curated order.
  merge           add domains to a named tier, preserving order + comments.
  check-liveness  DNS-resolve every domain; report unresolved candidates only.
  stats           per-tier rule counts.

Design invariants (why, not just what):
  * Order within a tier is CURATED (rough prominence), so normalize does NOT sort
    by default; it only dedups + fixes syntax. --sort forces registrable-suffix
    ordering when you explicitly want it.
  * Dead-domain handling NEVER deletes. getaddrinfo cannot distinguish NXDOMAIN
    from SERVFAIL/timeout, and Cloudflare/geo-fencing yields false negatives, so
    check-liveness reports and you decide (quarantine under a '! DEAD (verify)'
    comment rather than dropping).
  * PaaS / shared-hosting apexes (github.io, netlify.app, ...) are refused on
    merge and flagged on validate: an apex ||github.io^ is catastrophic collateral.
"""
from __future__ import annotations
import argparse
import datetime
import re
import sys

# --- classification -----------------------------------------------------------

# Tier key -> distinctive substring in that tier's banner comment.
TIER_KEYWORDS = {
    "portals":     "TIER 1",
    "aggregators": "AGGREGATOR",
    "io":          ".io",
    "unblocked":   "unblocked",
    "cloud":       "Cloud",
}

# Multi-tenant apexes: blocking the apex nukes unrelated tenants. Never add as
# ||apex^. Individual subdomains (||foo.github.io^) are fine and not flagged.
PAAS_APEX = {
    "github.io", "gitlab.io", "netlify.app", "vercel.app", "pages.dev",
    "onrender.com", "render.com", "repl.co", "replit.dev", "glitch.me",
    "web.app", "firebaseapp.com", "surge.sh", "herokuapp.com", "amplifyapp.com",
    "cloudfront.net", "sites.google.com", "google.com", "weebly.com",
    "wixsite.com", "workers.dev", "r2.dev", "deno.dev", "fly.dev", "appspot.com",
    "azurewebsites.net", "pythonanywhere.com", "000webhostapp.com",
    "neocities.org", "itch.zone", "framer.app", "webflow.io",
}

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)

# --- parsing ------------------------------------------------------------------


def parse_segments(text):
    """Split into ordered [(kind, [lines])] where kind in {'other','rules'}.
    'other' = comments/blank (verbatim); 'rules' = consecutive rule lines."""
    segments, cur_kind, cur = [], None, []
    for line in text.splitlines():
        s = line.strip()
        kind = "rules" if (s and not s.startswith("!")) else "other"
        if kind != cur_kind:
            if cur:
                segments.append((cur_kind, cur))
            cur_kind, cur = kind, []
        cur.append(line)
    if cur:
        segments.append((cur_kind, cur))
    return segments


def extract_domain(rule):
    """(domain, True) for a simple host-block rule; (None, False) if opaque
    (exception/modifier/cosmetic) or unparseable."""
    r = rule.strip()
    if not r:
        return None, False
    # opaque AdGuard rules we must not rewrite: exceptions, modifiers, cosmetic.
    if r.startswith("@@") or "#" in r or "$" in r:
        return None, False
    # hosts-file style "0.0.0.0 domain" / "127.0.0.1 domain"
    m = re.match(r"^(?:0\.0\.0\.0|127\.0\.0\.1)\s+(\S+)$", r)
    if m:
        r = m.group(1)
    # ||domain^ / ||domain
    m = re.match(r"^\|\|([^\^/]+)\^?$", r)
    if m:
        r = m.group(1)
    r = re.sub(r"^[a-z][a-z0-9+.-]*://", "", r)  # strip scheme
    r = r.split("/")[0].split("?")[0]            # strip path/query
    r = r.lower().strip().rstrip(".")
    if r.startswith("www."):
        r = r[4:]
    if DOMAIN_RE.match(r):
        return r, True
    return None, False


def canon(domain):
    return f"||{domain}^"


# --- operations ---------------------------------------------------------------


def collect(segments):
    """Yield (segment_index, line_index, raw, domain_or_None, is_simple)."""
    for si, (kind, lines) in enumerate(segments):
        if kind != "rules":
            continue
        for li, raw in enumerate(lines):
            if not raw.strip():
                continue
            dom, simple = extract_domain(raw)
            yield si, li, raw, dom, simple


def bump_version(text, version=None):
    version = version or datetime.date.today().strftime("%Y.%m.%d")
    if re.search(r"(?m)^!\s*Version:", text):
        return re.sub(r"(?m)^(!\s*Version:\s*).*$", r"\g<1>" + version, text)
    # no header field present: inject after Title if any, else prepend.
    line = f"! Version: {version}"
    if re.search(r"(?m)^!\s*Title:", text):
        return re.sub(r"(?m)^(!\s*Title:.*$)", r"\1\n" + line, text, count=1)
    return line + "\n" + text


def normalize(text, sort=False, do_bump=True, version=None):
    segments = parse_segments(text)
    seen = set()
    warnings = []
    for si, (kind, lines) in enumerate(segments):
        if kind != "rules":
            continue
        kept = []
        for raw in lines:
            if not raw.strip():
                continue
            dom, simple = extract_domain(raw)
            if simple:
                key, out = dom, canon(dom)
                if out != raw.strip():
                    warnings.append(f"normalized: {raw.strip()!r} -> {out!r}")
            else:
                key, out = ("opaque", raw.strip()), raw.rstrip()
            if key in seen:
                warnings.append(f"dropped duplicate: {raw.strip()!r}")
                continue
            seen.add(key)
            kept.append((out, dom))
        if sort:
            kept.sort(key=lambda t: (t[1] or "").split(".")[::-1])
        segments[si] = (kind, [o for o, _ in kept])
    out_text = "\n".join("\n".join(lines) for _, lines in segments)
    if not out_text.endswith("\n"):
        out_text += "\n"
    if do_bump:
        out_text = bump_version(out_text, version)
    return out_text, warnings


def validate(text):
    """Return (errors, warns). errors are hard (exit 1)."""
    errors, warns = [], []
    seen = {}
    for si, li, raw, dom, simple in collect(parse_segments(text)):
        s = raw.strip()
        if not simple:
            warns.append(f"opaque/unparseable rule kept as-is: {s!r}")
            continue
        if dom in PAAS_APEX:
            errors.append(f"PaaS apex would cause massive collateral: {s!r}")
        if dom in seen:
            errors.append(f"duplicate domain {dom!r} ({s!r} vs {seen[dom]!r})")
        else:
            seen[dom] = s
        if s != canon(dom):
            warns.append(f"non-normalized (run 'normalize'): {s!r}")
    return errors, warns


def merge(text, tier, domains, version=None, do_bump=True):
    key_sub = TIER_KEYWORDS.get(tier)
    if key_sub is None:
        raise SystemExit(f"unknown tier {tier!r}; choose from {sorted(TIER_KEYWORDS)}")
    segments = parse_segments(text)
    existing = {d for _, _, _, d, s in collect(segments) if s}

    # locate target rules-segment: first rules-block whose preceding 'other'
    # block's text contains the tier keyword.
    target = None
    for i, (kind, lines) in enumerate(segments):
        if kind != "rules":
            continue
        prev = segments[i - 1][1] if i and segments[i - 1][0] == "other" else []
        if any(key_sub.lower() in ln.lower() for ln in prev):
            target = i
            break
    if target is None:
        raise SystemExit(f"could not locate tier section for keyword {key_sub!r}")

    added, skipped, rejected = [], [], []
    for d in domains:
        dom, simple = extract_domain(d)
        if not simple:
            rejected.append((d, "not a valid domain"))
        elif dom in PAAS_APEX:
            rejected.append((d, "PaaS apex (collateral)"))
        elif dom in existing:
            skipped.append(dom)
        else:
            existing.add(dom)
            segments[target][1].append(canon(dom))
            added.append(dom)

    out_text = "\n".join("\n".join(lines) for _, lines in segments)
    if not out_text.endswith("\n"):
        out_text += "\n"
    if do_bump and added:
        out_text = bump_version(out_text, version)
    return out_text, added, skipped, rejected


def stats(text):
    segments = parse_segments(text)
    rows, total = [], 0
    for i, (kind, lines) in enumerate(segments):
        if kind != "rules":
            continue
        prev = segments[i - 1][1] if i and segments[i - 1][0] == "other" else []
        # Banners are '=== / title / ===' sandwiches; take content between the
        # last two fences (fallbacks handle 1 or 0 fences).
        fences = [j for j, ln in enumerate(prev) if "===" in ln]
        if len(fences) >= 2:
            window = prev[fences[-2] + 1: fences[-1]]
        elif fences:
            window = prev[fences[0] + 1:]
        else:
            window = prev
        label = next((ln.lstrip("! ").strip() for ln in window
                      if ln.strip().startswith("!") and "===" not in ln
                      and ln.strip() != "!"), "(unlabeled)")
        n = sum(1 for ln in lines if ln.strip())
        total += n
        rows.append((label[:60], n))
    return rows, total


def check_liveness(domains, timeout=3.0, workers=32):
    import concurrent.futures
    import socket
    socket.setdefaulttimeout(timeout)  # NB: does not bound getaddrinfo itself;

    # resolution timeout is governed by the system resolver (resolv.conf).
    def probe(d):
        try:
            socket.getaddrinfo(d, None)
            return (d, True, "")
        except socket.gaierror as e:
            return (d, False, (e.strerror or str(e)))
        except Exception as e:  # noqa: BLE001
            return (d, False, str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(probe, domains))


# --- CLI ----------------------------------------------------------------------


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text, in_place):
    if in_place:
        with open(path + ".bak", "w", encoding="utf-8") as f:
            f.write(read(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        sys.stderr.write(f"wrote {path} (backup at {path}.bak)\n")
    else:
        sys.stdout.write(text)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("validate")
    pv.add_argument("file")

    pn = sub.add_parser("normalize")
    pn.add_argument("file")
    pn.add_argument("-i", "--in-place", action="store_true")
    pn.add_argument("--sort", action="store_true")
    pn.add_argument("--no-bump", action="store_true")
    pn.add_argument("--version", default=None)

    pm = sub.add_parser("merge")
    pm.add_argument("file")
    pm.add_argument("--tier", required=True, choices=sorted(TIER_KEYWORDS))
    g = pm.add_mutually_exclusive_group(required=True)
    g.add_argument("--add", help="comma-separated domains")
    g.add_argument("--from-file", help="newline-delimited domains")
    pm.add_argument("-i", "--in-place", action="store_true")
    pm.add_argument("--no-bump", action="store_true")
    pm.add_argument("--version", default=None)

    pl = sub.add_parser("check-liveness")
    pl.add_argument("file")
    pl.add_argument("--timeout", type=float, default=3.0)
    pl.add_argument("--workers", type=int, default=32)

    ps = sub.add_parser("stats")
    ps.add_argument("file")

    a = p.parse_args(argv)

    if a.cmd == "validate":
        errors, warns = validate(read(a.file))
        for w in warns:
            print(f"WARN  {w}", file=sys.stderr)
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        print(f"{len(errors)} error(s), {len(warns)} warning(s)", file=sys.stderr)
        return 1 if errors else 0

    if a.cmd == "normalize":
        out, warns = normalize(read(a.file), sort=a.sort,
                               do_bump=not a.no_bump, version=a.version)
        for w in warns:
            print(f"WARN  {w}", file=sys.stderr)
        write(a.file, out, a.in_place)
        return 0

    if a.cmd == "merge":
        if a.add:
            doms = [d.strip() for d in a.add.split(",") if d.strip()]
        else:
            doms = [ln.strip() for ln in read(a.from_file).splitlines()
                    if ln.strip() and not ln.strip().startswith("!")]
        out, added, skipped, rejected = merge(
            read(a.file), a.tier, doms, version=a.version, do_bump=not a.no_bump)
        for d in added:
            print(f"ADD   {d}", file=sys.stderr)
        for d in skipped:
            print(f"SKIP  {d} (already present)", file=sys.stderr)
        for d, why in rejected:
            print(f"REJECT {d} ({why})", file=sys.stderr)
        write(a.file, out, a.in_place)
        return 0

    if a.cmd == "check-liveness":
        doms = sorted({d for _, _, _, d, s in collect(parse_segments(read(a.file)))
                       if s})
        results = check_liveness(doms, timeout=a.timeout, workers=a.workers)
        dead = [(d, why) for d, ok, why in results if not ok]
        for d, why in sorted(dead):
            print(f"UNRESOLVED {d}  ({why})")
        print(f"{len(dead)}/{len(doms)} unresolved "
              f"(verify manually; may be geo/Cloudflare false negatives)",
              file=sys.stderr)
        return 0

    if a.cmd == "stats":
        rows, total = stats(read(a.file))
        for label, n in rows:
            print(f"{n:4d}  {label}")
        print(f"{total:4d}  TOTAL")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
