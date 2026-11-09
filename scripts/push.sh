#!/usr/bin/env bash
# Commit data/ and push it to main. Several runs can finish at the same time (research requests, queue, watcher):
# when the rebase stops on JSON conflicts, scripts/gitsync.py merges both sides instead of dropping a run's work.
#   bash scripts/push.sh "data: KI-Recherche 2026-11-09"     (writes changed=true/false to $GITHUB_OUTPUT)
set -u
out() { [ -n "${GITHUB_OUTPUT:-}" ] && echo "changed=$1" >> "$GITHUB_OUTPUT"; echo "changed=$1"; }
git add data
if git diff --cached --quiet; then out false; exit 0; fi
git commit -q -m "$1"
for i in 1 2 3 4 5; do
  if ! git pull -q --rebase origin main; then
    python scripts/gitsync.py >&2 && GIT_EDITOR=true git rebase --continue >&2 || { git rebase --abort; out false; exit 1; }
  fi
  if ! python scripts/atlas.py validate >&2; then git log -1 --oneline >&2; out false; exit 1; fi
  if git push -q origin HEAD:main; then out true; exit 0; fi
  sleep $((i * 4))
done
out false
exit 1
