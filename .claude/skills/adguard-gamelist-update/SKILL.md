---
name: adguard-gamelist-update
description: Update, refresh, extend, prune, or lint the AdGuard browser-games blocklist (the friv-class / in-browser gaming filter list, e.g. browser-games-blocklist.txt). Use this whenever the user wants to add or remove game-portal domains, refresh the list against the current landscape, check for dead domains, re-validate or re-normalize the filter syntax, bump its version, or otherwise maintain a hand-curated AdGuard/hosts-style gaming denylist — even if they just say "update my games list" or "add these sites to the blocklist" without naming this skill.
---

# AdGuard game-list maintenance

Maintain a hand-curated AdGuard blocklist of in-browser game portals (friv.com,
poki.com, crazygames.com, the `.io` cluster, school "unblocked" portals, etc.).
The list is tiered by comment banners; ordering *within* a tier is curated by
prominence, not alphabetical — preserve it.

Do deterministic work with `scripts/manage_blocklist.py` (stdlib-only, no deps).
Reserve model judgment for classification and scope decisions. Read
`references/taxonomy.md` before adding any domain — it defines the tiers, the
hard PaaS-apex prohibition, and the borderline-inclusion policy.

## Locate the file first

Default target is `browser-games-blocklist.txt` (check the working dir, uploads,
and outputs). If several candidates or none exist, ask which file — do not guess.
All commands below take the path as their last argument. Prefer `-i` (in-place;
writes a `.bak`) once the plan is confirmed; otherwise commands print to stdout.

## The script

```
python3 scripts/manage_blocklist.py validate       FILE
python3 scripts/manage_blocklist.py stats          FILE
python3 scripts/manage_blocklist.py normalize      FILE [-i] [--sort] [--no-bump] [--version YYYY.MM.DD]
python3 scripts/manage_blocklist.py merge          FILE --tier {portals,aggregators,io,unblocked,cloud} (--add a.com,b.com | --from-file f) [-i]
python3 scripts/manage_blocklist.py check-liveness FILE [--timeout S] [--workers N]
```

Guarantees the script enforces so you don't have to reason about them each time:
global dedup (first occurrence wins, across all tiers), coercion of any input
form (`domain`, `http://…/path`, `www.`, `0.0.0.0 domain`) to `||domain^`,
idempotent `normalize`, refusal to add a PaaS/shared-hosting apex, and
`check-liveness` that only *reports* — it never deletes.

## Workflows

### Add domains the user supplies
1. Classify each into a tier per `references/taxonomy.md`. If a domain is a PaaS
   apex or clearly out of scope, say so instead of forcing it in.
2. `merge FILE --tier <tier> --add <csv>` (one call per tier). Read the
   ADD/SKIP/REJECT report back to the user — REJECTs need a decision.
3. `validate FILE`. Fix any hard errors before presenting.

### Refresh against the current landscape
1. Search the web for currently-prominent browser-game portals and note which
   listed domains have died. There is no authoritative "top-N by traffic" feed;
   rankings come from SEO blogs and paywalled SimilarWeb data — treat additions
   as curated inference, and tell the user that.
2. Propose the diff (adds per tier, death candidates) and get sign-off *before*
   editing. Then `merge` the adds.
3. `check-liveness FILE`. Unresolved domains are candidates, not confirmed dead
   (getaddrinfo can't separate NXDOMAIN from SERVFAIL/timeout; Cloudflare and
   geo-fencing produce false negatives, and a sandboxed resolver may fail names
   that resolve fine in production). Re-check survivors before removing.
4. Quarantine rather than delete: move a confirmed-dead rule under a
   `! DEAD (verify) — <date>` comment so history is auditable, unless the user
   asks for hard removal.

### Remove / prune
Delete the specific `||domain^` line(s) or a whole tier, then `validate`. For a
"conservative vs aggressive" split, duplicate the file and strip the borderline
`cloud` tier and the churny `unblocked` tier from the conservative copy.

### Lint / re-normalize only
`normalize -i FILE` then `validate FILE`. Use `--version` to pin the bump date
(otherwise it uses today's system date). Only pass `--sort` if the user
explicitly wants alphabetical order — it destroys the curated prominence order.

## Always finish with
`validate` (must exit 0) and `stats` (report the per-tier counts). Then present
the updated file and summarize the diff: what was added, skipped, rejected, and
any death candidates left for the user to confirm.

## Hard rules (see taxonomy for rationale)
- Never add a PaaS/shared-hosting apex (`github.io`, `netlify.app`, `vercel.app`,
  `pages.dev`, `sites.google.com`, …). The script refuses these; don't work
  around it. Individual subdomains (`||foo.github.io^`) are acceptable.
- Never silently drop a domain on a single failed DNS lookup.
- Preserve the tiered comment structure and intra-tier ordering.
