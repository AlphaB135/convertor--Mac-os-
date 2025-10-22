#!/usr/bin/env bash
set -euo pipefail

PLIST_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/launch_agent/com.alphab.autoconvert.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.alphab.autoconvert.plist"

if [[ ! -f "$PLIST_SRC" ]]; then
  echo "Source plist not found: $PLIST_SRC" >&2
  exit 1
fi

if [[ ! -f "$HOME/convertor/.venv/bin/python" ]]; then
  cat >&2 <<'EOF'
Virtualenv not found at ~/convertor/.venv/bin/python.
Create it first:
  python3 -m venv ~/convertor/.venv
  source ~/convertor/.venv/bin/activate
  pip install -r ~/convertor/requirements.txt
EOF
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"

if launchctl list | grep -q "com.alphab.autoconvert"; then
  launchctl unload "$PLIST_DEST"
fi

launchctl load -w "$PLIST_DEST"

echo "Launch agent installed and loaded. It will now watch ~/convertor/input automatically."
