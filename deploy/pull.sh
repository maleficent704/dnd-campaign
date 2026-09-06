#!/usr/bin/env bash
# Redeploy only if the branch actually moved, and only if nobody is playing.
#
# The timer runs every fifteen minutes; a rebuild every fifteen minutes would be a
# rebuild for the sake of having one. More to the point, `deploy.sh` recreates the
# container, and recreating it **ends whatever evening is running** — so this checks two
# things before it does anything: did the code change, and is anybody at the table.
#
# A table mid-turn beats a table on the newest commit. The deploy happens on the next
# tick, or when somebody runs deploy.sh by hand.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch --quiet origin
local_head=$(git rev-parse HEAD)
remote_head=$(git rev-parse '@{u}')

if [ "$local_head" = "$remote_head" ]; then
  exit 0
fi

# `phase` comes from the same snapshot the page draws from (P6.7b-iii). The request
# carries the token, because the server does not answer without one — that is the point
# of the token.
#
# **The three outcomes are deliberately not two.** A connection that fails means the
# service is down, and a down service has no evening to lose. A connection that succeeds
# but does not yield a phase means the server is up and we could not read it — a wrong
# token, most likely — and *that* is the case where redeploying would kill a live evening
# on the strength of not knowing. Treating "cannot tell" as "safe to restart" is the
# same failure shape as a control that reports success and protects nothing.
if ! body=$(curl -sf -H "Authorization: Bearer ${DNDC_WEB_TOKEN:-}" \
            http://192.168.50.46:8093/api/table 2>/dev/null); then
  if curl -s -o /dev/null --max-time 5 http://192.168.50.46:8093/ 2>/dev/null; then
    echo "the server is up but would not tell me its phase — leaving it alone." >&2
    echo "check DNDC_WEB_TOKEN in $(pwd)/.env; deploy by hand when the table is free." >&2
    exit 0
  fi
  echo "new commits and the service is not answering at all; deploying"
  exec ./deploy.sh
fi

phase=$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("phase",""))')

if [ "$phase" != "idle" ]; then
  echo "new commits, but an evening is ${phase:-unreadable} — leaving it alone"
  exit 0
fi

echo "new commits ($local_head -> $remote_head) and nothing playing; redeploying"
exec ./deploy.sh
