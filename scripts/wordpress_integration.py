#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WordPress Integration Module for Innovation News
Strict Mapping with verified PTB Custom Fields: innovation_tip_content, innovation_tip_url, innovation_tip_video
Updated: 2026-03-25 (Enhanced: Added Organization Benefits section)
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, List, Optional
import html
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlparse

# รายชื่อเดือนไทย
THAI_MONTH_NAMES = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

def log_message(message: str):
    """บันทึกข้อความลงใน Console"""
    print(message)

def get_wp_config():
    """ดึงค่าคอนฟิกจาก Environment"""
    api_url = os.getenv('WP_API_URL', '').strip().rstrip('/')
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
        log_message('  WordPress API URL must use HTTPS; integration disabled')
        api_url = ''
    ca_bundle = os.getenv('WP_CA_BUNDLE', '').strip()
    verify_tls_value = os.getenv('WP_VERIFY_TLS', '1').strip().lower()
    if verify_tls_value not in {'1', 'true', 'yes', 'on'}:
        log_message('  WP_VERIFY_TLS cannot disable certificate verification; using secure default')
    return {
        'url': api_url,
        'user': os.getenv('WP_USERNAME', '').strip(),
        'pwd': os.getenv('WP_APP_PASSWORD', '').strip(),
        'verify_tls': ca_bundle if ca_bundle else True,
        'benefit_taxonomy_rest_base': os.getenv(
            'WP_BENEFIT_TAXONOMY_REST_BASE',
            'organization-benefits'
        ).strip().strip('/')
    }

def is_wordpress_configured() -> bool:
    config = get_wp_config()
    return all([config['url'], config['user'], config['pwd']])

def format_thai_date(date_val) -> str:
    """แปลงวันที่เป็นรูปแบบไทย: 25 มีนาคม 2569 09:18 น."""
    dt = None
    
    if isinstance(date_val, datetime):
        dt = date_val
    elif isinstance(date_val, str) and date_val.strip() != "":
        clean_date = re.sub(r'\s+[\+\-]\d{4}$', '', date_val.strip())
        if re.match(r'^\d{4}-\d{2}-\d{2}', clean_date):
            try:
                dt = datetime.fromisoformat(clean_date.replace('Z', '+00:00'))
            except ValueError:
                dt = None
        formats = [
            '%a, %d %b %Y %H:%M:%S',
            '%d/%m/%Y %H:%M'
        ]
        if dt is None:
            for fmt in formats:
                try:
                    dt = datetime.strptime(clean_date, fmt)
                    break
                except ValueError:
                    continue
    
    if not dt:
        dt = datetime.now()
        
    thai_year = dt.year + 543
    thai_month = THAI_MONTH_NAMES[dt.month - 1]
    return f"{dt.day} {thai_month} {thai_year} {dt.strftime('%H:%M')} น."

def resolve_display_date(article: Dict) -> str:
    published_date_th = article.get('published_date_th')
    if published_date_th:
        return published_date_th

    fallback_value = article.get('date')
    fallback_date = format_thai_date(fallback_value)
    if fallback_date.endswith(" เธ."):
        return fallback_date.rsplit(' ', 2)[0]
    return fallback_date

SOURCE_MAPPING = {
    'NIA (สำนักงานนวัตกรรมแห่งชาติ)': 'NIA',
    'ETDA (สพธอ.)': 'ETDA',
    'Techsauce': 'Techsauce',
    'NSTDA (สวทช.)': 'NSTDA',
    'RYT9': 'RYT9',
    'iT24Hrs': 'iT24Hrs',
    'TechTalkThai': 'TechTalkThai',
    'NECTEC (สวทช.)': 'NECTEC',
    'Innomatter': 'Innomatter',
    'สำนักงานการวิจัยแห่งชาติ (วช.)': 'NRIIS'
}

BENEFITS_PER_ARTICLE = 3
DEFAULT_BENEFITS = [
    'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
    'การวิจัยและพัฒนาองค์ความรู้',
    'การปรับตัวต่อเทรนด์และตลาด',
]

# Canonical mapping shared with the WordPress plugin. Term IDs are resolved
# from these stable slugs because IDs differ between WordPress environments.
BENEFIT_TERM_SLUGS = {
    'ความสามารถในการแข่งขัน': 'competitiveness',
    'การลดต้นทุนและเพิ่มประสิทธิภาพ': 'cost-efficiency',
    'การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน': 'digital-transformation',
    'การพัฒนาทักษะและการเรียนรู้': 'skills-learning',
    'การใช้งาน AI และเทคโนโลยีขั้นสูง': 'ai-advanced-technology',
    'ความปลอดภัยและความเป็นส่วนตัว': 'security-privacy',
    'การสร้างนวัตกรรมและการเปลี่ยนแปลง': 'innovation-change',
    'การปรับตัวต่อเทรนด์และตลาด': 'trends-market-adaptation',
    'การจัดการข้อมูลและวิเคราะห์ข้อมูล': 'data-management-analytics',
    'การสร้างประสบการณ์ลูกค้าและบริการ': 'customer-experience-service',
    'การเชื่อมต่อและการทำงานร่วมกัน': 'connectivity-collaboration',
    'การพัฒนาเทคโนโลยีและโครงสร้าง': 'technology-infrastructure',
    'การสนับสนุนนวัตกรรมและสตาร์ทอัพ': 'innovation-startup-support',
    'การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน': 'blockchain-fintech',
    'การใช้เทคโนโลยีสีเขียวและยั่งยืน': 'green-technology-sustainability',
    'การพัฒนาสุขภาพและการดูแลโรงพยาบาล': 'healthcare-hospital-care',
    'การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์': 'generative-ai',
    'การพัฒนาภาคศึกษาและเมืองอัจฉริยะ': 'education-smart-city',
    'การทำธุรกิจในยุคดิจิทัล': 'digital-business',
    'การวิจัยและพัฒนาองค์ความรู้': 'research-knowledge-development',
}

_BENEFIT_TERM_ID_CACHE = {}


def normalize_article_benefits(benefits) -> List[str]:
    """Return exactly three distinct benefits from the controlled vocabulary."""
    if isinstance(benefits, str):
        benefits = [benefits]

    normalized_benefits = []
    for benefit in benefits or []:
        if benefit not in BENEFIT_TERM_SLUGS or benefit in normalized_benefits:
            continue
        normalized_benefits.append(benefit)
        if len(normalized_benefits) == BENEFITS_PER_ARTICLE:
            return normalized_benefits

    for fallback_benefit in DEFAULT_BENEFITS:
        if fallback_benefit not in normalized_benefits:
            normalized_benefits.append(fallback_benefit)
        if len(normalized_benefits) == BENEFITS_PER_ARTICLE:
            break

    return normalized_benefits


def _response_json(response):
    try:
        return response.json()
    except Exception:
        return None


def resolve_wordpress_benefit_term_ids(
    benefits,
    config=None,
    max_retries: int = 2,
) -> Optional[List[int]]:
    """Resolve or create exactly three WordPress benefit terms by stable slug."""
    config = config or get_wp_config()
    normalized_benefits = normalize_article_benefits(benefits)
    taxonomy_rest_base = config.get('benefit_taxonomy_rest_base', '').strip().strip('/')
    if len(normalized_benefits) != BENEFITS_PER_ARTICLE or not taxonomy_rest_base:
        log_message("  ❌ Benefit taxonomy configuration is incomplete")
        return None

    endpoint = f"{config['url']}/wp/v2/{taxonomy_rest_base}"
    auth = HTTPBasicAuth(config['user'], config['pwd'])
    term_ids = []

    for benefit_name in normalized_benefits:
        slug = BENEFIT_TERM_SLUGS[benefit_name]
        cache_key = (config['url'], taxonomy_rest_base, slug)
        cached_term_id = _BENEFIT_TERM_ID_CACHE.get(cache_key)
        if cached_term_id:
            term_ids.append(cached_term_id)
            continue

        term_id = None
        for attempt in range(max(0, max_retries) + 1):
            try:
                response = requests.get(
                    endpoint,
                    auth=auth,
                    params={'slug': slug, 'per_page': 1},
                    headers={'User-Agent': 'Innovation-News-Bot/1.0'},
                    timeout=10,
                    verify=config.get('verify_tls', True)
                )
            except Exception as exc:
                if attempt < max_retries:
                    log_message(
                        f"  ⚠️ Retrying WordPress benefit lookup for '{slug}' "
                        f"after error: {str(exc)}"
                    )
                    continue
                log_message(f"  ❌ Cannot resolve WordPress benefit term '{slug}': {str(exc)}")
                return None

            payload = _response_json(response)
            if response.status_code == 200 and isinstance(payload, list) and payload:
                term_id = payload[0].get('id')
                break
            if response.status_code == 404:
                log_message(
                    "  ❌ WordPress benefit taxonomy endpoint was not found. "
                    "Install and activate the Innovation Tip Benefit Taxonomy plugin."
                )
                return None
            if response.status_code != 200:
                if response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                    log_message(
                        f"  ⚠️ Retrying WordPress benefit lookup for '{slug}' "
                        f"after HTTP {response.status_code}"
                    )
                    continue
                log_message(f"  ❌ Benefit taxonomy lookup failed for '{slug}' (HTTP {response.status_code})")
                return None

            try:
                create_response = requests.post(
                    endpoint,
                    auth=auth,
                    json={'name': benefit_name, 'slug': slug},
                    headers={'User-Agent': 'Innovation-News-Bot/1.0'},
                    timeout=15,
                    verify=config.get('verify_tls', True)
                )
            except Exception as exc:
                if attempt < max_retries:
                    log_message(
                        f"  ⚠️ Retrying WordPress benefit creation for '{slug}' "
                        f"after error: {str(exc)}"
                    )
                    continue
                log_message(f"  ❌ Cannot create WordPress benefit term '{slug}': {str(exc)}")
                return None

            create_payload = _response_json(create_response)
            if create_response.status_code == 201 and isinstance(create_payload, dict):
                term_id = create_payload.get('id')
            elif (
                create_response.status_code == 400
                and isinstance(create_payload, dict)
                and create_payload.get('code') == 'term_exists'
            ):
                term_id = (create_payload.get('data') or {}).get('term_id')
            else:
                if create_response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                    log_message(
                        f"  ⚠️ Retrying WordPress benefit creation for '{slug}' "
                        f"after HTTP {create_response.status_code}"
                    )
                    continue
                log_message(f"  ❌ Benefit taxonomy creation failed for '{slug}' (HTTP {create_response.status_code})")
                return None

            if term_id:
                break

        try:
            normalized_term_id = int(term_id)
        except (TypeError, ValueError):
            log_message(f"  ❌ WordPress returned an invalid term ID for '{slug}'")
            return None

        _BENEFIT_TERM_ID_CACHE[cache_key] = normalized_term_id
        term_ids.append(normalized_term_id)

    if len(term_ids) != BENEFITS_PER_ARTICLE or len(set(term_ids)) != BENEFITS_PER_ARTICLE:
        log_message("  ❌ WordPress benefit taxonomy did not resolve to three distinct terms")
        return None

    return term_ids

def check_duplicate_in_wordpress(article_title: str, config=None) -> Optional[int]:
    """ตรวจสอบบทความซ้ำใน WordPress ผ่าน REST API"""
    config = config or get_wp_config()
    if not config['url']: return None
    try:
        url = f"{config['url']}/wp/v2/innovation-tip"
        params = {'search': article_title, 'per_page': 5}
        response = requests.get(
            url,
            auth=HTTPBasicAuth(config['user'], config['pwd']),
            params=params,
            headers={'User-Agent': 'Innovation-News-Bot/1.0'},
            timeout=10,
            verify=config.get('verify_tls', True)
        )
        if response.status_code == 200:
            for post in response.json():
                post_title = html.unescape(post.get('title', {}).get('rendered', '')).strip()
                if post_title.lower() == article_title.lower():
                    return post.get('id')
    except: pass
    return None


def canonical_wordpress_url(post_payload: Dict) -> Optional[str]:
    """Return a safe canonical public URL supplied by the WordPress REST API."""
    raw_url = str(post_payload.get('link', '') or '').strip()
    parsed_url = urlparse(raw_url)
    if (
        parsed_url.scheme.lower() != 'https'
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
    ):
        return None
    return raw_url


def get_wordpress_post_url(post_id: int, config=None) -> Optional[str]:
    """Read the canonical URL of an existing published innovation-tip post."""
    config = config or get_wp_config()
    if not config.get('url') or not post_id:
        return None

    try:
        response = requests.get(
            f"{config['url']}/wp/v2/innovation-tip/{int(post_id)}",
            auth=HTTPBasicAuth(config['user'], config['pwd']),
            headers={'User-Agent': 'Innovation-News-Bot/1.0'},
            timeout=10,
            verify=config.get('verify_tls', True),
        )
        if response.status_code == 200:
            return canonical_wordpress_url(_response_json(response) or {})
        log_message(
            f"  ❌ Cannot read canonical URL for WordPress post {post_id} "
            f"(HTTP {response.status_code})"
        )
    except Exception as exc:
        log_message(f"  ❌ Cannot read canonical URL for WordPress post {post_id}: {str(exc)}")
    return None


def update_wordpress_post_benefits(post_id: int, term_ids: List[int], config=None) -> bool:
    """Ensure an existing WordPress post has the three selected benefit terms."""
    config = config or get_wp_config()
    taxonomy_rest_base = config.get('benefit_taxonomy_rest_base', '').strip().strip('/')
    if not taxonomy_rest_base:
        return False

    try:
        response = requests.post(
            f"{config['url']}/wp/v2/innovation-tip/{int(post_id)}",
            auth=HTTPBasicAuth(config['user'], config['pwd']),
            json={taxonomy_rest_base: term_ids},
            headers={'User-Agent': 'Innovation-News-Bot/1.0'},
            timeout=20,
            verify=config.get('verify_tls', True)
        )
        if response.status_code == 200:
            return True

        log_message(f"  ❌ Cannot update benefit taxonomy for WordPress post {post_id} (HTTP {response.status_code})")
    except Exception as exc:
        log_message(f"  ❌ Cannot update benefit taxonomy for WordPress post {post_id}: {str(exc)}")

    return False

def save_to_wordpress_result(article: Dict, content_hash: str = None, max_retries: int = 2) -> Dict:
    """Save an article with exactly three organization-benefit taxonomy terms."""
    config = get_wp_config()
    
    if not all([config['url'], config['user'], config['pwd']]):
        log_message("  ⚠️ WordPress credentials not configured")
        return {'post_id': None, 'created': False, 'status': 'not_configured'}

    benefits_list = normalize_article_benefits(article.get('benefits', []))
    article['benefits'] = benefits_list
    benefit_term_ids = resolve_wordpress_benefit_term_ids(
        benefits_list,
        config=config,
        max_retries=max_retries,
    )
    if not benefit_term_ids:
        log_message("  ❌ WordPress sync stopped because three benefit taxonomy terms were not available")
        return {
            'post_id': None,
            'created': False,
            'status': 'failed',
            'benefits': benefits_list,
            'benefit_term_ids': [],
        }

    existing_id = check_duplicate_in_wordpress(article['title'], config=config)
    if existing_id:
        if not update_wordpress_post_benefits(existing_id, benefit_term_ids, config=config):
            return {
                'post_id': existing_id,
                'created': False,
                'status': 'failed',
                'benefits': benefits_list,
                'benefit_term_ids': benefit_term_ids,
            }

        wordpress_url = get_wordpress_post_url(existing_id, config=config)
        if not wordpress_url:
            return {
                'post_id': existing_id,
                'created': False,
                'status': 'failed',
                'benefits': benefits_list,
                'benefit_term_ids': benefit_term_ids,
            }
        log_message(f"  ℹ️ Article already exists; benefit taxonomy updated (ID: {existing_id})")
        return {
            'post_id': existing_id,
            'created': False,
            'status': 'duplicate',
            'wordpress_url': wordpress_url,
            'taxonomy_updated': True,
            'benefits': benefits_list,
            'benefit_term_ids': benefit_term_ids,
        }

    source_name = SOURCE_MAPPING.get(article.get('source'), article.get('source'))
    display_date = resolve_display_date(article)

    # จัดการข้อมูลประโยชน์ต่อองค์กร (Benefits)
    benefits_plain = ""
    benefits_html = ""
    
    if benefits_list:
        # สำหรับ Plain Text (Meta Field)
        benefits_plain = "\n\n<strong>ประโยชน์ต่อองค์กร:</strong>\n" + "\n".join([f"• {b}" for b in benefits_list])
        # สำหรับ HTML (Standard Editor)
        benefits_html = "<strong>🚀 ประโยชน์ต่อองค์กร:</strong><ul>" + "".join([f"<li>{b}</li>" for b in benefits_list]) + "</ul>"

    # กลยุทธ์ที่ 2: PTB Content (รวม สรุป + ประโยชน์ + ที่มา)
    combined_content = f"{article.get('summary', '')}{benefits_plain}\n\n<strong>ที่มา:</strong> {source_name}\n<strong>เผยแพร่เมื่อ:</strong> {display_date}"

    # กลยุทธ์ที่ 1: แผนสำรอง (Standard WordPress Content)
    html_content = f"""
    <div class="innovation-tip-sync">
        <p>{article.get('summary', '')}</p>
        {benefits_html}
        <hr>
        <p><strong>ที่มา:</strong> {source_name}</p>
        <p><strong>วันที่:</strong> {display_date}</p>
        <p><strong>ลิงก์:</strong> <a href="{article.get('link', '')}" target="_blank">{article.get('link', '')}</a></p>
    </div>
    """

    meta_fields = {
        'ptb_innovation_tip_content': combined_content,
        'ptb_innovation_tip_url': article.get('link', ''),
        'ptb_innovation_tip_video': ''
    }

    post_data = {
        'title': article['title'],
        'content': html_content,
        'status': 'publish',
        'meta': meta_fields,
        config['benefit_taxonomy_rest_base']: benefit_term_ids,
    }

    for attempt in range(max_retries + 1):
        try:
            url = f"{config['url']}/wp/v2/innovation-tip"
            response = requests.post(
                url,
                auth=HTTPBasicAuth(config['user'], config['pwd']),
                json=post_data,
                headers={'User-Agent': 'Innovation-News-Bot/1.0'},
                timeout=30,
                verify=config.get('verify_tls', True)
            )

            if response.status_code == 201:
                response_payload = _response_json(response) or {}
                post_id = response_payload.get('id')
                wordpress_url = canonical_wordpress_url(response_payload)
                if not wordpress_url:
                    log_message("  ❌ WordPress create response did not contain a valid canonical HTTPS URL")
                    return {
                        'post_id': post_id,
                        'created': False,
                        'status': 'failed',
                        'benefits': benefits_list,
                        'benefit_term_ids': benefit_term_ids,
                    }
                log_message(f"  ✅ Saved to WordPress (ID: {post_id})")
                return {
                    'post_id': post_id,
                    'created': True,
                    'status': 'created',
                    'wordpress_url': wordpress_url,
                    'benefits': benefits_list,
                    'benefit_term_ids': benefit_term_ids,
                }
            
            elif response.status_code == 400:
                log_message(f"  ❌ API 400: {response.json().get('message')}")
                if "meta" in response.text:
                    log_message("  ⚠️ Meta rejected. Retrying without meta...")
                    if 'meta' in post_data: del post_data['meta']
                    continue
            else:
                log_message(f"  ❌ API error {response.status_code}")
        
        except Exception as e:
            log_message(f"  ❌ Attempt {attempt+1} failed: {str(e)}")

    return {
        'post_id': None,
        'created': False,
        'status': 'failed',
        'benefits': benefits_list,
        'benefit_term_ids': benefit_term_ids,
    }

def save_to_wordpress(article: Dict, content_hash: str = None, max_retries: int = 2) -> Optional[int]:
    result = save_to_wordpress_result(article, content_hash=content_hash, max_retries=max_retries)
    if result.get('status') not in {'created', 'duplicate'}:
        return None
    return result.get('post_id')

def test_wordpress_connection() -> bool:
    """Verify the CPT accepts the taxonomy field and all controlled terms exist."""
    config = get_wp_config()
    try:
        auth = HTTPBasicAuth(config['user'], config['pwd'])
        post_response = requests.get(
            f"{config['url']}/wp/v2/innovation-tip",
            auth=auth,
            params={'per_page': 1},
            timeout=10,
            verify=config.get('verify_tls', True)
        )
        taxonomy_response = requests.get(
            f"{config['url']}/wp/v2/{config['benefit_taxonomy_rest_base']}",
            auth=auth,
            params={'per_page': 100},
            timeout=10,
            verify=config.get('verify_tls', True)
        )
        schema_response = requests.options(
            f"{config['url']}/wp/v2/innovation-tip",
            auth=auth,
            timeout=10,
            verify=config.get('verify_tls', True)
        )
        taxonomy_payload = _response_json(taxonomy_response)
        schema_payload = _response_json(schema_response)
        returned_slugs = {
            term.get('slug')
            for term in taxonomy_payload or []
            if isinstance(term, dict)
        }
        schema_properties = (
            (schema_payload or {}).get('schema', {}).get('properties', {})
            if isinstance(schema_payload, dict)
            else {}
        )
        return all([
            post_response.status_code == 200,
            taxonomy_response.status_code == 200,
            schema_response.status_code == 200,
            set(BENEFIT_TERM_SLUGS.values()).issubset(returned_slugs),
            config['benefit_taxonomy_rest_base'] in schema_properties,
        ])
    except: return False
