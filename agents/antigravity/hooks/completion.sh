#!/bin/sh
set -eu

DOTFILES="${DOTFILES:-$HOME/dotfiles}"

# Intercept the first stop attempt to trigger self-review; allow subsequent stop.
exec jq --rawfile checklist "$DOTFILES/agents/hooks/completion.txt" '
  if (.executionNum // 1) > 1 then
    {}
  else
    {decision: "continue", reason: $checklist}
  end
'
