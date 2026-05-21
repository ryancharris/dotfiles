#!/bin/sh
# Write BEL to the agent's controlling pts so kitty's `bell_on_tab` symbol
# appears on the tab. Used by claude and gemini Notification hooks.
# Hook subprocesses don't inherit /dev/tty, so we walk up ppid to find an
# ancestor with a real pts device.
#
# Debug log at /tmp/ring-bell.log; tail it while testing.
log=/tmp/ring-bell.log
ts=$(date '+%Y-%m-%d %H:%M:%S')
{
  echo "--- $ts pid=$$ ppid=$PPID ---"
  echo "argv: $*"
  echo "user: $(id -un)  euid: $(id -u)"
  echo "stdin tty? $(if [ -t 0 ]; then echo yes; else echo no; fi)  stdout tty? $(if [ -t 1 ]; then echo yes; else echo no; fi)"
  echo "ancestor chain:"
  p=$$
  i=0
  while [ -n "$p" ] && [ "$p" != "1" ] && [ $i -lt 12 ]; do
    line=$(ps -o pid,ppid,tty,command -p "$p" 2>/dev/null | tail -1)
    echo "  $line"
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
    i=$((i+1))
  done
} >> "$log" 2>&1

p=$$
found=
while [ -n "$p" ] && [ "$p" != "1" ]; do
  t=$(ps -o tty= -p "$p" 2>/dev/null | tr -d ' ')
  case "$t" in
    ttys*|tty[0-9]*|pts/*)
      found="/dev/$t"
      break
      ;;
  esac
  p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
done

if [ -z "$found" ]; then
  echo "RESULT: no ancestor tty found" >> "$log"
  exit 1
fi

if [ ! -w "$found" ]; then
  echo "RESULT: $found not writable (owner=$(stat -f %u "$found" 2>/dev/null))" >> "$log"
  exit 1
fi

if printf '\a' > "$found" 2>>"$log"; then
  echo "RESULT: wrote BEL to $found" >> "$log"
  exit 0
else
  echo "RESULT: write to $found failed exit=$?" >> "$log"
  exit 1
fi
