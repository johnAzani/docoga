#!/bin/bash
echo "Testing Telegram posting locally..."
echo ""
echo "Enter your TELEGRAM_BOT_TOKEN:"
read -r BOT_TOKEN
echo ""
echo "Enter your TELEGRAM_CHAT_ID (e.g., @docogadaily or -1001234567890):"
read -r CHAT_ID

export TELEGRAM_BOT_TOKEN="$BOT_TOKEN"
export TELEGRAM_CHAT_ID="$CHAT_ID"

python3 scripts/generate_telegram_content.py
python3 scripts/post_telegram.py
