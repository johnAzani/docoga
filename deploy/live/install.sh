#!/bin/bash
# DocOga Live — install the always-on stream on an Oracle Always Free VM (Ubuntu 22.04/24.04).
#
# Owner, 26 Oct 2026: "I don't want to run it on GitHub … Let's do it in Oracle." This is the
# whole install: ffmpeg + python3 + a clone of the public repo + one systemd service that runs
# `tools/yt_live.py serve` forever. The only secret on the machine is the YouTube stream key,
# written to /etc/docoga-live/stream_key (root, 0600). Nothing else of ours lives here: the
# loop (loop.json + segments) is pulled from the public live-library release, and a timer
# pulls the repo every hour so a fix merged to main reaches the VM without a visit.
#
# Run as root, once:   bash install.sh <STREAM_KEY>
# or paste deploy/live/cloud-init.sh into the instance's "cloud-init script" box at creation.
# Re-running is safe (idempotent). Rotate the key: write the new one to the key file; the
# service reads it on every (re)start:  systemctl restart docoga-live
set -euo pipefail

KEY="${1:-${DOCOGA_STREAM_KEY:-}}"
REPO_URL="${DOCOGA_REPO:-https://github.com/johnAzani/docoga.git}"
BRANCH="${DOCOGA_BRANCH:-main}"
APP=/opt/docoga
ETC=/etc/docoga-live
LIB=/var/lib/docoga-live

if [ "$(id -u)" -ne 0 ]; then echo "run as root (sudo bash install.sh <STREAM_KEY>)" >&2; exit 2; fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends ffmpeg python3 python3-requests git ca-certificates curl >/dev/null

# Oracle's Ubuntu images ship an iptables policy that drops everything but SSH. Outbound RTMPS
# (443) is allowed by default; nothing inbound is needed, so no firewall change is made.

mkdir -p "$ETC" "$LIB"
chmod 700 "$ETC"
if [ -n "$KEY" ]; then
  umask 077
  printf '%s\n' "$KEY" > "$ETC/stream_key"
  umask 022
fi
if [ ! -s "$ETC/stream_key" ]; then
  echo "no stream key: pass it as the first argument (YouTube Studio → Go live → Manage → DocOga Live key (reusable))" >&2
  exit 3
fi
chmod 600 "$ETC/stream_key"

if [ -d "$APP/.git" ]; then
  git -C "$APP" fetch -q origin "$BRANCH" && git -C "$APP" reset -q --hard "origin/$BRANCH"
else
  rm -rf "$APP"
  git clone -q --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP"
fi

install -m 0644 "$APP/deploy/live/docoga-live.service" /etc/systemd/system/docoga-live.service
install -m 0644 "$APP/deploy/live/docoga-live-pull.service" /etc/systemd/system/docoga-live-pull.service
install -m 0644 "$APP/deploy/live/docoga-live-pull.timer" /etc/systemd/system/docoga-live-pull.timer
systemctl daemon-reload
systemctl enable --now docoga-live-pull.timer >/dev/null
systemctl enable docoga-live >/dev/null
systemctl restart docoga-live
sleep 3
systemctl --no-pager --lines=5 status docoga-live || true
echo "DocOga Live installed. Logs: journalctl -u docoga-live -f"
