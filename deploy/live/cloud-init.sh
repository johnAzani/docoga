#!/bin/bash
# DocOga Live — paste this whole box into Oracle's "Cloud-init script" field when creating the
# instance (Advanced options → Management → Initialization script). Replace PASTE_STREAM_KEY_HERE
# with the key from YouTube Studio → Go live → Manage → "DocOga Live key (reusable)" → copy.
# Shape: VM.Standard.E2.1.Micro (Always Free). Image: Canonical Ubuntu 24.04 Minimal.
curl -fsSL https://raw.githubusercontent.com/johnAzani/docoga/main/deploy/live/install.sh -o /root/install.sh
bash /root/install.sh "PASTE_STREAM_KEY_HERE"
