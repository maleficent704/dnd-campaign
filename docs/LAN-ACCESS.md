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

From the machine itself — two binds, three targets:

```
bound to 0.0.0.0:8791          bound to 192.168.50.160:8792
  127.0.0.1        -> 200        127.0.0.1        -> FAIL
  192.168.50.160   -> 200        192.168.50.160   -> 200
```

**The LAN bind genuinely narrows, on Windows.** It drops loopback as well, so the port is
present on exactly one interface. The control works here and not only on Linux.

The tailnet question cannot be answered from the same machine, and the first attempt could
not be answered at all: Tailscale on kelly-pc was down — service running, adapter `Up`,
`tailscale status` reporting `NoState` with no IPv4 assigned. `0.0.0.0` measured as
LAN-only **by accident of state**, which is not a control and must never be reported as
one. Kelly turned it back on the same day, and it was then measured properly, **from the
VM, over both routes** — the second-machine test the house doc asks for:

```
from ubuntu-docker (192.168.50.46 / 100.97.50.9)      :8791 (0.0.0.0)   :8792 (LAN bind)
  via the tailnet   http://100.100.147.83/                200               refused
  via the LAN       http://192.168.50.160/                200               200
```

That is the whole argument for the default, in four numbers:

- **A wildcard bind on this machine really is on the tailnet.** Another machine reached it
  over the VPN, not over the LAN. The old default was doing this.
- **The LAN bind really does close it**, while staying reachable from the sofa. The control
  is the bind, and it needs nothing to be remembered or kept running.
- **Windows Firewall is not a mitigating control here.** Both ports answered a machine
  across the LAN without any rule being added. Do not count on it.

The house doc's rule applies to this file too — **verify, don't assert**, and from a second
machine. The commands are in `race-control/docs/operations/lan-only-services.md`.

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
- **A shared token, decided.** See *Settled* below. It is checked on the write routes and
  on the event stream, and it is not authentication — it stops "a device that found the
  port", which is the actual threat, and nothing else.
- **Idle sessions end.** An always-on service that will happily hold an abandoned session
  open is how the money gets spent by accident.

---

## Settled (Kelly, 2026-09-04): a fixed token in `.env`

The question was whether a code is wanted at all, given that every other service on the VM
is unauthenticated on the LAN by deliberate posture. What makes this port different is that
a device on it can **spend money and rewrite the campaign's canon**, which a dashboard
cannot. Kelly's answer: **a fixed token in the gitignored `.env`, matching `the-room`'s
`ROOM_TOKEN`.**

This overrides the per-session code recommended above when this file was written, and the
reason is worth keeping, because the earlier recommendation was worse for the actual use:

> A rotating code has to be read off a terminal and re-sent to two people every evening —
> on a page a family is meant to **bookmark**. It optimises against an attacker who does
> not exist here (nobody is replaying yesterday's link) at the cost of the thing that made
> hosting worth doing, which is that Kelly does not have to be at a keyboard for the
> evening to start. A fixed token is one bookmark, forever, and it is already the shape
> this house uses.

What that means for P6.7b, where it gets built:

- The token lives in `.env` (gitignored) and reaches the container through `env_file:`,
  never inline in `docker-compose.yml` and never in the image.
- **Absent token → refuse to start**, not "run without a gate". A service that silently
  drops its only control is the P6.6 firewall again: it reports success and protects
  nothing.
- Checked on `POST /api/turn`, `POST /api/answer` and `GET /api/events`. A read of `GET /`
  handing out the shell is not the boundary — the stream is, because that is where the
  narration actually flows.
- It is **not** a login and must never be described as one. There is still no identity
  here: everyone who has the token is the same person as far as this server knows, which
  is the whole of "There is no login" above, unchanged.
