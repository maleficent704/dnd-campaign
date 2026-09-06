#!/usr/bin/env bash
# Rebuild and restart the hosted table.
#
# `docker compose restart` does NOT recreate containers, so config changes need
# stop/rm/up — that is the house gotcha and the reason this script exists at all
# (same shape as ~/services/the-room/deploy.sh).
set -euo pipefail
cd "$(dirname "$0")"

git pull --ff-only
docker compose build
docker compose up -d --force-recreate dndc

# Long enough for uvicorn to bind. The image refuses to start without a token, so a
# missing `.env` fails here rather than three hours later at the table.
sleep 3

# The gate answers 401 to an anonymous request, and that is the *success* condition:
# a 200 here would mean the table was open to anyone who reached the port. `-o /dev/null`
# because the body is the closed-table page and nobody needs it in a deploy log.
code=$(curl -s -o /dev/null -w '%{http_code}' http://192.168.50.46:8093/)
if [ "$code" = "401" ]; then
  echo "up on http://192.168.50.46:8093 — gated (401 without a key, as it should be)"
elif [ "$code" = "200" ]; then
  echo "UP BUT UNGATED: / answered 200 without a key. Check DNDC_WEB_TOKEN in .env." >&2
  exit 1
else
  echo "unexpected status $code from http://192.168.50.46:8093/" >&2
  exit 1
fi
