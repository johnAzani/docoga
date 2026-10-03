#!/bin/bash
# Quick test: Send a formatted message to @docogadaily
# Usage: ./send_test_post.sh

BOT_TOKEN="8852331279:AAHU8f5hfM0GfkU5K0O5y1ZJ4UCahpbqBSI"
CHAT_ID="@docogadaily"

MESSAGE='🏠 *DAILY DOCUMENT TIP* 🏠

Renting in Lagos? Here'\''s what you MUST know about *Caution Fees*:

💡 Many landlords charge ₦50k–₦200k as caution fee but refuse to refund when you move out!

✅ *How to Protect Yourself:*
1️⃣ Get a written receipt
2️⃣ Include it in your tenancy agreement
3️⃣ Take photos of the apartment before moving in
4️⃣ Request a move-out inspection

📋 *Need proper documents?*
DocOga has templates for:
• Tenancy Agreements
• Rent Receipts
• Notice to Quit
• Caution Fee Receipts

👉 Visit: https://docoga.com.ng

🔔 *Subscribe for daily tips!*'

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{
    \"chat_id\": \"${CHAT_ID}\",
    \"text\": $(echo "$MESSAGE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
    \"parse_mode\": \"Markdown\"
  }" | python3 -c "import sys,json; r=json.load(sys.stdin); print('✅ Sent! Message ID:', r['result']['message_id']) if r.get('ok') else print('❌ Error:', r.get('description','Unknown'))"