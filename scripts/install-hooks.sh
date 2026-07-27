#!/usr/bin/env bash
# Install the warn-only pre-commit hook (run once per clone, after git init).
# Mirrors the race-control pattern: the hook nags, never blocks.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  echo "No .git directory — run 'git init' first." >&2
  exit 1
fi

cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
# Warn-only: code changed without a PROGRESS.md update means the handoff entry
# (CLAUDE.md session protocol) was probably skipped. Never blocks.
staged=$(git diff --cached --name-only)
if echo "$staged" | grep -q '^src/' ; then
  if ! echo "$staged" | grep -q '^docs/PROGRESS.md$' ; then
    echo ""
    echo "⚠  src/ changed but docs/PROGRESS.md is not in this commit."
    echo "   The handoff entry is the communication channel — did you run /handoff?"
    echo "   (Warning only — commit proceeds. Bypass silently: git commit --no-verify)"
    echo ""
  fi
fi
exit 0
HOOK
chmod +x .git/hooks/pre-commit
echo "pre-commit hook installed (warn-only)."
