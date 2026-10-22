#!/bin/sh

# Request one completion review; allow the stop after that review.
exec jq --rawfile checklist "$(dirname "$0")/completion.txt" '
  if .hook_event_name != "Stop" or .stop_hook_active == true then
    {}
  else
    {decision: "block", reason: $checklist}
  end
'
