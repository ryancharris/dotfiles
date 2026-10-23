#!/bin/sh
set -eu

DOTFILES="${DOTFILES:-$HOME/dotfiles}"

exec jq -n \
  --rawfile concise "$DOTFILES/agents/hooks/concise.txt" \
  --rawfile subagents "$DOTFILES/agents/hooks/subagents.txt" \
  --rawfile git "$DOTFILES/agents/hooks/git-workflow.txt" \
  '{
    injectSteps: [
      {
        ephemeralMessage: "\($concise)\n\($subagents)\n\($git)"
      }
    ]
  }'
