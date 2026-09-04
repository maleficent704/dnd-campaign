# LAN access — what serving a session exposes

Written for **P6.6**, because `web/server.py` used to bind every interface with a comment
saying what that did and did not protect would be "written down in P6.6 rather than
assumed here". This is that. Writing it down is what changed the default.

Read this before widening `web.host` in `config.yaml`, and again before **P6.7** puts this
on the VM, where the exposure window stops being an evening and becomes always.

---

## There is no login

A device that can reach the port is sitting at the table. It is not a viewer with limited
rights; it is a player. Specifically it can:

- **watch the whole session** — every turn, every NPC line, the party, the recap window;
- **take a turn** as whoever is currently acting, with no check that it is that person's
  device. The name comes out of a dropdown and out of `localStorage`, and neither is
  evidence of anything;
- **`/switch`** the acting player, which means it can hand the turn to itself first;
- **`/scene`** — move the party somewhere else;
- **answer the end-of-session confirmations** (P6.5), so it decides what goes on a sheet
  and what enters the canon ledger permanently;
- **`/quit`** — end the evening for everybody;
- **spend money.** Every turn is a GM call. On `api` billing that is real dollars against
  the console cap; on `subscription` it is Max quota, per-account, shared with everything
  else in the house (D-004, and the P6.7 note).

None of that is a defect. It is what "a browser can play" means, and it is the right shape
for a family on one network. It is written down because the size of the trust boundary
should be a decision and not a discovery.

## What is out of reach, and why

These hold structurally rather than by policy, which is the only kind worth writing down:

- **`gm_only` canon and the NPC belief register never leave the process.** Not filtered on
  the way out — `web/view.py` has nowhere to put them. No `scope` field exists on the
  types a device is sent, so there is no bug that can leak one (P6.2, and P4.1's
  discipline: protection by absence, not by instruction).
- **Live narration is filtered at the point it enters the mirror**, not at the point it is
  displayed, so the streamed text a device sees has been through `TagStream` before it is
  anybody's to render (P6.3).
- **A spectator link has no write route at all.** `--watch-only` does not refuse writes; it
  builds a server with no `POST` routes on it. A device cannot tell "not allowed" from
  "not built", because there is nothing to tell apart (P6.4).
- **There is no filesystem or shell surface.** The routes are `GET /`, `GET /api/table`,
  `GET /api/events`, and — unless `--watch-only` — `POST /api/turn` and `POST /api/answer`.

## `0.0.0.0` is not "the LAN"

This is the finding that changed the default, and it is not this project's finding — the
house measured it on 2026-09-02 while gating the kids capture station. See
`race-control/docs/operations/lan-only-services.md`:

> Anything bound to `0.0.0.0` is served on `tailscale0` as well as the LAN, so it is
> reachable from **every device on the tailnet** — including `iphone172`, over cellular,
> from anywhere in the world.

Both machines this will ever run on are tailnet nodes: `kelly-pc` (`100.100.147.83`) and
the VM (`100.97.50.9`). So the old default meant an unauthenticated campaign GUI, with the
authority listed above, published to a VPN — for as long as an evening lasted.

**The default is now `host: lan`**, resolved to this machine's LAN address when the socket
is bound rather than written into the file, because an address in a config file goes stale
on the next DHCP lease and a stale bind address does not fail loudly: it binds to nothing
and reports that it started.

### Measured, 2026-09-04, on kelly-pc

```
bound to 0.0.0.0:8791          bound to 192.168.50.160:8792
  127.0.0.1        -> 200        127.0.0.1        -> FAIL
  192.168.50.160   -> 200        192.168.50.160   -> 200
  100.100.147.83   -> FAIL       100.100.147.83   -> FAIL
```

Two things to read carefully, because one of them is not evidence:

1. **The LAN bind genuinely narrows, on Windows.** It drops loopback as well — the port is
   present on exactly one interface. The control works here, not just on Linux.
2. **The tailnet row proves nothing.** Tailscale on kelly-pc was *not up* during the test:
   the service was running, the adapter showed `Up`, and `tailscale status` reported
   `NoState` with no IPv4 assigned. So `0.0.0.0` was measured LAN-only **by accident of
   state**. A control that holds only while a VPN happens to be down is not a control, and
   this table must not be cited as though the first column were safe. (Separately: this
   contradicts `race-control/docs/inventory/network.md`, which lists kelly-pc as *Always
   on* at `100.100.147.83`. Flagged there, not fixed here.)

The house doc's rule applies to this file too — **verify, don't assert.** If it matters
tonight, run it, and from a second machine.

## What to do when

| You want | Set |
|---|---|
| the other sofa, and nothing else | nothing — `host: lan` is the default |
| just to look at it yourself | `--serve-host 127.0.0.1` |
| a screen that cannot play | `--watch-only` — no write route is built |
| the tailnet on purpose (phone, away from home) | `--serve-host 0.0.0.0`, and read the rest of this file first |

A wildcard bind is still allowed and still one flag away. It announces itself: the startup
line says *every interface, the tailnet included*, and says there is no login. Making the
unsafe thing loud is better than making it impossible, because the safe default is what
people actually get.

## What changes at P6.7

Hosting on the VM changes exactly one thing about this file, and it is the important one:
**the window.** Today the surface exists while `dndc serve` is running and disappears with
it — an evening, started deliberately, by someone in the room. Hosted, it answers all the
time.

Three things follow, and belong in P6.7 rather than here:

- **Bind to the VM's LAN address explicitly** in `docker-compose.yml`
  (`192.168.50.46:PORT:PORT`, not `PORT:PORT`). On that box the bind *is* the control:
  `ufw` does not filter Docker-published ports, so a firewall there reports "active, deny
  incoming" while the port stays wide open. A firewall that says active while the port
  answers is worse than none — it converts an unknown into a confident wrong belief.
- **Then a shared code becomes worth it.** Not now: today the session is bounded by
  someone starting it. My recommendation for P6.7 is the cheapest thing that matches the
  actual threat — a per-session code in the URL (`/?k=…`), checked on the write routes and
  on the event stream, printed in the terminal and regenerated per session. It stops "a
  device that found the port" without asking a family to hold accounts. It is not
  authentication and should not be described as any.
- **Idle sessions end.** An always-on service that will happily hold an abandoned session
  open is how the money gets spent by accident.

---

## Open, for Kelly

**Is a code wanted at all, or is the LAN trusted?** Both are defensible and the house
already leans one way — every service on the VM today is unauthenticated on the LAN, and
that is a deliberate posture rather than an oversight. Matching it is a real option. The
thing that makes this one different from pit-wall or the scrapbook is that a stranger on
this port can **spend money and rewrite the campaign's canon**, which a dashboard cannot.

Nothing is blocked either way; P6.6 does not need the answer, and P6.7 is where it costs
something to have got wrong.
