#!/usr/bin/env bash
# Claude Code statusline: cost · model · ctx% · dir · PR

DATA=$(cat)

# Parse all fields in one jq call
eval "$(echo "$DATA" | jq -r '
  (if (.model | type) == "object" then (.model.display_name // .model.id // "") else (.model // "") end) as $mn |
  @sh "
    _model_raw=\($mn)
    _fast=\(.fast_mode // false)
    _cost_raw=\(.cost.total_cost_usd // "")
    _ctx_raw=\(.context_window.used_percentage // "")
    _pr_num=\(.pr.number // "")
    _pr_state=\(.pr.review_state // "")
    _dir=\(.workspace.current_dir // .cwd // "")
  "
')"

# Model family name
model=$(echo "$_model_raw" | grep -oiE '(sonnet|opus|haiku)' | head -1 | tr '[:upper:]' '[:lower:]')
[ -z "$model" ] && model="?"
[ "$_fast" = "true" ] && model="⚡ ${model}" || model="🤖 ${model}"

# Session cost
cost=""
[ -n "$_cost_raw" ] && cost=$(printf '$%.2f' "$_cost_raw")

# Context window — brain normally, fire when ≥80%
ctx=""
if [ -n "$_ctx_raw" ]; then
  ctx_pct=$(printf '%.0f' "$_ctx_raw")
  [ "$ctx_pct" -ge 80 ] && ctx="🔥 ${ctx_pct}%" || ctx="🧠 ${ctx_pct}%"
fi

# Working dir
workdir=""
[ -n "$_dir" ] && workdir="📂 $(basename "$_dir")"

# PR
pr=""
if [ -n "$_pr_num" ]; then
  case "$_pr_state" in
    approved)   pr="✅ #${_pr_num}" ;;
    changes_*)  pr="🔴 #${_pr_num}" ;;
    pending)    pr="👀 #${_pr_num}" ;;
    *)          pr="#${_pr_num}" ;;
  esac
fi

# Assemble: cost · model · ctx · dir · PR
parts=()
[ -n "$cost" ]    && parts+=("$cost")
[ -n "$model" ]   && parts+=("$model")
[ -n "$ctx" ]     && parts+=("$ctx")
[ -n "$workdir" ] && parts+=("$workdir")
[ -n "$pr" ]      && parts+=("$pr")

result=""
for part in "${parts[@]}"; do
  result="${result:+$result · }$part"
done
printf '%s\n' "$result"
