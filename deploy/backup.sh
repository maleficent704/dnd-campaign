#!/usr/bin/env bash
# Nightly backup of the campaign and its logs to the NAS, age-encrypted.
#
# ---------------------------------------------------------------------------
# Why encrypted, when a campaign is a made-up story about a salt caravan
# ---------------------------------------------------------------------------
# Not because the fiction is sensitive. Because the same tarball carries the
# JSONL event stream, and that stream is the research instrument: every prompt,
# every model reply, every cost line, and the character sheets of two real
# people who live here. The NAS is a CIFS mount with file_mode=0664 forced, so
# a chmod on the destination changes nothing — anyone with SMB access as
# `labvm` reads the bytes either way. **Encryption is the real protection on
# that share; permissions are decoration.** `the-room/automation/db_backup.sh`
# reached the same conclusion first and this follows it rather than re-deciding.
#
# `age -r <recipient>` encrypts to a *public* recipient, which is what lets this
# run unattended — no passphrase, no prompt on the VM. The recipient is the one
# the secrets backup already uses, reused deliberately: it inherits a bootstrap
# story that has already been worked out, and a second key would be a second
# root of trust to lose.
#
# No plaintext touches the NAS. The tar is piped straight through gzip through
# age, and only ciphertext is written to $DEST.
#
# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------
#   cd ~/services/dndc
#   age -d -i ~/.config/sops/age/keys.txt <backup>.tar.gz.age | gunzip > /tmp/dndc.tar
#   docker compose stop dndc
#   docker run --rm -v dndc_campaigns:/data/campaigns -v dndc_logs:/app/logs \
#       -v /tmp:/restore alpine sh -c 'cd / && tar xf /restore/dndc.tar'
#   docker compose up -d --force-recreate dndc
#
# There is no WAL trap here — unlike The Room, this is YAML and JSONL on a
# filesystem, so what the tar holds is what the game reads. The one thing that
# *is* worth knowing: `saves/state.yaml` is the turn window, and restoring a
# campaign without it starts the next evening from the chronicle instead. That
# is a recoverable difference, not a corrupt one.
set -euo pipefail

# Defaulted inline, the way the-room's does, because it is a *public* recipient — the
# whole point of encrypting to one is that no secret has to sit on the VM for the timer
# to run. Same key the secrets backup uses, deliberately reused.
RECIPIENT="${DNDC_BACKUP_RECIPIENT:-age16vzcmmg5ys6zmlvrrgrgfpxa97r4c48gsfj4qnm7j90djcjcqvmszwtkxz}"
DEST="${DNDC_BACKUP_DEST:-/mnt/truenas/shared/backups/dnd-campaign}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$DEST/dndc-$STAMP.tar.gz.age"

mkdir -p "$DEST"

# Read straight out of the named volumes rather than out of the running container:
# a backup that needs the service to be up is a backup that is missing on exactly the
# night the service is down.
docker run --rm \
  -v dndc_campaigns:/data/campaigns:ro \
  -v dndc_logs:/app/logs:ro \
  alpine tar cf - /data/campaigns /app/logs \
  | gzip \
  | age -r "$RECIPIENT" \
  > "$OUT"

# Prove it is a tarball and not a zero-byte file with a confident name. Costs one
# decryption and is the difference between a backup and a directory of hopes.
if ! age -d -i "$HOME/.config/sops/age/keys.txt" "$OUT" | gunzip | tar tf - >/dev/null 2>&1; then
  echo "backup at $OUT did not verify — removing it rather than leaving a bad one" >&2
  rm -f "$OUT"
  exit 1
fi

echo "wrote and verified $OUT ($(du -h "$OUT" | cut -f1))"

# Retention is hard-off, as on the scrapbook and The Room. Kelly, 2026-09-02:
# "I will clear up space elsewhere before I will prune this." A campaign's whole
# history compresses to less than a phone photo; the day that stops being true is
# the day to revisit it, and not before.
