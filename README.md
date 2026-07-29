# Browser Game Portals Blocklist

A curated blocklist of **in-browser / casual gaming portals** (friv-class sites, `.io` games, embed CDNs and "unblocked games" school-proxy portals) in **Adblock format**.

It deliberately **excludes PC game storefronts** (Steam, EA, Epic, GOG, etc.) — the target is casual, play-in-the-browser gaming, not gaming in general.

## Compatibility

The list uses only `||domain^` network rules (no cosmetic rules), so it works equally well in browser extensions and at the DNS layer — a DNS-only deployment loses nothing:

- [Pi-hole](https://pi-hole.net/)
- [AdGuard](https://adguard.com/) / [AdGuard Home](https://adguard.com/en/adguard-home/overview.html) / AdGuard DNS
- [eBlocker](https://eblocker.org/)
- [uBlock Origin](https://github.com/gorhill/uBlock)
- [Brave](https://brave.com/) (only in aggressive blocking mode)
- [AdNauseam](https://adnauseam.io/)

## Subscribe

```
https://raw.githubusercontent.com/dkorunic/browser-games-blocklist/main/hosts.txt
```

- **Pi-hole**: *Settings → Lists (Adlists) → Add* the URL above, then update gravity (`pihole -g`). Pi-hole natively supports Adblock-style `||domain^` entries.
- **AdGuard Home**: *Filters → DNS blocklists → Add blocklist → Add a custom list*, paste the URL.
- **uBlock Origin / AdNauseam**: *Dashboard → Filter lists → Import*, paste the URL.
- **Brave**: *Settings → Shields → Content filtering → Add custom filter lists*, paste the URL. Set *Trackers & ads blocking* to **Aggressive**, otherwise custom lists are not fully enforced.
- **eBlocker**: *Settings → Blocker → add a custom blocklist* with the URL.

## What's inside

Each `||domain^` rule matches the domain and **all of its subdomains**, on any scheme or path. The list is organized into tiers:

| Tier | Contents | Examples |
|------|----------|----------|
| Casual HTML5 portals | Friv-class portals safe to block at the apex | `friv.com`, `poki.com`, `crazygames.com`, `coolmathgames.com`, `miniclip.com`, `itch.io` |
| Aggregator / embed CDNs | High-leverage: blocking these kills embedded games across thousands of long-tail sites | `gamedistribution.com`, `gamemonetize.com`, `gamepix.com`, `famobi.com` |
| `.io` / real-time multiplayer | Mostly single-game domains | `agar.io`, `slither.io`, `krunker.io`, `1v1.lol` |
| "Unblocked games" portals | Apex-blockable subset of school-proxy game sites | `unblockedgames66.com`, `classroom6x.com`, `66ez.com` |
| Cloud / board / UGC | Borderline entries — prune to taste | `now.gg`, `roblox.com`, `chess.com`, `lichess.org`, `scratch.mit.edu` |

## Caveats

- **Embed CDN rules may cause false positives.** The aggregator tier (`gamedistribution.com` and friends) occasionally breaks a non-game embed. Remove those rules if you hit collateral damage.
- **"Unblocked games" sites rotate faster than any blocklist can track.** Most live on PaaS wildcards (`github.io`, `*.netlify.app`, `*.vercel.app`, `*.pages.dev`, `sites.google.com`, `glitch.me`, …) that cannot be apex-blocked without massive collateral. Domain blocklisting is the wrong control for that segment; only a stable, apex-blockable subset is included here.
- **The last tier is opinionated.** Roblox (UGC platform), chess.com/lichess (board games), now.gg (cloud Android gaming) and scratch.mit.edu (educational) are borderline vs. strictly "friv-class" — delete lines you don't want.

## Updating

The list carries an `! Expires: 7 days` hint, so compatible clients re-fetch it automatically. The `! Version:` field is a date stamp (e.g. `2026.07.29`).

## Contributing

Issues and pull requests with additions, removals or false-positive reports are welcome. When proposing a domain, note which tier it belongs to and whether it is safe to apex-block.

## License

None specified — use at your own discretion.
