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

The alternative was real: the VM's Claude Code install is on the same Max login (Kelly,
2026-09-04), so the *host* has a subscription seat. But a container does not inherit its
host's, so `subscription` would have meant shipping the Claude Code CLI inside the image
**and** bind-mounting the Max credentials into it — a much larger image and a live
credential on a mount, to save an amount of money the campaign has not yet spent. Total
API billing across the whole campaign to date is **$0.2428**.

Nothing is lost by this: D-004's sticky default is per-machine, so a hot-seat evening on
Kelly's PC can still run on `subscription`. If the hosted spend ever stops looking like
noise, the change is a credential mount and a `billing:` line, not a redesign.

**Flagged rather than assumed** — it was recorded as open in PROGRESS.md and this is the
answer, not a ratification.

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
