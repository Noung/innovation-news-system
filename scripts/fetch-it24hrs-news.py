#!/usr/bin/env python3
# Script ดึงข่าว IT จาก iT24Hrs และส่งไป Telegram

import xml.etree.ElementTree as ET
import subprocess
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = SCRIPT_DIR.parent

def load_env_file(env_path):
    if not env_path.exists():
        return False
    with env_path.open('r', encoding='utf-8') as env_handle:
        for raw_line in env_handle:
            line = raw_line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                    continue
                if key != 'INNOVATION_NEWS_ENV_FILE':
                    os.environ[key] = value.strip().strip('"').strip("'")
    return True

explicit_env_file = os.getenv('INNOVATION_NEWS_ENV_FILE', '').strip()
if explicit_env_file:
    explicit_env_path = Path(explicit_env_file).expanduser()
    if not load_env_file(explicit_env_path):
        raise SystemExit(
            f'Explicit INNOVATION_NEWS_ENV_FILE does not exist: {explicit_env_path}'
        )
else:
    loaded_env_file = False
    for env_path in (DEFAULT_WORKSPACE / '.env', SCRIPT_DIR / '.env'):
        if load_env_file(env_path):
            loaded_env_file = True
            break
    if not loaded_env_file:
        raise SystemExit(
            'No Innovation News environment file found; expected workspace-root .env '
            'or temporary scripts/.env fallback'
        )

WORKSPACE = Path(os.getenv('INNOVATION_NEWS_WORKSPACE_DIR', str(DEFAULT_WORKSPACE))).expanduser()
CACHE_FILE = WORKSPACE / "cache" / "it24hrs-last-news.txt"
TELEGRAM_USER_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
OPENCLAW_BIN = os.getenv('OPENCLAW_BIN', 'openclaw').strip()

if not TELEGRAM_USER_ID:
    raise SystemExit('Missing TELEGRAM_CHAT_ID in the canonical environment file')

# สร้างโฟลเดอร์ cache
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

# ดึง RSS feed
rss_url = "https://it24hrs.com/feed"
result = subprocess.run(["curl", "-s", "-L", rss_url], capture_output=True, text=True)
rss_content = result.stdout

# Parse XML
root = ET.fromstring(rss_content)

# Namespace ของ RSS
namespaces = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

# ดึง 5 ข่าวล่าสุดเพื่อตรวจสอบ
items_to_check = root.findall('.//item')[:5]

# โหลด cache เดิม
cache = set()
if CACHE_FILE.exists():
    with open(CACHE_FILE, 'r') as f:
        cache = set(line.strip() for line in f if line.strip())

# ตัวแปรติดตาม
has_new_news = False
newest_date = None

# แปลงเดือนภาษาอังกฤษ → ไทย
MONTH_MAP = {
    'Jan': 'ม.ค.', 'Feb': 'ก.พ.', 'Mar': 'มี.ค.', 'Apr': 'เม.ย.',
    'May': 'พ.ค.', 'Jun': 'มิ.ย.', 'Jul': 'ก.ค.', 'Aug': 'ส.ค.',
    'Sep': 'ก.ย.', 'Oct': 'ต.ค.', 'Nov': 'พ.ย.', 'Dec': 'ธ.ค.'
}

def format_date(pub_date_str):
    """แปลงวันที่ RSS → รูปแบบไทย"""
    try:
        dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
        dt_th = dt + timedelta(hours=7)
        month_th = MONTH_MAP.get(dt.strftime('%b'), dt.strftime('%b'))
        return f"{dt_th.day} {month_th} {dt_th.year}, {dt_th.hour:02d}:{dt_th.minute:02d} น."
    except:
        return pub_date_str

def clean_html(html_text):
    """ลบ HTML tags และ entities"""
    if not html_text:
        return ""
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', html_text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#8230;', '...')
    text = ' '.join(text.split())
    return text

def send_telegram(message):
    """ส่งข้อความไป Telegram"""
    if not TELEGRAM_USER_ID:
        return False
    result = subprocess.run([
        OPENCLAW_BIN,
        "message", "send",
        "--channel", "telegram",
        "--target", TELEGRAM_USER_ID,
        "--message", message
    ], capture_output=True, text=True)
    return result.returncode == 0

# ตรวจสอบข่าวทั้ง 5 ข่าว
new_items_found = []

for item in items_to_check:
    title_elem = item.find('title')
    title = title_elem.text if title_elem is not None else ""
    title = clean_html(title)

    link_elem = item.find('link')
    link = link_elem.text if link_elem is not None else ""

    pub_date_elem = item.find('pubDate')
    pub_date = pub_date_elem.text if pub_date_elem is not None else ""
    formatted_date = format_date(pub_date) if pub_date else ""

    # บันทึกวันที่ข่าวล่าสุด
    if pub_date and (newest_date is None or pub_date > newest_date):
        newest_date = pub_date

    # หมวดหมู่
    categories = []
    category_elems = item.findall('category')
    for cat_elem in category_elems:
        cat_text = cat_elem.text
        if cat_text and cat_text not in categories:
            cat_text = clean_html(cat_text)
            if cat_text and "รายการ" not in cat_text:
                categories.append(cat_text)
                if len(categories) >= 4:
                    break
    category_str = " • ".join(categories) if categories else "ทั่วไป"

    desc_elem = item.find('description')
    description = desc_elem.text if desc_elem is not None else ""
    description = clean_html(description)
    description = description[:150] + "..." if len(description) > 150 else description

    # เก็บข่าวที่ไม่อยู่ใน cache (ข่าวใหม่)
    if link and link not in cache:
        new_items_found.append({
            'title': title,
            'link': link,
            'date': formatted_date,
            'categories': category_str,
            'description': description
        })

# หากมีข่าวใหม่ → ส่งไป Telegram
if new_items_found:
    for item in new_items_found:
        message = f"""📰 ข่าว IT ล่าสุดจาก iT24Hrs

🤖 {item['title']}
📅 {item['date']}
🏷️ {item['categories']}
📝 {item['description']}
🔗 {item['link']}"""

        success = send_telegram(message)

        # บันทึกลง cache (บันทึกเสมอ ไม่ว่าจะส่งสำเร็จหรือไม่)
        with open(CACHE_FILE, 'a') as f:
            f.write(f"{item['link']}\n")

        if success:
            print(f"✅ ส่งข่าว: {item['title']}")
        else:
            print(f"❌ ส่งข่าวไม่สำเร็จ: {item['title']}")

    has_new_news = True
else:
    # ไม่มีข่าวใหม่ → ส่งแจ้งไป Telegram ทุกครั้ง
    print("ℹ️ ขณะนี้ยังไม่มีข่าวใหม่")

    message = """📊 ตรวจสอบข่าว IT จาก iT24Hrs

ℹ️ ขณะนี้ยังไม่มีข่าวใหม่"""

    success = send_telegram(message)
    if success:
        print("✅ ส่งแจ้งไม่มีข่าวใหม่แล้ว")
    else:
        print("❌ ส่งแจ้งไม่มีข่าวใหม่ไม่สำเร็จ")
