#!/bin/sh

exec jq -Rs '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: .
  }
}' "$(dirname "$0")/subagents.txt"
