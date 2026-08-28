#!/bin/bash
# Script เรียกหน้าเพจ ksstat เพื่อให้สคริปต์ส่งค่าไปฐานข้อมูล
# และส่งผลไป Telegram

set -u
umask 077

URL="https://innovation.oas.psu.ac.th/ksstat/"
WORKSPACE_DIR="${INNOVATION_NEWS_WORKSPACE_DIR:-/home/kittisak/.openclaw/workspace}"
ENV_FILE="${INNOVATION_NEWS_ENV_FILE:-$WORKSPACE_DIR/.env}"
LOG_FILE="$WORKSPACE_DIR/logs/ksstat-trigger.log"

read_env_value() {
    key=$1
    awk -F= -v key="$key" '
        $0 ~ "^" key "=" {
            value = substr($0, length(key) + 2)
            gsub(/^[[:space:]\047\"]+|[[:space:]\047\"]+$/, "", value)
            print value
            exit
        }
    ' "$ENV_FILE"
}

if [ ! -f "$ENV_FILE" ]; then
    echo "Configuration file not found: $ENV_FILE" >&2
    exit 78
fi

TELEGRAM_USER_ID="${TELEGRAM_CHAT_ID:-$(read_env_value TELEGRAM_CHAT_ID)}"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(read_env_value OPENCLAW_BIN)}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
KSSTAT_CA_BUNDLE="${KSSTAT_CA_BUNDLE:-$(read_env_value KSSTAT_CA_BUNDLE)}"

if [ -z "$TELEGRAM_USER_ID" ]; then
    echo "Missing TELEGRAM_CHAT_ID in canonical root .env" >&2
    exit 78
fi
if ! command -v "$OPENCLAW_BIN" >/dev/null 2>&1; then
    echo "OPENCLAW_BIN is not executable or not on PATH" >&2
    exit 69
fi
if [ -n "$KSSTAT_CA_BUNDLE" ] && [ ! -r "$KSSTAT_CA_BUNDLE" ]; then
    echo "KSSTAT_CA_BUNDLE is not readable" >&2
    exit 78
fi

# สร้างโฟลเดอร์ logs ถ้ายังไม่มี
mkdir -p "$(dirname "$LOG_FILE")"

# บันทึกเวลา (ใช้ timezone ไทย)
DATE=$(TZ='Asia/Bangkok' date '+%Y-%m-%d %H:%M:%S')
DATE_TH=$(TZ='Asia/Bangkok' date '+%Y-%m-%d %H:%M:%S น.')

# ส่ง HTTP request ไปยังหน้าเพจ
echo "[$DATE] เรียกหน้าเพจ: $URL" >> "$LOG_FILE"

CURL_ARGS=(-sS -o /dev/null -w "%{http_code}" -L --max-time 30)
if [ -n "$KSSTAT_CA_BUNDLE" ]; then
    CURL_ARGS+=(--cacert "$KSSTAT_CA_BUNDLE")
fi
if ! HTTP_CODE=$(curl "${CURL_ARGS[@]}" "$URL"); then
    HTTP_CODE="000"
fi

# กำหนดสถานะ
if [ "$HTTP_CODE" = "200" ]; then
    STATUS="✅ สำเร็จ (HTTP $HTTP_CODE)"
    EMOJI="✅"
else
    STATUS="❌ ล้มเหลว (HTTP $HTTP_CODE)"
    EMOJI="❌"
fi

# สร้างข้อความแจ้งเตือน
MESSAGE="📊 Trigger ksstat

$EMOJI $STATUS
🌐 URL: $URL
🕐 เวลา: $DATE_TH

หน้าเพจถูกเรียกให้สคริปต์ส่งค่าไปฐานข้อมูล"

# ส่งไป Telegram (ใช้ path ที่ถูกต้อง)
if "$OPENCLAW_BIN" message send \
    --channel telegram \
    --target "$TELEGRAM_USER_ID" \
    --message "$MESSAGE" \
    >/dev/null 2>&1; then
    NOTIFY_STATUS="ส่งแจ้งเตือนไป Telegram แล้ว"
else
    NOTIFY_STATUS="ส่งแจ้งเตือนไป Telegram ไม่สำเร็จ"
fi

# บันทึกลง log
echo "[$DATE] เรียกหน้าเพจ: $URL" >> "$LOG_FILE"
echo "[$DATE] $STATUS" >> "$LOG_FILE"
echo "[$DATE] $NOTIFY_STATUS" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
