# Classification taxonomy & policy

Read before adding any domain. The list is scoped to **in-browser / casual game
portals** (friv-class). It explicitly **excludes** PC/console storefronts and
launchers (Steam, Epic, EA/Origin, GOG, Ubisoft Connect, Battle.net, Xbox,
PlayStation, GeForce NOW, itch's *desktop app* distribution, etc.). If a domain's
primary purpose is selling/launching installed games, it is out of scope.

## Tiers (the `--tier` values)

| tier          | banner keyword | what belongs here |
|---------------|----------------|-------------------|
| `portals`     | `TIER 1`       | Casual HTML5 aggregator portals: many games under one apex, safe to apex-block (friv.com, poki.com, crazygames.com, coolmathgames.com, y8.com, kizi.com, armorgames.com, …). |
| `aggregators` | `AGGREGATOR`   | Embed/CDN backends that *serve* game iframes into thousands of long-tail sites (gamedistribution.com, gamemonetize.com, gamepix.com, famobi.com). High leverage: one rule kills embeds everywhere. Tradeoff: may break an occasional non-game embed. |
| `io`          | `.io`          | Real-time multiplayer, usually one game per apex (agar.io, slither.io, krunker.io, 1v1.lol, territorial.io, …). Churny: single-game domains die and revive. |
| `unblocked`   | `unblocked`    | School-proxy / "unblocked games" portals with a **stable apex** only. |
| `cloud`       | `Cloud`        | Borderline: cloud/UGC/board (now.gg, roblox.com, chess.com, lichess.org) and educational (scratch.mit.edu — subdomain only). Prune to taste. |

## Hard rule: never apex-block PaaS / shared hosting

The `unblocked` ecosystem deliberately rehosts on multi-tenant platforms. Blocking
their apex is catastrophic collateral (`||github.io^` blocks millions of unrelated
sites). The script refuses these on `merge` and flags them on `validate`. Do not
work around it. Denylisted apexes:

```
github.io gitlab.io netlify.app vercel.app pages.dev onrender.com render.com
repl.co replit.dev glitch.me web.app firebaseapp.com surge.sh herokuapp.com
amplifyapp.com cloudfront.net sites.google.com google.com weebly.com wixsite.com
workers.dev r2.dev deno.dev fly.dev appspot.com azurewebsites.net
pythonanywhere.com 000webhostapp.com neocities.org itch.zone framer.app webflow.io
```

A **specific subdomain** (`||someproxy.github.io^`) is fine to add manually — it's
a single tenant, not the platform. But understand it's whack-a-mole: they rotate.
For the `unblocked`/PaaS class, the right control is category-based DNS filtering
(NextDNS / Cloudflare Gateway "Games"), an allowlist model, or SNI/keyword rules —
not this blocklist. State that when a user expects the list to hold that line.

## Borderline-inclusion policy

Include only if the site's *primary* mode is playing games in the browser with no
install. Flag borderline entries to the user rather than deciding unilaterally:

- **itch.io** — hosts browser games *and* downloadable indie builds; overlaps the
  PC-gaming exclusion. Keep in `portals` but mention the overlap.
- **scratch.mit.edu** — educational programming, heavily used as a school "game"
  site. Subdomain-scope only; never `||mit.edu^`.
- **roblox.com / now.gg** — UGC / cloud platforms, not friv-style arcades.
- **chess.com / lichess.org** — board games; include only if the user wants board
  games covered.

## Sourcing new domains

No authoritative traffic ranking exists (SimilarWeb category data is paywalled;
"top browser games 2026" articles are SEO content citing each other). Treat any
refresh as **curated inference** and say so. Cross-check a candidate against a
couple of independent sources before adding, and prefer the apex over deep paths.

## POSIX-sh equivalents (for the trivial ops, if avoiding Python)

The script is stdlib-only Python for portability (one `getaddrinfo` path across
Linux/BSD/macOS). The pure-text ops are also expressible in sh + coreutils:

```sh
# dedup while preserving order, rules only:
awk '/^\|\|/ && !seen[$0]++' list.txt

# lint: any rule line not matching the ||domain^ canonical form:
grep -nE -v '^(!|\|\|[a-z0-9.-]+\^$|$)' list.txt

# liveness (glibc): getent; on BSD/musl fall back to host/dig:
grep -oE '\|\|[^^]+' list.txt | sed 's/^||//' | while read -r d; do
  getent ahosts "$d" >/dev/null 2>&1 || echo "UNRESOLVED $d"
done
```

`getent` is glibc-only. On BSD/musl use `host "$d"` or `dig +short "$d"` and test
for empty output. The Python `check-liveness` avoids this divergence, which is why
it's the default.
