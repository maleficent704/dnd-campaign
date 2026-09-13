# Running the table on the VM (P6.7c)

What this is: `dndc serve` in a container on `ubuntu-docker` (192.168.50.46), published
on **`:8093`**, gated by `DNDC_WEB_TOKEN`, with the campaign on a volume and a nightly
age-encrypted backup to the NAS.

It follows the house service pattern rather than inventing one — `~/services/<name>/`
with `deploy.sh`, `docker-compose.yml`, a gitignored `.env` via `env_file:`, and
`*-backup.timer` / `*-pull.timer`. If something here looks odd, compare
`~/services/the-room/`, which is the closest sibling and settled most of these questions
first.

## Why `:8093`

Measured free three times (2026-09-04, -09-05, -09-06). Deliberately **not** `:8090`,
which the port map records as a dead PC service with a surviving firewall rule.
`~/services/the-room` rejected that same number in writing: *"a number that already means
something else on another host is a number someone will misread."* Following house
precedent rather than re-litigating it.

## The GM seat: `api`, not `subscription`

D-004 gives two adapters and the container uses `api`, with `ANTHROPIC_API_KEY` arriving
through `env_file:`.

**This section was rewritten on 2026-09-13. The reasons it gave before were wrong**, and
they were wrong in the direction that matters — they made the choice look like a
convenience call when it is a security one. Kept visible rather than quietly replaced,
because a future session re-reading the old argument would have concluded the decision
was cheap to reverse. It is not.

What the old version said, and why each half fails:

- *"`subscription` would mean shipping the Claude Code CLI inside the image."* **False.**
  Claude Code on the VM is a single standalone ELF binary already on the box, under
  `~/.local/share/claude/versions/`. Nothing needs shipping.
- *"...to save an amount of money the campaign has not yet spent ($0.2428)."* **An
  argument for the wrong side.** A subscription seat draws the Max pool and costs nothing
  in dollars, so cost, if it counted at all, favoured `subscription`.

### The real reason

**A `claude -p` seat is a tool-using process, and the GM prompt carries text typed by
whoever is at the table.**

Until 2026-09-13, `models/subscription.py` built `claude -p <prompt> --output-format json
--model … --system-prompt …` and passed **no tool restriction at all**. Headless Claude
Code therefore inherited whatever the invoking `$HOME` permitted, and the VM's
`labmonitor` identity grants `Bash(*)`, `Read`, `Write`, `Edit` with
`skipDangerousModePermissionPrompt: true`.

Verified by side effect that day — not by asking the model, which
`race-control/operations/llm-agents.md` warns produces confident false positives, a trap
this session walked into on its first attempt — a headless prompt under that identity
**created a file on disk**. Bash really ran.

**That hole is now closed**, and it was closed for both machines rather than just the VM,
because the PC's `settings.json` allows `Bash(*)` too: the adapter passes `--restricted
--strict-mcp-config` plus a `--disallowedTools` deny list. `--restricted` is the
load-bearing one — it removes code-running tools as a *class* and ignores the settings
files outright. An enumerated deny was not enough on its own: probed with `Bash` denied,
the seat refused and then named `Monitor` as another shell-running tool that was not on
the list. It declined to use it; a control cannot rest on that.

A real narration was measured through the hardened seat afterwards — unchanged prose, and
cache-write fell from the ~33–40k this project recorded to **7,465 tokens**, because the
tool definitions are no longer in the payload.

None of that makes the hosted subscription seat safe *by itself*, because the tool grant
was only half the problem. Pointing the hosted GM seat at the VM's existing Claude Code
would still build this:

> anyone on the LAN holding the table token types a line into the browser → it is
> flattened into the `claude -p` prompt → that process runs arbitrary shell commands,
> unprompted → as `labmonitor`, which is in the `docker` group and holds every SSH key
> and token on the box.

— or it would have, before the hardening. With `--restricted` the shell route is shut,
but the seat would still run *as* `labmonitor`, inside that `$HOME`, sharing its
credential and its transcripts, one flag away from the old behaviour if anyone ever edits
the command. **Defence in depth is not a reason to put the exposed thing on the
root-equivalent account**, and that is the inversion
`race-control/planning/backlog/2026-08-10-agent-privilege-separation.md` exists to remove.

The API seat has none of this, because **a model call is not a tool call** — an `api` GM
can be talked into bad prose and nothing else.

### What it would take to do it safely

Not impossible, and not what was rejected. The house already has the pattern —
`sysadmin-run`, "one Claude credential and nothing else… the `claude -p` child of such an
agent." The GM seat wants its own minimal identity: no sudo, no docker group, no keys, a
`settings.json` that denies every tool (a GM narrating prose needs none), registered in
`lab-agents/claude_installs.py` **before first use**, with the container running as that
uid and mounting that `$HOME`.

One detail that would bite anyone who tries it: **mount `~/.local`, never a version
path.** Claude Code self-updates and deletes old versions — measured 2.1.267 → 2.1.270 in
three days — so a pinned-version bind mount breaks within a week, and Docker silently
recreates the missing source as a root-owned directory rather than failing.

**Decided 2026-09-13 (Kelly): stay on `api`.** The safe version is a new unix account, an
interactive login only she can perform, and doc changes in four places — to save roughly
two cents an evening. D-004's sticky default is per-machine, so a hot-seat evening on the
PC still runs on `subscription` whenever she wants a Claude Code GM.

## The one step that is not automated

**`.env` has to be put on the VM by hand**, at `~/services/dndc/.env`, containing at
least:

```
DNDC_WEB_TOKEN=…      # the LAN gate — the same one already in the PC's .env
ANTHROPIC_API_KEY=…   # the GM seat
```

Then `./deploy.sh`.

That step is deliberately manual. Copying a file of credentials between machines is the
kind of thing that should happen because somebody meant it, not because a script found it
convenient — and the house rule is that secrets live in a gitignored `.env`, never in
`docker-compose.yml` and never in an image layer.

`deploy.sh` checks the result the right way round: **an anonymous `GET /` answering 401 is
the success condition.** A 200 there would mean the table was open to anyone who reached
the port, and the script fails loudly on it.

## Where the campaign lives now

On the `campaigns` volume, at `/data/campaigns` inside the container — because P6.7a gave
the campaigns directory a configurable path precisely so this could be true.

**It is no longer in the git repo.** Committed game state was always wrong under the house
rule ("never `git init` a data dir"), and it survived this long for a good reason: git was
the only thing backing it up. It was evicted only once there were three copies —

1. Kelly's PC, at `C:\dev\dnd-campaign\campaigns\` (now untracked, still there),
2. the `campaigns` volume on the VM,
3. an age-encrypted tarball on the NAS, with a rehearsed restore.

— and not before. Git history still holds every earlier version, so nothing is lost;
what stops is *new* game state landing in a code repo.

**Two homes, one canonical.** The VM's volume is where the campaign lives now. The PC's
copy is a development fixture: play there and the two diverge, with no merge story. If
you want to play on the PC against the real campaign, pull it down first:

```
docker run --rm -v dndc_campaigns:/data alpine tar cf - /data | tar xf - -C /tmp/dndc
```

## Backups

`deploy/backup.sh`, nightly at **05:45 UTC** — after chat-archive (05:00), the scrapbook
(05:15) and The Room (05:30), so the CIFS-heavy jobs do not contend for the share. It
tars both volumes, pipes straight through gzip through `age`, and writes only ciphertext
to `/mnt/truenas/shared/backups/dnd-campaign/`.

Encrypted, and not because a story about a salt caravan is sensitive. The same tarball
carries the JSONL event stream — every prompt, every reply, every cost line — and the
character sheets of two real people who live here. The NAS is a CIFS mount with
`file_mode=0664` forced, so permissions on that share are decoration; encryption is the
actual protection. `the-room/automation/db_backup.sh` reached that conclusion first.

Every backup is **verified by decrypting it** before the script reports success. A backup
that has never been read is a directory of hopes.

Restore is in the script's own header, where somebody looking for it will be.

## Updating

`dndc-pull.timer` every 15 minutes. It redeploys only if the branch actually moved **and
nothing is playing** — recreating the container ends the evening, and a table mid-turn
beats a table on the newest commit. Otherwise it waits for the next tick.

## What a hosted table exposes

Read `docs/LAN-ACCESS.md`. The short version: a key is not a login, everyone holding it is
the same person as far as this server is concerned, and a hosted server adds one thing the
played one did not have — **the ability to begin an evening, which spends money.** That is
why `DNDC_WEB_REQUIRE_TOKEN=1` is set in the image and why an absent token refuses to
start rather than coming up open.
