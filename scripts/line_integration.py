#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OAR Notify Integration Module
Sends innovation news to LINE groups via OAR Notify API
Updated: 2026-03-25 (Fixed: UTF-8 Binary Post & Default Benefits logic)
"""

import os
import requests
import json
import re
import html
from typing import Dict, Optional
from datetime import datetime
from urllib.parse import parse_qsl, urlparse

# รายชื่อเดือนไทย
THAI_MONTH_NAMES = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

# Mapping Emoji
BENEFIT_EMOJI_MAP = {
    "ความสามารถในการแข่งขัน": "🏆",
    "การลดต้นทุนและเพิ่มประสิทธิภาพ": "⚡",
    "การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน": "💻",
    "การพัฒนาทักษะและการเรียนรู้": "🎓",
    "การใช้งาน AI และเทคโนโลยีขั้นสูง": "🤖",
    "ความปลอดภัยและความเป็นส่วนตัว": "🛡️",
    "การสร้างนวัตกรรมและการเปลี่ยนแปลง": "🚀",
    "การปรับตัวต่อเทรนด์และตลาด": "📊",
    "การจัดการข้อมูลและวิเคราะห์ข้อมูล": "🔍",
    "การสร้างประสบการณ์ลูกค้าและบริการ": "🤝",
    "การเชื่อมต่อและการทำงานร่วมกัน": "👥",
    "การพัฒนาเทคโนโลยีและโครงสร้าง": "💼",
    "การสนับสนุนนวัตกรรมและสตาร์ทอัพ": "🚀",
    "การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน": "💰",
    "การใช้เทคโนโลยีสีเขียวและยั่งยืน": "🇪🇺",
    "การพัฒนาสุขภาพและการดูแลโรงพยาบาล": "🏥",
    "การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์": "🤖",
    "การพัฒนาภาคศึกษาและเมืองอัจฉริยะ": "🎯",
    "การทำธุรกิจในยุคดิจิทัล": "📈",
    "การวิจัยและพัฒนาองค์ความรู้": "🔬"
}

DEFAULT_BENEFITS = [
    "การสร้างนวัตกรรมและการเปลี่ยนแปลง",
    "การวิจัยและพัฒนาองค์ความรู้",
    "การปรับตัวต่อเทรนด์และตลาด",
]

def log_message(message: str):
    print(message)

def get_line_config():
    """ดึงค่าคอนฟิก LINE จาก Environment"""
    api_url = os.getenv('LINE_API_URL', '').strip()
    parsed_api_url = urlparse(api_url) if api_url else None
    if api_url and not (
        parsed_api_url.scheme.lower() == 'https' and parsed_api_url.hostname
        and not parsed_api_url.username and not parsed_api_url.password
        and not any(
            re.fullmatch(
                r'(?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|auth)',
                key,
                re.IGNORECASE,
            )
            for key, _value in parse_qsl(parsed_api_url.query, keep_blank_values=True)
        )
    ):
        log_message('  LINE API URL must use HTTPS; integration disabled')
        api_url = ''
    ca_bundle = os.getenv('LINE_CA_BUNDLE', '').strip()
    verify_tls_value = os.getenv('LINE_VERIFY_TLS', '1').strip().lower()
    if verify_tls_value not in {'1', 'true', 'yes', 'on'}:
        log_message('  LINE_VERIFY_TLS cannot disable certificate verification; using secure default')
    return {
        'url': api_url,
        'api_key': os.getenv('LINE_API_KEY', '').strip(),
        'verify_tls': ca_bundle if ca_bundle else True,
    }

def is_line_configured() -> bool:
    config = get_line_config()
    return all([config['url'], config['api_key']])

def format_thai_date_simple(date_val) -> str:
    """แปลงวันที่เป็นรูปแบบไทยสำหรับ LINE"""
    dt = None
    if isinstance(date_val, datetime):
        dt = date_val
    elif isinstance(date_val, str) and date_val.strip() != "":
        clean_date = re.sub(r'\s+[\+\-]\d{4}$', '', date_val.strip())
        formats = ['%a, %d %b %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']
        for fmt in formats:
            try:
                dt = datetime.strptime(clean_date, fmt)
                break
            except:
                continue
    
    if not dt:
        dt = datetime.now()
        
    thai_year = dt.year + 543
    thai_month = THAI_MONTH_NAMES[dt.month - 1]
    return f"{dt.day} {thai_month} {thai_year}"

def resolve_display_date(article: Dict) -> str:
    published_date_th = article.get('published_date_th')
    if published_date_th:
        return published_date_th
    return format_thai_date_simple(article.get('date'))

def format_line_message(article: Dict) -> str:
    """จัดรูปแบบข้อความสำหรับ LINE พร้อมจัดการกรณีไม่มีประโยชน์ที่ระบุ"""
    title = article.get('title', 'ไม่มีหัวข้อ')
    summary = article.get('summary', '')
    benefits = []
    for benefit in article.get('benefits', []) or []:
        if benefit in BENEFIT_EMOJI_MAP and benefit not in benefits:
            benefits.append(benefit)
        if len(benefits) == 3:
            break

    for fallback_benefit in DEFAULT_BENEFITS:
        if fallback_benefit not in benefits:
            benefits.append(fallback_benefit)
        if len(benefits) == 3:
            break
    link = article.get('link', '')
    source = article.get('source', 'ไม่ระบุแหล่งข้อมูล')

    thai_date = resolve_display_date(article)

    # ใช้ summary ถ้ามี ถ้าไม่มีให้ใช้ title แทน
    summary_text = summary.strip()
    if not summary_text:
        summary_text = title

    msg = f"✨ Innovation Daily Update\n\n"
    msg += f"หัวข้อ: {title}\n"
    msg += f"เผยแพร่เมื่อ: {thai_date}\n"
    msg += f"แหล่งข้อมูล: {source}\n\n"
    msg += f"รายละเอียดโดยสรุป: {summary_text[:800]}...\n\n"
    
    msg += "ประโยชน์ต่อองค์กร:\n"
    for b in benefits:
        emoji = BENEFIT_EMOJI_MAP.get(b, "✅")
        # msg += f"{emoji} {b}\n"
        msg += f"✅ {b}\n"
    msg += "\n"
        
    msg += f"อ่านต่อ: {link}\n\n"

    msg += "✍ ค้นหาและนำเสนอข้อมูลโดย Inno Bot"
    return msg

def send_to_line(article: Dict, max_retries: int = 2) -> bool:
    """ส่งข้อมูลแบบ Raw UTF-8 Bytes เพื่อป้องกันปัญหาการเข้ารหัสตัวอักษรพิเศษ"""
    config = get_line_config()
    
    if not is_line_configured():
        log_message("  ⚠️ LINE API Key not configured")
        return False

    message_text = format_line_message(article)
    
    payload = {
        "msg_detail": message_text
    }
    
    # กำหนด Header ให้ชัดเจนว่าข้อมูลเป็น UTF-8
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {config['api_key']}"
    }

    for attempt in range(max_retries + 1):
        try:
            # ใช้ json.dumps แบบไม่แปลง ascii และ encode เป็น bytes ก่อนส่ง
            binary_payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            
            response = requests.post(
                config['url'],
                headers=headers,
                data=binary_payload,
                timeout=20,
                verify=config.get('verify_tls', True)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return True
                else:
                    log_message(f"  ❌ LINE API Error: {result.get('message')}")
            else:
                log_message(f"  ❌ LINE HTTP Error {response.status_code}")
                
        except Exception as e:
            log_message(f"  ❌ LINE Attempt {attempt+1} failed: {str(e)}")
            
    return False
