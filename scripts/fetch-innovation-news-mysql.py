#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Innovation/Learning Technology News Fetcher (MySQL Version)
Updated: 2026-03-25 (Full Scrapers Restored & New Workflow Sequence)
Workflow: Fetch -> MySQL -> Telegram -> WordPress -> LINE (if WP success)
"""

import requests
import re
import json
import os
import html
import locale
import sys
import time
from datetime import datetime, timedelta, timezone
import hashlib
from typing import List, Dict, Optional, Tuple
import urllib.parse
import xml.etree.ElementTree as ET
import subprocess
import unicodedata
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import fcntl
except ImportError:  # Windows local development; PROD Linux provides fcntl.
    fcntl = None

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

# --- โหลด Environment Variables จาก .env ---
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == 'scripts' else SCRIPT_DIR
WORKSPACE_DIR = Path(os.getenv('INNOVATION_NEWS_WORKSPACE_DIR', str(DEFAULT_WORKSPACE_DIR))).expanduser()

def load_env_file(env_path: Path) -> bool:
    if not env_path.exists():
        return False

    with env_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                    continue
                value = value.strip().strip('"').strip("'").strip()
                if key != 'INNOVATION_NEWS_ENV_FILE' and key not in os.environ:
                    os.environ[key] = value
    return True

def load_env_from_candidates():
    explicit_env = os.getenv('INNOVATION_NEWS_ENV_FILE', '').strip()
    if explicit_env:
        explicit_path = Path(explicit_env).expanduser()
        if not load_env_file(explicit_path):
            raise FileNotFoundError(
                f'Explicit INNOVATION_NEWS_ENV_FILE does not exist: {explicit_path}'
            )
        return explicit_path

    seen = set()
    candidates = [
        WORKSPACE_DIR / '.env',
        SCRIPT_DIR / '.env',
    ]

    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if load_env_file(candidate):
            return candidate
    raise FileNotFoundError(
        'No Innovation News environment file found; expected workspace-root .env '
        'or temporary scripts/.env fallback'
    )

ENV_FILE = load_env_from_candidates()
WORKSPACE_DIR = Path(os.getenv('INNOVATION_NEWS_WORKSPACE_DIR', str(DEFAULT_WORKSPACE_DIR))).expanduser()

def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise ValueError(
        f'Invalid boolean for {name}; expected 1/0, true/false, yes/no, or on/off'
    )

ENABLE_TELEGRAM = env_flag('ENABLE_TELEGRAM', True)
ENABLE_WORDPRESS = env_flag('ENABLE_WORDPRESS', True)
ENABLE_LINE = env_flag('ENABLE_LINE', True)
ENABLE_EMAIL_WORKER = env_flag('ENABLE_EMAIL_WORKER', False)

# Add scripts directory to Python path for imports
import sys
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Import Integration Modules
try:
    from wordpress_integration import (
        is_wordpress_configured,
        save_to_wordpress,
        save_to_wordpress_result,
    )
    WORDPRESS_CONFIGURED = is_wordpress_configured()
    WORDPRESS_ENABLED = ENABLE_WORDPRESS and WORDPRESS_CONFIGURED
except ImportError:
    WORDPRESS_CONFIGURED = False
    WORDPRESS_ENABLED = False

try:
    from line_integration import is_line_configured, send_to_line
    LINE_CONFIGURED = is_line_configured()
    LINE_ENABLED = ENABLE_LINE and LINE_CONFIGURED
except ImportError:
    LINE_CONFIGURED = False
    LINE_ENABLED = False

# ตั้งค่า stdout/stderr เป็น UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Set Locale
try:
    locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

# ============================================================
# Configuration
# ============================================================

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
OPENCLAW_BIN = os.getenv('OPENCLAW_BIN', 'openclaw').strip()
DRY_RUN = env_flag('DRY_RUN', False)

DB_HOST = os.getenv('DB_HOST', 'localhost').strip()
DB_USER = os.getenv('DB_USER', '').strip()
DB_PASS = os.getenv('DB_PASS', '').strip()
DB_NAME = os.getenv('DB_NAME', 'innovation_news').strip()
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv('DB_CONNECT_TIMEOUT_SECONDS', '10'))

_fetch_lock_name = os.getenv(
    'INNOVATION_NEWS_FETCH_LOCK_NAME',
    f'innovation-news:{DB_NAME}:fetch',
).strip()
FETCH_LOCK_NAME = (_fetch_lock_name or 'innovation-news:fetch')[:64]
try:
    FETCH_LOCK_TIMEOUT_SECONDS = max(
        0,
        int(os.getenv('INNOVATION_NEWS_FETCH_LOCK_TIMEOUT_SECONDS', '0')),
    )
except ValueError:
    FETCH_LOCK_TIMEOUT_SECONDS = 0
EXIT_OK = 0
EXIT_UNEXPECTED_ERROR = 1
EXIT_FETCH_LOCK_ERROR = 70
EXIT_FETCH_ALREADY_RUNNING = 75

LOG_DIR = Path(os.getenv('INNOVATION_NEWS_LOG_DIR', str(WORKSPACE_DIR / 'logs'))).expanduser()
CACHE_DIR = Path(os.getenv('INNOVATION_NEWS_CACHE_DIR', str(WORKSPACE_DIR / 'cache'))).expanduser()
FETCH_FILE_LOCK_PATH = Path(
    os.getenv(
        'INNOVATION_NEWS_FETCH_FILE_LOCK',
        str(CACHE_DIR / 'innovation-news-fetch.lock'),
    )
).expanduser()
LOG_FILE = str(LOG_DIR / 'innovation-news-fetch.log')
SOURCES_INDEX_FILE = os.getenv(
    'INNOVATION_NEWS_SOURCES_INDEX_FILE',
    str(CACHE_DIR / 'innovation-sources-index.txt')
).strip()

INNOVATION_KEYWORDS = [
    'ai', 'artificial intelligence', 'machine learning', 'automation', 'chatbot',
    'innovation', 'startup', 'edtech', 'digital transformation', 'cybersecurity', 'future skills',
    'blockchain', 'cloud', 'big data', 'iot', 'robotics', 'analytics',
    'digital economy', 'smart city', 'quantum computing', 'metaverse', 'generative ai',
    'agentic ai', 'copilot', 'llm', 'deep learning', 'neural network',
    'remote work', 'hybrid work', 'digital workplace', 'collaboration', 'productivity',
    'green tech', 'sustainable', 'carbon neutral', 'circular economy', 'esg',
    'fintech', 'insurtech', 'healthtech', 'edutech', 'agritech', 'retailtech',
    'digital twin', 'predictive analytics', 'realtime', 'api', 'microservices',
    'startup ecosystem', 'entrepreneur', 'venture capital', 'accelerator', 'incubator'
]
INNOVATION_KEYWORDS_TH = [
    'ปัญญาประดิษฐ์', 'นวัตกรรม', 'สตาร์ทอัพ', 'ดิจิทัล', 'เอ็ดเทค', 'อีเลิร์นิง', 'ทักษะดิจิทัล',
    'บล็อกเชน', 'คลาวด์', 'บิ๊กดาต้า', 'ไอโอที', 'หุ่นยนต์', 'การวิเคราะห์',
    'เศรษฐกิจดิจิทัล', 'เมืองอัจฉริยะ', 'ควอนตัม', 'เมตาเวิร์ส', 'เจเนอเรทีฟเอไอ',
    'เอเจนติกเอไอ', 'โคไพล็อต', 'แอลแอลเอ็ม', 'ดีปเลิร์นิง', 'เครือข่ายเนอรัล',
    'การทำงานระยะไกล', 'การทำงานแบบไฮไบริด', 'เวิร์กแพลสดิจิทัล', 'ความร่วมมือ', 'ประสิทธิภาพ',
    'เทคโนโลยีสีเขียว', 'ยั่งยืน', 'คาร์บอนเนิวทรัล', 'เศรษฐกิจหมุนเวียน', 'อีเอสจี',
    'ฟินเทค', 'อินชัวร์เทค', 'เฮลท์เทค', 'เอ็ดยูเทค', 'แอกริเทค', 'เรตเทค',
    'ดิจิทัลทวิน', 'การวิเคราะห์ทำนายการ', 'เรียลไทม์', 'เอพีไอ', 'ไมโครเซอร์วิส',
    'ระบบนิเวิเคชัวร์', 'ผู้ประกอบการ', 'เวนเจอร์แคปปิทอล', 'แอกเซเลอเรเตอร์', 'อินคูเบเตอร์'
]

THAI_MONTHS = {1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน', 5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม', 9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'}

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

BENEFITS_PER_ARTICLE = 3
DEFAULT_BENEFITS = [
    "การสร้างนวัตกรรมและการเปลี่ยนแปลง",
    "การวิจัยและพัฒนาองค์ความรู้",
    "การปรับตัวต่อเทรนด์และตลาด",
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def sql_quote(value) -> str:
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"

def normalized_title(title: str) -> str:
    return clean_text(title or '')

def normalized_link(link: str) -> str:
    return (link or '').strip()

def generate_content_hash(article: Dict) -> str:
    hash_input = f"{normalized_title(article.get('title', ''))}|{normalized_link(article.get('link', ''))}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

def generate_legacy_title_hash(title: str) -> str:
    return hashlib.md5(normalized_title(title).encode('utf-8')).hexdigest()

def build_duplicate_conditions(article: Dict, content_hash: Optional[str] = None) -> List[str]:
    title = normalized_title(article.get('title', ''))
    link = normalized_link(article.get('link', ''))
    hashes = [
        hash_value for hash_value in {
            content_hash or generate_content_hash(article),
            generate_legacy_title_hash(title),
        } if hash_value
    ]

    conditions = []
    if hashes:
        conditions.append(f"content_hash IN ({', '.join(sql_quote(hash_value) for hash_value in hashes)})")
    if title and link:
        conditions.append(f"(title = {sql_quote(title)} AND link = {sql_quote(link)})")
    return conditions

SENSITIVE_SOURCE_QUERY_PARAMETER = re.compile(
    r'^(?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)$',
    re.IGNORECASE,
)
URL_IN_TEXT_PATTERN = re.compile(r'https?://[^\s\"\'<>]+', re.IGNORECASE)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r'(?i)\b(api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)'
    r'=([^&\s;,]+)'
)


def source_url_has_credentials(raw_url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit((raw_url or '').strip())
    except ValueError:
        return True
    return bool(
        parsed.username
        or parsed.password
        or any(
            SENSITIVE_SOURCE_QUERY_PARAMETER.fullmatch(key or '')
            for key, _value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        )
    )


def source_url_is_allowed(raw_url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit((raw_url or '').strip())
    except ValueError:
        return False
    return bool(
        parsed.scheme.lower() == 'https'
        and parsed.hostname
        and not source_url_has_credentials(raw_url)
    )


def redact_url_credentials(raw_url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit((raw_url or '').strip())
        hostname = parsed.hostname or ''
        if ':' in hostname and not hostname.startswith('['):
            hostname = f'[{hostname}]'
        try:
            port = f':{parsed.port}' if parsed.port else ''
        except ValueError:
            port = ''
        safe_query = urllib.parse.urlencode([
            (
                key,
                '[REDACTED]' if SENSITIVE_SOURCE_QUERY_PARAMETER.fullmatch(key or '') else value,
            )
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        ], doseq=True)
        return urllib.parse.urlunsplit(
            (parsed.scheme, f'{hostname}{port}', parsed.path, safe_query, parsed.fragment)
        )
    except Exception:
        return '[INVALID_URL]'


def sanitize_error_text(message: str) -> str:
    sanitized = URL_IN_TEXT_PATTERN.sub(
        lambda match: redact_url_credentials(match.group(0)),
        str(message or ''),
    )
    sanitized = SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f'{match.group(1)}=[REDACTED]',
        sanitized,
    )
    sanitized = re.sub(
        r'(?i)\b(authorization\s*:\s*(?:bearer|basic)\s+)\S+',
        r'\1[REDACTED]',
        sanitized,
    )
    return re.sub(
        r'(?i)([\"\'](?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|auth)'
        r'[\"\']\s*:\s*[\"\'])[^\"\']*',
        r'\1[REDACTED]',
        sanitized,
    )


def truncate_error_message(message: Optional[str], max_length: int = 1000) -> Optional[str]:
    if not message:
        return None

    compact_message = re.sub(r'\s+', ' ', sanitize_error_text(str(message))).strip()
    if not compact_message:
        return None

    if len(compact_message) <= max_length:
        return compact_message

    return compact_message[: max_length - 3].rstrip() + '...'

def combine_error_messages(messages: List[str]) -> Optional[str]:
    cleaned_messages = [truncate_error_message(message, max_length=250) for message in messages if message]
    joined_message = '; '.join(message for message in cleaned_messages if message)
    return truncate_error_message(joined_message)

# ============================================================
# Database Functions
# ============================================================

def get_source_url(slug: str) -> Optional[List[str]]:
    """ดึง URL จาก news_sources ตาม slug คืนเป็น list (รองรับหลาย URL)"""
    try:
        include_inactive = env_flag('INNOVATION_NEWS_ALLOW_INACTIVE_SOURCE_URLS', False)
        active_filter = '' if include_inactive else ' AND is_active = 1'
        out = run_mysql_query(
            f"SELECT source_url FROM news_sources WHERE slug = {sql_quote(slug)}{active_filter};"
        )
        if out:
            url_str = out.strip()
            # รองรับหลาย URL คั่นด้วย comma
            candidate_urls = [u.strip() for u in url_str.split(',') if u.strip()]
            urls = [url for url in candidate_urls if source_url_is_allowed(url)]
            if len(urls) != len(candidate_urls):
                log_message(
                    f"  Source URL rejected for {slug}: HTTPS is required and credentials must not be stored in URLs"
                )
            if urls:
                return urls
        return None
    except Exception as e:
        log_message(f"  ❌ Error fetching source URL for {slug}: {str(e)[:100]}")
        return None

def get_active_sources() -> List[Tuple[str, str, str]]:
    """ดึงรายชื่อแหล่งข้อมูลที่ active (is_active = 1) จาก DB"""
    try:
        out = run_mysql_query(
            "SELECT slug, name, fetch_method FROM news_sources WHERE is_active = 1 ORDER BY id;"
        )
        if out:
            sources = []
            for line in out.split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        slug, name, fetch_method = parts[0], parts[1], parts[2]
                        sources.append((slug, name, fetch_method))
            return sources
        return []
    except Exception as e:
        log_message(f"  ❌ Error fetching active sources: {str(e)[:100]}")
        return []

def split_sql_statements(sql: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0

    while index < len(sql):
        char = sql[index]

        if char == "'" and not in_double_quote:
            current.append(char)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                current.append(sql[index + 1])
                index += 1
            else:
                in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            current.append(char)
            if in_double_quote and index + 1 < len(sql) and sql[index + 1] == '"':
                current.append(sql[index + 1])
                index += 1
            else:
                in_double_quote = not in_double_quote
        elif char == ';' and not in_single_quote and not in_double_quote:
            statement = ''.join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)

        index += 1

    trailing_statement = ''.join(current).strip()
    if trailing_statement:
        statements.append(trailing_statement)

    return statements

def format_mysql_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)

def get_db_connection():
    if mysql is None:
        raise RuntimeError(
            "mysql-connector-python is not installed. Install it with 'python -m pip install mysql-connector-python'."
        )

    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS if DB_PASS else None,
        database=DB_NAME,
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci',
        use_unicode=True,
        autocommit=True,
        connection_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )


class GlobalFetchLockError(RuntimeError):
    """Raised when the process cannot reliably establish the global run lock."""


@contextmanager
def global_fetch_lock():
    """Hold a MySQL advisory lock for the complete fetch/publish cycle.

    A dedicated connection is required because MySQL named locks belong to the
    session that acquired them. The function fails closed: callers must not run
    the fetch cycle when lock state cannot be determined.
    """
    connection = None
    cursor = None
    acquired = False
    release_error = None
    file_lock_handle = None
    file_lock_acquired = False
    file_lock_busy = False

    try:
        try:
            if fcntl is not None:
                FETCH_FILE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
                file_lock_handle = FETCH_FILE_LOCK_PATH.open('a+', encoding='utf-8')
                try:
                    os.chmod(FETCH_FILE_LOCK_PATH, 0o600)
                    fcntl.flock(
                        file_lock_handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                    file_lock_acquired = True
                except BlockingIOError:
                    file_lock_busy = True

            if file_lock_busy:
                yield False
                return

            if not DB_USER or not DB_NAME:
                raise GlobalFetchLockError('Missing DB configuration: DB_USER/DB_NAME')

            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                'SELECT GET_LOCK(%s, %s)',
                (FETCH_LOCK_NAME, FETCH_LOCK_TIMEOUT_SECONDS),
            )
            row = cursor.fetchone()
            lock_result = row[0] if row else None

            if lock_result is None:
                raise GlobalFetchLockError('MySQL GET_LOCK returned NULL')

            acquired = int(lock_result) == 1
        except GlobalFetchLockError:
            raise
        except Exception as exc:
            raise GlobalFetchLockError(str(exc)) from exc

        yield acquired
    finally:
        if acquired and cursor is not None:
            try:
                cursor.execute('SELECT RELEASE_LOCK(%s)', (FETCH_LOCK_NAME,))
                release_row = cursor.fetchone()
                if not release_row or release_row[0] != 1:
                    release_error = 'MySQL RELEASE_LOCK was not confirmed'
            except Exception as exc:
                release_error = f'MySQL RELEASE_LOCK failed: {str(exc)[:200]}'

        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

        if file_lock_handle is not None:
            try:
                if file_lock_acquired:
                    fcntl.flock(file_lock_handle.fileno(), fcntl.LOCK_UN)
                file_lock_handle.close()
            except Exception as exc:
                local_release_error = f'local file lock release failed: {str(exc)[:200]}'
                release_error = release_error or local_release_error

        if release_error:
            log_message(f'  Global fetch lock integrity failure: {release_error}')
            raise GlobalFetchLockError(release_error)

def run_mysql_query(query: str) -> Optional[str]:
    connection = None
    cursor = None

    try:
        if not DB_USER or not DB_NAME:
            log_message("  ❌ Missing DB configuration: DB_USER/DB_NAME")
            return None

        statements = split_sql_statements(query)
        if not statements:
            return None

        connection = get_db_connection()
        cursor = connection.cursor()
        output_lines: List[str] = []

        cursor.execute("SET NAMES utf8mb4")
        for statement in statements:
            cursor.execute(statement)
            if cursor.with_rows:
                for row in cursor.fetchall():
                    output_lines.append('\t'.join(format_mysql_value(value) for value in row))

        return '\n'.join(output_lines) if output_lines else None
    except (MySQLError, RuntimeError) as e:
        if connection and getattr(connection, 'in_transaction', False):
            connection.rollback()
        log_message(f"  ❌ MySQL query error: {str(e)[:200]}")
        return None
    except Exception as e:
        if connection and getattr(connection, 'in_transaction', False):
            connection.rollback()
        log_message(f"  ❌ Unexpected DB error: {str(e)[:200]}")
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

def save_article_to_db(article: Dict, source_slug: str, source_name: str, content_hash: str) -> Optional[int]:
    try:
        # Check duplicate ก่อน save
        if is_article_duplicate(article, content_hash):
            return None

        # Handle empty summary - use title as fallback
        summary = article.get('summary', '').strip()
        if not summary:
            summary = article.get('title', '')[:500]
        if not summary:
            summary = 'No summary available'

        query = (
            "SET @aid=NULL; SET @isnew=NULL; "
            f"CALL save_article({sql_quote(source_slug)}, {sql_quote(article['title'])}, {sql_quote(summary[:800])}, "
            f"{sql_quote(article.get('link', ''))}, {sql_quote(article.get('date', ''))}, {sql_quote(content_hash)}, @aid, @isnew); "
            "SELECT @aid, @isnew;"
        )
        out = run_mysql_query(query)
        if out:
            res = out.strip().split('\n')[-1].split('\t')
            if len(res) >= 2:
                article_id = int(res[0])
                if article_id:
                    log_message(f"  💾 Saved new article to DB: {article['title'][:50]}")
                    return article_id
        return None
    except Exception as e:
        log_message(f"  ❌ DB save error: {str(e)[:150]}")
        return None

def update_article_delivery_statuses(
    article_id: int,
    telegram_status: str = 'skipped',
    wordpress_status: str = 'skipped',
    line_status: str = 'skipped',
    wordpress_url: Optional[str] = None,
) -> bool:
    try:
        normalized_telegram = telegram_status if telegram_status in {'sent', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled'} else 'skipped'
        normalized_wordpress = wordpress_status if wordpress_status in {'created', 'duplicate', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled'} else 'skipped'
        normalized_line = line_status if line_status in {'sent', 'failed', 'skipped', 'dry_run', 'blocked_by_wordpress', 'not_configured', 'disabled'} else 'skipped'
        date_sent_sql = "NOW()" if normalized_line == 'sent' else "date_sent"
        out = run_mysql_query(
            "UPDATE innovation_news SET "
            f"telegram_status = {sql_quote(normalized_telegram)}, "
            f"wordpress_status = {sql_quote(normalized_wordpress)}, "
            f"line_status = {sql_quote(normalized_line)}, "
            f"wordpress_url = {sql_quote(wordpress_url) if wordpress_url else 'wordpress_url'}, "
            f"date_sent = {date_sent_sql}, "
            "updated_at = NOW() "
            f"WHERE id = {int(article_id)} LIMIT 1; "
            "SELECT ROW_COUNT();"
        )
        return bool(out and out.strip().splitlines()[-1].strip() not in {'', '0'})
    except Exception as e:
        log_message(f"  โ ๏ธ Failed to update article delivery status: {str(e)[:120]}")
        return False

BENEFIT_TERM_SLUGS = {
    "ความสามารถในการแข่งขัน": "competitiveness",
    "การลดต้นทุนและเพิ่มประสิทธิภาพ": "cost-efficiency",
    "การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน": "digital-transformation",
    "การพัฒนาทักษะและการเรียนรู้": "skills-learning",
    "การใช้งาน AI และเทคโนโลยีขั้นสูง": "ai-advanced-technology",
    "ความปลอดภัยและความเป็นส่วนตัว": "security-privacy",
    "การสร้างนวัตกรรมและการเปลี่ยนแปลง": "innovation-change",
    "การปรับตัวต่อเทรนด์และตลาด": "trends-market-adaptation",
    "การจัดการข้อมูลและวิเคราะห์ข้อมูล": "data-management-analytics",
    "การสร้างประสบการณ์ลูกค้าและบริการ": "customer-experience-service",
    "การเชื่อมต่อและการทำงานร่วมกัน": "connectivity-collaboration",
    "การพัฒนาเทคโนโลยีและโครงสร้าง": "technology-infrastructure",
    "การสนับสนุนนวัตกรรมและสตาร์ทอัพ": "innovation-startup-support",
    "การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน": "blockchain-fintech",
    "การใช้เทคโนโลยีสีเขียวและยั่งยืน": "green-technology-sustainability",
    "การพัฒนาสุขภาพและการดูแลโรงพยาบาล": "healthcare-hospital-care",
    "การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์": "generative-ai",
    "การพัฒนาภาคศึกษาและเมืองอัจฉริยะ": "education-smart-city",
    "การทำธุรกิจในยุคดิจิทัล": "digital-business",
    "การวิจัยและพัฒนาองค์ความรู้": "research-knowledge-development",
}

def save_article_benefits_to_db(article_id: int, benefits: List[str]) -> bool:
    selected_slugs = [
        BENEFIT_TERM_SLUGS[benefit]
        for benefit in benefits
        if benefit in BENEFIT_TERM_SLUGS
    ]
    if len(selected_slugs) != BENEFITS_PER_ARTICLE:
        return False
    try:
        values = ', '.join(
            f"({int(article_id)}, {sql_quote(slug)})" for slug in selected_slugs
        )
        run_mysql_query(
            "START TRANSACTION; "
            f"DELETE FROM article_benefits WHERE article_id = {int(article_id)}; "
            f"INSERT INTO article_benefits (article_id, benefit_slug) VALUES {values}; "
            "COMMIT;"
        )
        return True
    except Exception as e:
        log_message(f"  Failed to save article benefits: {str(e)[:120]}")
        return False

def is_article_duplicate(article: Dict, content_hash: Optional[str] = None) -> bool:
    title = normalized_title(article.get('title', ''))
    link = normalized_link(article.get('link', ''))
    hashes = {
        content_hash or generate_content_hash(article),
        generate_legacy_title_hash(title)
    }

    conditions = [f"content_hash IN ({', '.join(sql_quote(h) for h in hashes if h)})"]
    if title and link:
        conditions.append(f"(title = {sql_quote(title)} AND link = {sql_quote(link)})")

    out = run_mysql_query(f"SELECT COUNT(*) FROM innovation_news WHERE {' OR '.join(conditions)};")
    return int(out) > 0 if out else False

def log_fetch_operation_to_db(
    source_slug,
    status,
    found,
    sent,
    new,
    err,
    duration,
    mysql_status='skipped',
    telegram_status='skipped',
    wordpress_status='skipped',
    line_status='skipped',
):
    try:
        run_mysql_query(
            f"CALL log_fetch_operation({sql_quote(source_slug)},{sql_quote(status)},{found},{sent},{new},{sql_quote(err)},{duration});"
        )
    except Exception as e:
        log_message(f"  ⚠️ Failed to log fetch operation: {str(e)[:100]}")

# ============================================================
# Helper Functions
# ============================================================

def log_message(message: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {message}")

def clean_text(text: str) -> str:
    if not text: return ''
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    return html.unescape(text).strip()

def is_innovation_article(title: str, summary: str = "") -> bool:
    t = (title + " " + summary).lower()
    return any(kw.lower() in t for kw in INNOVATION_KEYWORDS_TH + INNOVATION_KEYWORDS)

THAI_MONTH_NAME_LOOKUP = {
    'มกราคม': 1,
    'ม.ค.': 1,
    'มค': 1,
    'กุมภาพันธ์': 2,
    'ก.พ.': 2,
    'กพ': 2,
    'มีนาคม': 3,
    'มี.ค.': 3,
    'มีค': 3,
    'เมษายน': 4,
    'เม.ย.': 4,
    'เมย': 4,
    'พฤษภาคม': 5,
    'พ.ค.': 5,
    'พค': 5,
    'มิถุนายน': 6,
    'มิ.ย.': 6,
    'มิย': 6,
    'กรกฎาคม': 7,
    'ก.ค.': 7,
    'กค': 7,
    'สิงหาคม': 8,
    'ส.ค.': 8,
    'สค': 8,
    'กันยายน': 9,
    'ก.ย.': 9,
    'กย': 9,
    'ตุลาคม': 10,
    'ต.ค.': 10,
    'ตค': 10,
    'พฤศจิกายน': 11,
    'พ.ย.': 11,
    'พย': 11,
    'ธันวาคม': 12,
    'ธ.ค.': 12,
    'ธค': 12,
}

ARTICLE_DATE_CACHE: Dict[str, str] = {}
ENGLISH_MONTH_NAME_LOOKUP = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

def parse_thai_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None

    cleaned = re.sub(r'\s+', ' ', date_str.strip())
    cleaned = cleaned.replace('วันที่', '').replace('เผยแพร่เมื่อ', '').replace('เผยแพร่', '').strip()
    cleaned = re.sub(r'\s+\d{1,2}:\d{2}$', '', cleaned)

    match = re.search(r'(\d{1,2})(?:\s*[-/]\s*\d{1,2})?\s+([ก-๙\.]+)\s+(\d{4})', cleaned)
    if not match:
        return None

    day = int(match.group(1))
    month_token = match.group(2).strip()
    year = int(match.group(3))
    month = THAI_MONTH_NAME_LOOKUP.get(month_token)
    if not month:
        return None

    if year >= 2400:
        year -= 543

    try:
        return datetime(year, month, day)
    except ValueError:
        return None

def parse_relative_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None

    cleaned = re.sub(r'\s+', ' ', date_str.strip().lower())
    now = datetime.now()

    if cleaned in {'วันนี้', 'today'}:
        return now
    if cleaned in {'เมื่อวานนี้', 'yesterday'}:
        return now - timedelta(days=1)

    patterns = [
        (r'(\d+)\s*(นาที|นาทีก่อน|minute|minutes)\s*ที่แล้ว?', 'minutes'),
        (r'(\d+)\s*(ชั่วโมง|ชั่วโมงก่อน|hour|hours)\s*ที่แล้ว?', 'hours'),
        (r'(\d+)\s*(วัน|day|days)\s*ที่แล้ว?', 'days'),
        (r'(\d+)\s*(สัปดาห์|week|weeks)\s*ที่แล้ว?', 'weeks'),
        (r'(\d+)\s*(เดือน|month|months)\s*ที่แล้ว?', 'months'),
        (r'(\d+)\s*(ปี|year|years)\s*ที่แล้ว?', 'years'),
        (r'(\d+)\s*(minutes?|hours?|days?|weeks?|months?|years?)\s+ago', None),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue

        amount = int(match.group(1))
        normalized_unit = unit
        if normalized_unit is None:
            normalized_unit = match.group(2).lower()

        if normalized_unit.startswith('minute') or normalized_unit.startswith('นาที'):
            return now - timedelta(minutes=amount)
        if normalized_unit.startswith('hour') or normalized_unit.startswith('ชั่วโมง'):
            return now - timedelta(hours=amount)
        if normalized_unit.startswith('day') or normalized_unit == 'วัน':
            return now - timedelta(days=amount)
        if normalized_unit.startswith('week') or normalized_unit.startswith('สัปดาห์'):
            return now - timedelta(weeks=amount)
        if normalized_unit.startswith('month') or normalized_unit == 'เดือน':
            return now - timedelta(days=amount * 30)
        if normalized_unit.startswith('year') or normalized_unit == 'ปี':
            return now - timedelta(days=amount * 365)

    return None

def parse_english_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None

    cleaned = re.sub(r'\s+', ' ', date_str.strip())

    match = re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})', cleaned)
    if match:
        month = ENGLISH_MONTH_NAME_LOOKUP.get(match.group(1).lower())
        if month:
            return datetime(int(match.group(3)), month, int(match.group(2)))

    match = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', cleaned)
    if match:
        month = ENGLISH_MONTH_NAME_LOOKUP.get(match.group(2).lower())
        if month:
            return datetime(int(match.group(3)), month, int(match.group(1)))

    return None

def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None

    s = re.sub(r'\s+', ' ', date_str.strip()).replace(' GMT', ' +0000')

    for parser in (
        lambda value: datetime.fromisoformat(value.replace('Z', '+00:00')),
        parsedate_to_datetime,
        lambda value: datetime.strptime(value, '%Y-%m-%d %H:%M:%S'),
        lambda value: datetime.strptime(value, '%Y-%m-%d'),
        parse_english_date,
        parse_thai_date,
        parse_relative_date,
    ):
        try:
            parsed = parser(s)
            if parsed:
                return parsed
        except (ValueError, TypeError):
            continue

    return None

def is_within_last_1_year(date_obj: Optional[datetime]) -> bool:
    if not date_obj:
        return False
    return date_obj.replace(tzinfo=None) >= (datetime.now() - timedelta(days=365))

def format_thai_date(date_obj: Optional[datetime]) -> str:
    if not date_obj: return "ไม่ระบุวันที่"
    
    # Add timezone support - use Asia/Bangkok timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=ZoneInfo('Asia/Bangkok'))
    elif date_obj.tzinfo != ZoneInfo('Asia/Bangkok'):
        date_obj = date_obj.astimezone(ZoneInfo('Asia/Bangkok'))
    
    return f"{date_obj.day} {THAI_MONTHS.get(date_obj.month, '')} {date_obj.year + 543}"

def extract_published_date_from_article(link: str) -> str:
    cached = ARTICLE_DATE_CACHE.get(link)
    if cached is not None:
        return cached

    published_date = ""

    try:
        response = requests.get(link, timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        meta_selectors = [
            ('meta', {'property': 'article:published_time'}, 'content'),
            ('meta', {'name': 'article:published_time'}, 'content'),
            ('meta', {'property': 'og:published_time'}, 'content'),
            ('meta', {'name': 'date'}, 'content'),
            ('meta', {'itemprop': 'datePublished'}, 'content'),
        ]
        for tag_name, attrs, value_key in meta_selectors:
            tag = soup.find(tag_name, attrs=attrs)
            if tag and tag.get(value_key):
                published_date = tag.get(value_key).strip()
                break

        if not published_date:
            time_tag = soup.find('time')
            if time_tag:
                published_date = (
                    time_tag.get('datetime', '').strip()
                    or time_tag.get_text(' ', strip=True)
                )

        if not published_date:
            for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
                raw_json = script.get_text(strip=True)
                if not raw_json:
                    continue

                try:
                    payload = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue

                queue = payload if isinstance(payload, list) else [payload]
                while queue:
                    item = queue.pop(0)
                    if isinstance(item, dict):
                        if item.get('datePublished'):
                            published_date = str(item.get('datePublished')).strip()
                            break
                        queue.extend(item.values())
                    elif isinstance(item, list):
                        queue.extend(item)

                if published_date:
                    break
    except Exception as e:
        log_message(f"  โ ๏ธ Failed to extract article date from {link}: {str(e)[:80]}")

    ARTICLE_DATE_CACHE[link] = published_date
    return published_date

def generate_benefits(title: str, summary: str) -> List[str]:
    title_text = unicodedata.normalize('NFKC', str(title or '')).lower()
    summary_text = unicodedata.normalize('NFKC', str(summary or '')).lower()
    # kw_map = {
    #     "ความสามารถในการแข่งขัน": ["competitiv", "แข่งขัน", "ระดับโลก", "global"],
    #     "การลดต้นทุนและเพิ่มประสิทธิภาพ": ["cost", "saving", "ประสิทธิภาพ", "budget", "value"],
    #     "การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน": ["digital transformation", "ดิจิทัล", "digitize"],
    #     "การพัฒนาทักษะและการเรียนรู้": ["skill", "training", "learn", "ทักษะ", "edtech", "edutech", "หลักสูต"],
    #     "การใช้งาน AI และเทคโนโลยีขั้นสูง": ["ai", "artificial intelligence", "ปัญญาประดิษฐ์", "machine learning", "deep learning", "neural", "llm", "generative ai", "agentic ai"],
    #     "ความปลอดภัยและความเป็นส่วนตัว": ["secur", "privacy", "cyber", "security", "protection", "trust"],
    #     "การสร้างนวัตกรรมและการเปลี่ยนแปลง": ["innovat", "innovation", "disrupt", "นวัตกรรม"],
    #     "การปรับตัวต่อเทรนด์และตลาด": ["trend", "market", "future", "emerging", "ทิศทาง"],
    #     "การจัดการข้อมูลและวิเคราะห์ข้อมูล": ["data", "analytics", "big data", "predictive", "วิเคราะห์", "insight"],
    #     "การสร้างประสบการณ์ลูกค้าและบริการ": ["customer", "service", "ลูกค้า", "ประสบการณ์", "customer experience"],
    #     "การเชื่อมต่อและการทำงานร่วมกัน": ["collaborat", "connect", "ร่วมมือ", "partner", "ความร่วมมือ"],
    #     "การพัฒนาเทคโนโลยีและโครงสร้าง": ["tech", "technology", "infrastructure", "cloud", "iot", "smart", "automation", "robotics", "remote work", "hybrid work", "digital workplace", "collaboration", "productivity", "การทำงานระยะไกล", "เวิร์กแพลส"],
    #     "การสนับสนุนนวัตกรรมและสตาร์ทอัพ": ["startup", "entrepreneur", "venture", "incubator", "accelerator", "สตาร์ทอัพ", "นวัตกรรมไทย", "ecosystem"],
    #     "การใช้เทคโนโลยีสีเขียวและยั่งยืน": ["green tech", "sustainable", "carbon", "circular", "esg", "เทคโนโลยีสีเขียว", "ยั่งยืน", "carbon neutral"],
    #     "การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน": ["blockchain", "fintech", "digital asset", "crypto", "defi", "บล็อกเชน", "ฟินเทค"],
    #     "การพัฒนาสุขภาพและการดูแลโรงพยาบาล": ["healthtech", "digital health", "telemedicine", "ai doctor", "wellness", "health", "เฮลท์เทค"],
    #     "การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์": ["agentic ai", "copilot", "agent", "ai assistant", "autonomous"],
    #     "การพัฒนาภาคศึกษาและเมืองอัจฉริยะ": ["smart city", "urban tech", "digital economy", "metaverse", "vr", "ar", "เมืองอัจฉริยะ"],
    #     "การทำธุรกิจในยุคดิจิทัล": ["ecommerce", "retailtech", "marketplace", "digital", "รีเทลเทค", "อีคอมเมิร์ซ"]
    # }

    kw_map = {
    "ความสามารถในการแข่งขัน": [
        "competitiveness", "competitive", "แข่งขัน", "ขีดความสามารถ", "ระดับโลก", "global competitiveness"
    ],

    "การลดต้นทุนและเพิ่มประสิทธิภาพ": [
        "cost reduction", "cost saving", "saving", "ลดต้นทุน", "ประสิทธิภาพ", "efficiency",
        "productivity", "lean", "optimization", "budget", "value for money"
    ],

    "การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน": [
        "digital transformation", "digitalization", "digitization", "digitize",
        "ดิจิทัลทรานส์ฟอร์เมชัน", "เปลี่ยนผ่านดิจิทัล", "ดิจิทัล"
    ],

    "การพัฒนาทักษะและการเรียนรู้": [
        "skill", "reskill", "upskill", "training", "learning", "learn",
        "ทักษะ", "การเรียนรู้", "อบรม", "หลักสูตร", "edtech", "education technology"
    ],

    "การใช้งาน AI และเทคโนโลยีขั้นสูง": [
        "ai", "artificial intelligence", "ปัญญาประดิษฐ์", "machine learning",
        "deep learning", "neural network", "llm", "large language model",
        "generative ai", "foundation model"
    ],

    "ความปลอดภัยและความเป็นส่วนตัว": [
        "security", "cybersecurity", "cyber", "privacy", "data privacy",
        "protection", "trust", "zero trust", "ความปลอดภัย", "ความเป็นส่วนตัว", "คุ้มครองข้อมูล"
    ],

    "การสร้างนวัตกรรมและการเปลี่ยนแปลง": [
        "innovation", "innovative", "innovat", "disruption", "disruptive",
        "transformation", "change", "นวัตกรรม", "การเปลี่ยนแปลง"
    ],

    "การปรับตัวต่อเทรนด์และตลาด": [
        "trend", "market trend", "market", "future of", "future trend",
        "emerging", "consumer behavior", "ทิศทาง", "แนวโน้ม", "ตลาด"
    ],

    "การจัดการข้อมูลและวิเคราะห์ข้อมูล": [
        "data", "analytics", "data analytics", "big data", "predictive",
        "business intelligence", "insight", "dashboard", "วิเคราะห์ข้อมูล", "ข้อมูลเชิงลึก"
    ],

    "การสร้างประสบการณ์ลูกค้าและบริการ": [
        "customer", "customer experience", "cx", "service", "user experience",
        "ux", "ลูกค้า", "ประสบการณ์ลูกค้า", "การบริการ"
    ],

    "การเชื่อมต่อและการทำงานร่วมกัน": [
        "collaboration", "collaborate", "connect", "connected", "partnership",
        "partner", "ecosystem", "ร่วมมือ", "ความร่วมมือ", "เครือข่าย"
    ],

    "การพัฒนาเทคโนโลยีและโครงสร้าง": [
        "technology", "infrastructure", "cloud", "iot", "smart", "automation",
        "robotics", "remote work", "hybrid work", "digital workplace",
        "workplace technology", "โครงสร้างพื้นฐาน", "ระบบอัตโนมัติ"
    ],

    "การสนับสนุนนวัตกรรมและสตาร์ทอัพ": [
        "startup", "start-up", "entrepreneur", "venture", "incubator",
        "accelerator", "ecosystem", "สตาร์ทอัพ", "ผู้ประกอบการ", "ระบบนิเวศนวัตกรรม"
    ],

    "การใช้เทคโนโลยีสีเขียวและยั่งยืน": [
        "green technology", "green tech", "sustainable", "sustainability",
        "carbon", "carbon neutral", "circular economy", "esg",
        "เทคโนโลยีสีเขียว", "ยั่งยืน", "เศรษฐกิจหมุนเวียน"
    ],

    "การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน": [
        "blockchain", "fintech", "digital asset", "crypto", "cryptocurrency",
        "defi", "web3", "บล็อกเชน", "ฟินเทค", "สินทรัพย์ดิจิทัล"
    ],

    "การพัฒนาสุขภาพและการดูแลโรงพยาบาล": [
        "healthtech", "digital health", "telemedicine", "wellness",
        "healthcare", "hospital", "medical ai", "เฮลท์เทค", "สุขภาพดิจิทัล", "การแพทย์ทางไกล"
    ],

    "การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์": [
        "generative ai", "copilot", "ai assistant", "agentic ai",
        "autonomous agent", "ai agent", "ผู้ช่วยอัจฉริยะ"
    ],

    "การพัฒนาภาคศึกษาและเมืองอัจฉริยะ": [
        "smart city", "urban tech", "digital economy", "metaverse",
        "virtual reality", "augmented reality", "vr", "ar",
        "เมืองอัจฉริยะ", "เศรษฐกิจดิจิทัล"
    ],

    "การทำธุรกิจในยุคดิจิทัล": [
        "ecommerce", "e-commerce", "retailtech", "marketplace",
        "digital business", "online business", "อีคอมเมิร์ซ", "ธุรกิจดิจิทัล", "รีเทลเทค"
    ],

    "การวิจัยและพัฒนาองค์ความรู้": [
        "research", "research and development", "r&d", "ศึกษา", "ศึกษาวิจัย",
        "งานวิจัย", "paper", "academic", "scholar", "journal", "publication",
        "ตีพิมพ์", "บทความวิชาการ", "peer review", "literature review",
        "methodology", "experimental", "experiment", "hypothesis",
        "องค์ความรู้", "ฐานความรู้", "knowledge creation", "knowledge base",
        "การวิจัยและพัฒนา", "การสร้างองค์ความรู้"
    ]
}
    
    def keyword_matches(text: str, keyword: str) -> bool:
        """Avoid false positives for short Latin tokens such as ai/ar/vr."""
        normalized_keyword = keyword.lower().strip()
        if (
            normalized_keyword.isascii()
            and len(normalized_keyword) <= 3
            and re.fullmatch(r'[a-z0-9+#.&-]+', normalized_keyword)
        ):
            return bool(re.search(
                rf'(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])',
                text,
            ))
        return normalized_keyword in text

    scored_benefits = []
    for order, (benefit, keywords) in enumerate(kw_map.items()):
        title_matches = [keyword for keyword in keywords if keyword_matches(title_text, keyword)]
        summary_matches = [
            keyword for keyword in keywords
            if keyword not in title_matches and keyword_matches(summary_text, keyword)
        ]
        if not title_matches and not summary_matches:
            continue

        # Title evidence has three times the weight of summary evidence.
        score = (
            (len(title_matches) * 300)
            + sum(len(keyword) for keyword in title_matches)
            + (len(summary_matches) * 100)
            + sum(len(keyword) for keyword in summary_matches)
        )
        scored_benefits.append((score, order, benefit))

    scored_benefits.sort(key=lambda item: (-item[0], item[1]))
    selected_benefits = [benefit for _, _, benefit in scored_benefits[:BENEFITS_PER_ARTICLE]]

    for fallback_benefit in DEFAULT_BENEFITS:
        if len(selected_benefits) >= BENEFITS_PER_ARTICLE:
            break
        if fallback_benefit not in selected_benefits:
            selected_benefits.append(fallback_benefit)

    return selected_benefits[:BENEFITS_PER_ARTICLE]

def format_message(article: Dict) -> str:
    thai_date = article.get('published_date_th')
    if not thai_date:
        date_obj = parse_date(article['date'])
        thai_date = format_thai_date(date_obj) if date_obj else article['date']
    benefits = article.get('benefits', [])

    # ใช้ summary ถ้ามี ถ้าไม่มีให้ใช้ title แทน
    summary_text = article.get('summary', '').strip()
    if not summary_text:
        summary_text = article['title']

    msg = f"📌 Innovation Daily Update\n\nหัวข้อ: {article['title']}\nเผยแพร่เมื่อ: {thai_date}\nแหล่งข้อมูล: {article['source']}\n\nรายละเอียดโดยสรุป:\n{summary_text[:800]}..."
    if benefits:
        msg += "\n\nประโยชน์ต่อองค์กร:"
        for b in benefits:
            msg += f"\n{BENEFIT_EMOJI_MAP.get(b, '✅')} {b}"
    msg += f"\n\nอ่านต่อ: {article['link']}"
    return msg

def format_no_new_articles_message(source_name: str) -> str:
    return f"""📌 Innovation Daily Update

แหล่งข้อมูล: {source_name}
สถานะ: รอบนี้ยังไม่พบบทความใหม่ที่เข้าเงื่อนไข

🔄 ระบบจะเริ่มรอบถัดไปตาม scheduler ที่กำหนดไว้
"""

def send_telegram_message(message: str, max_retries: int = 2) -> bool:
    if DRY_RUN:
        log_message("  DRY_RUN enabled: skipping Telegram send")
        return False

    if not ENABLE_TELEGRAM:
        log_message("  Telegram send is disabled by configuration")
        return False

    if not TELEGRAM_CHAT_ID:
        log_message("  ⚠️ Telegram target is not configured")
        return False

    for attempt in range(max_retries + 1):
        try:
            cmd = [OPENCLAW_BIN, 'message', 'send', '--channel', 'telegram', '--target', TELEGRAM_CHAT_ID, '--message', message]
            result = subprocess.run(cmd, capture_output=True, timeout=45, text=True)
            if result.returncode == 0:
                return True
            else:
                log_message(f"  ⚠️ Telegram attempt {attempt + 1} failed: {result.stderr[-200:]}")
        except subprocess.TimeoutExpired:
            log_message(f"  ⚠️ Telegram timeout (attempt {attempt + 1}/{max_retries + 1})")
            if attempt < max_retries:
                time.sleep(2)  # รอ 2 วินาทีก่อน retry
        except Exception as e:
            log_message(f"  ❌ Telegram error: {str(e)}")
            return False
    log_message(f"  ❌ Telegram failed after {max_retries + 1} attempts")
    return False

# ============================================================
def sync_wordpress_and_line(article: Dict, content_hash: str, issues: Optional[List[str]] = None) -> Dict[str, Optional[object]]:
    issues = issues if issues is not None else []
    wp_result = {
        'post_id': None,
        'created': False,
        'status': 'skipped',
        'line_status': 'skipped',
    }

    if DRY_RUN:
        log_message("  DRY_RUN enabled: skipping WordPress and LINE sync")
        wp_result['status'] = 'dry_run'
        wp_result['line_status'] = 'dry_run'
        return wp_result

    if WORDPRESS_ENABLED:
        log_message("  Syncing to WordPress...")
        wp_result = save_to_wordpress_result(article, content_hash)
        wp_result['line_status'] = 'skipped'
        wp_id = wp_result.get('post_id')
        wp_status = wp_result.get('status')

        if wp_result.get('created'):
            log_message(f"  Saved to WP (ID: {wp_id})")
        elif wp_status == 'duplicate':
            log_message(f"  Skipped LINE Notify because WordPress already has this article (ID: {wp_id})")
        elif wp_status == 'not_configured':
            log_message("  Skipped WordPress sync because configuration is incomplete")
        else:
            log_message("  WordPress sync failed")
            issues.append('WordPress sync failed')
    else:
        wp_result['status'] = 'disabled' if not ENABLE_WORDPRESS else 'not_configured'
        wp_result['line_status'] = (
            'disabled' if not ENABLE_LINE else 'not_configured'
        ) if not LINE_ENABLED else 'blocked_by_wordpress'
        if LINE_ENABLED:
            log_message("  Skipped LINE Notify because WordPress integration is disabled or not configured")
        return wp_result

    wordpress_url = str(wp_result.get('wordpress_url') or '').strip()
    if LINE_ENABLED and wp_result.get('created') and wordpress_url:
        log_message("  WordPress created a new post. Sending to LINE (OAR Notify)...")
        line_article = dict(article)
        line_article['wordpress_url'] = wordpress_url
        if send_to_line(line_article):
            log_message("  Sent to LINE successfully")
            wp_result['line_status'] = 'sent'
        else:
            log_message("  Failed to send to LINE")
            issues.append('LINE send failed')
            wp_result['line_status'] = 'failed'
    elif not LINE_ENABLED:
        wp_result['line_status'] = 'disabled' if not ENABLE_LINE else 'not_configured'
    else:
        wp_result['line_status'] = 'blocked_by_wordpress'
        if wp_result.get('status') == 'failed' or not wordpress_url:
            log_message("  Skipped LINE Notify because no canonical WordPress URL is available")

    return wp_result

# Fetchers (Restored Full List)
# ============================================================

def fetch_nia(source_name: str):
    urls = get_source_url('nia')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for NIA")
        return []

    try:
        res = requests.get(urls[0], timeout=30, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')

        articles = []
        items = soup.find_all('div', class_='list-column-item')

        for item in items[:15]:
            try:
                # Find the link
                a_tag = item.find('a')
                if not a_tag:
                    continue

                link = a_tag.get('href', '')
                if link and not link.startswith('http'):
                    link = f"https://www.nia.or.th{link}"

                # Find the title in <h2> tag
                h2_tag = item.find('h2')
                title = h2_tag.get_text(strip=True) if h2_tag else ''

                if not title:
                    continue

                # NIA sends all articles without filtering (all are relevant)
                # No need to check is_innovation_article()

                # Extract date from .list-column-tag (optional)
                date_tag = item.find('div', class_='list-column-tag')
                date = ''
                if date_tag:
                    # Get text nodes before the <i class="fas fa-eye"></i> tag
                    for child in date_tag.children:
                        if hasattr(child, 'strip'):  # It's a NavigableString (text node)
                            date = child.strip()
                            break
                        elif child.name == 'i':  # Stop at the eye icon
                            break

                articles.append({
                    'title': clean_text(title),
                    'link': link,
                    'date': date,
                    'summary': clean_text(title),
                    'source': 'NIA (สำนักงานนวัตกรรมแห่งชาติ)' if source_name is None else source_name
                })

            except Exception as e:
                log_message(f"  ⚠️ NIA item parse error: {str(e)[:80]}")
                continue

        return articles

    except Exception as e:
        log_message(f"  ❌ NIA fetch error: {str(e)[:100]}")
        return []

def fetch_etda(source_name: str):
    urls = get_source_url('etda')
    if not urls:
        log_message("  ❌ No URL configured for ETDA")
        return []

    try:
        all_articles = []
        for url in urls:
            try:
                root = ET.fromstring(requests.get(url, timeout=30, headers=headers).content)
                items = root.findall('.//item')
                # Get last 10 items (newest), then reverse to newest-first order
                articles = [{'title': clean_text(i.find('title').text), 'link': i.find('link').text, 'date': i.find('pubDate').text, 'summary': clean_text(i.find('description').text), 'source': 'ETDA (สพธอ.)' if source_name is None else source_name} for i in items[-10:]]
                articles.reverse()  # Reverse so newest comes first
                all_articles.extend(articles)
            except Exception as e:
                log_message(f"  ⚠️ ETDA sub-feed error: {str(e)[:80]}")
                continue

        # Remove duplicates by link, keep first occurrence (which is newest)
        seen_links = set()
        unique_articles = []
        for article in all_articles:
            if article['link'] not in seen_links:
                seen_links.add(article['link'])
                unique_articles.append(article)

        return unique_articles
    except Exception as e:
        log_message(f"  ❌ ETDA fetch error: {str(e)[:100]}")
        return []

def fetch_techsauce_rss(source_name: str):
    urls = get_source_url('techsauce')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for Techsauce")
        return []

    try:
        root = ET.fromstring(requests.get(urls[0], timeout=30, headers=headers).content)
        return [{'title': clean_text(i.find('title').text), 'link': i.find('link').text, 'date': i.find('pubDate').text, 'summary': clean_text(i.find('description').text), 'source': 'Techsauce' if source_name is None else source_name} for i in root.findall('.//item')[:10]]
    except Exception as e:
        log_message(f"  ❌ Techsauce fetch error: {str(e)[:100]}")
        return []

def fetch_nstda(source_name: str):
    urls = get_source_url('nstda')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for NSTDA")
        return []

    try:
        posts = requests.get(urls[0], timeout=30, headers=headers).json()
        return [{'title': clean_text(p['title']['rendered']), 'link': p['link'], 'date': p['date'], 'summary': clean_text(p.get('excerpt', {}).get('rendered', '')), 'source': 'NSTDA (สวทช.)' if source_name is None else source_name} for p in posts]
    except Exception as e:
        log_message(f"  ❌ NSTDA fetch error: {str(e)[:100]}")
        return []

def fetch_ryt9(source_name: str):
    urls = get_source_url('ryt9')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for RYT9")
        return []

    try:
        root = ET.fromstring(requests.get(urls[0], timeout=30, headers=headers).content)
        return [{'title': clean_text(i.find('title').text), 'link': i.find('link').text, 'date': i.find('pubDate').text, 'summary': clean_text(i.find('description').text), 'source': 'RYT9' if source_name is None else source_name} for i in root.findall('.//item')[:10]]
    except Exception as e:
        log_message(f"  ❌ RYT9 fetch error: {str(e)[:100]}")
        return []

def fetch_it24hrs_rss(source_name: str):
    urls = get_source_url('it24hrs')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for iT24Hrs")
        return []

    try:
        res = requests.get(urls[0], timeout=30, headers=headers).text
        matches = re.findall(r'<h[2-4][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', res, re.DOTALL)
        articles = []
        for link, title in matches[:10]:
            if not is_innovation_article(title):
                continue
            articles.append({
                'title': clean_text(title),
                'link': link,
                'date': extract_published_date_from_article(link),
                'summary': clean_text(title),
                'source': 'iT24Hrs' if source_name is None else source_name
            })
        return articles
    except Exception as e:
        log_message(f"  ❌ iT24Hrs fetch error: {str(e)[:100]}")
        return []

def fetch_techtalkthai_rss(source_name: str):
    urls = get_source_url('techtalkthai')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for TechTalkThai")
        return []

    try:
        root = ET.fromstring(requests.get(urls[0], timeout=30, headers=headers).content)
        return [{'title': clean_text(i.find('title').text), 'link': i.find('link').text, 'date': i.find('pubDate').text, 'summary': clean_text(i.find('description').text), 'source': 'TechTalkThai' if source_name is None else source_name} for i in root.findall('.//item')[:10]]
    except Exception as e:
        log_message(f"  ❌ TechTalkThai fetch error: {str(e)[:100]}")
        return []

def fetch_nectec(source_name: str):
    urls = get_source_url('nectec')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for NECTEC")
        return []

    try:
        res = requests.get(urls[0], timeout=30, headers=headers).text
        matches = re.findall(r'<h3[^>]*elementor-post__title[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', res, re.DOTALL)
        articles = []
        for link, title in matches[:10]:
            full_link = link if link.startswith('http') else f"https://www.nectec.or.th{link}"
            articles.append({
                'title': clean_text(title),
                'link': full_link,
                'date': extract_published_date_from_article(full_link),
                'summary': clean_text(title),
                'source': 'NECTEC (สวทช.)' if source_name is None else source_name
            })
        return articles
    except Exception as e:
        log_message(f"  ❌ NECTEC fetch error: {str(e)[:100]}")
        return []

def fetch_nriis(source_name: str):
    urls = get_source_url('nriis')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for NRIIS")
        return []

    try:
        root = ET.fromstring(requests.get(urls[0], timeout=30, headers=headers).content)
        items = root.findall('.//item')
        # NRIIS RSS is newest-first (2026 → 2025), so use [:10] for newest 10
        return [{
            'title': clean_text(i.find('title').text),
            'link': i.find('link').text,
            'date': (i.find('pubDate').text if i.find('pubDate') is not None else i.find('pubdate').text if i.find('pubdate') is not None else ""),
            'summary': clean_text(i.find('description').text if i.find('description').text else ""),
            'source': 'สำนักงานการวิจัยแห่งชาติ (วช.)' if source_name is None else source_name
        } for i in items[:10]]  # Get first 10 items (newest first)
    except Exception as e:
        log_message(f"  ❌ NRIIS fetch error: {str(e)[:100]}")
        return []

def fetch_innomatter_rss(source_name: str):
    urls = get_source_url('innomatter')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for Innomatter")
        return []

    try:
        root = ET.fromstring(requests.get(urls[0], timeout=30, headers=headers).content)
        return [{'title': clean_text(i.find('title').text), 'link': i.find('link').text, 'date': i.find('pubDate').text, 'summary': clean_text(i.find('description').text), 'source': 'Innomatter' if source_name is None else source_name} for i in root.findall('.//item')[:10]]
    except Exception as e:
        log_message(f"  ❌ Innomatter fetch error: {str(e)[:100]}")
        return []

def fetch_techmovement(source_name: str):
    """ดึงข่าวจาก TechMovement.co.th/news โดยใช้ Scrapling Dynamic Fetcher"""
    urls = get_source_url('techmovement')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for TechMovement")
        return []

    try:
        sys.path.insert(0, '/opt/scrapling-venv/lib/python3.12/site-packages')
        from scrapling.fetchers import DynamicFetcher

        # Fetch เว็บด้วย Dynamic mode (ดึงจากหน้า /news)
        page = DynamicFetcher.fetch(urls[0], headless=True, network_idle=True)

        # หา card ข่าวทั้งหมด
        cards = page.css('div.group[data-variant]')

        articles = []

        for card in cards:
            try:
                # ดึงลิงก์
                link = card.css('a[href^="/news/content/"]::attr(href)').get()
                if not link:
                    continue

                # ดึงหมวดหมู่
                category = card.css('span.bg-primary::text').get() or ""

                # ดึงหัวข้อ
                title = card.css('h3::text').get() or ""
                title = title.strip()

                # ดึงเวลา
                time = card.css('span.text-xs::text').getall()
                time_str = time[-1].strip() if time else ""

                # ดึง excerpt
                excerpt = card.css('p::text').get() or ""
                excerpt = excerpt.strip()

                # สร้างลิงก์เต็ม
                base_url = urls[0].rstrip('/')
                full_link = f'{base_url}{link}'

                # ตรวจสอบว่าเป็น innovation article หรือไม่
                if not is_innovation_article(title, excerpt):
                    continue

                articles.append({
                    'title': clean_text(title),
                    'link': full_link,
                    'date': time_str,  # TechMovement uses relative time like "1 ชั่วโมงที่แล้ว"
                    'summary': clean_text(excerpt),
                    'source': 'TechMovement'
                })

            except Exception as e:
                log_message(f"  ⚠️ TechMovement card parse error: {str(e)[:80]}")
                continue

        # ลบข่าวซ้ำโดยใช้ link เป็น reference
        seen_links = set()
        unique_articles = []
        for item in articles:
            if item['link'] not in seen_links:
                seen_links.add(item['link'])
                unique_articles.append(item)

        return unique_articles

    except Exception as e:
        log_message(f"  ❌ TechMovement fetch error: {str(e)[:100]}")
        return []

# ============================================================
# Main Logic
# ============================================================

# Map slug กับ fetcher function
FETCHER_MAP = {
    'nia': fetch_nia,
    'etda': fetch_etda,
    'techsauce': fetch_techsauce_rss,
    'nstda': fetch_nstda,
    'ryt9': fetch_ryt9,
    'it24hrs': fetch_it24hrs_rss,
    'techtalkthai': fetch_techtalkthai_rss,
    'nectec': fetch_nectec,
    'nriis': fetch_nriis,
    'innomatter': fetch_innomatter_rss,
    'techmovement': fetch_techmovement
}

# Reverse map สำหรับการแสดงผล
FETCHER_NAMES = {
    'nia': 'NIA',
    'etda': 'ETDA',
    'techsauce': 'Techsauce',
    'nstda': 'NSTDA',
    'ryt9': 'RYT9',
    'it24hrs': 'iT24Hrs',
    'techtalkthai': 'TechTalkThai',
    'nectec': 'NECTEC',
    'nriis': 'NRIIS',
    'innomatter': 'Innomatter',
    'techmovement': 'TechMovement'
}

def get_slug_by_name(name: str) -> Optional[str]:
    """หา slug จาก name โดยตรวจสอบทั้ง short name และ full name จาก DB"""
    # ตรวจสอบ short name ใน FETCHER_NAMES ก่อน (เร็วกว่า)
    for slug, fetcher_name in FETCHER_NAMES.items():
        if fetcher_name in name or name == fetcher_name:
            return slug

    # ถ้าหาไม่เจอ ลอง query จาก DB (รองรับ full Thai name)
    try:
        escaped_name = name.replace("'", "\\'")
        out = run_mysql_query(f"SELECT slug FROM news_sources WHERE name = '{escaped_name}' LIMIT 1;")
        if out:
            slug = out.strip()
            if slug:
                return slug
    except Exception as e:
        log_message(f"  ⚠️ Error fetching slug from DB for name '{name}': {str(e)[:80]}")

    # ถ้าหาไม่เจอ คืน None
    return None

def get_current_source_index() -> int:
    try:
        with open(SOURCES_INDEX_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def update_source_index(index: int, total_sources: int):
    os.makedirs(os.path.dirname(SOURCES_INDEX_FILE), exist_ok=True)
    with open(SOURCES_INDEX_FILE, 'w') as f: f.write(str((index + 1) % total_sources))

def get_sources_list() -> List[tuple]:
    """ดึงรายชื่อแหล่งที่ active พร้อม fetcher function"""
    try:
        active_sources = get_active_sources()
        sources_list = []

        for slug, name in active_sources:
            if slug in FETCHER_MAP:
                fetcher = FETCHER_MAP[slug]
                sources_list.append((name, fetcher))
            else:
                log_message(f"  ⚠️ Skipping active source without fetcher implementation: {slug}")

        return sources_list
    except Exception as e:
        log_message(f"  ❌ Error building sources list: {str(e)[:100]}")
        return []

def process_articles_for_source(source_name: str, source_slug: str, articles: List[Dict]) -> Dict:
    result = {
        'new_article': None,
        'sent_count': 0,
        'new_count': 0,
    }

    for article in articles:
        date_obj = parse_date(article.get('date', ''))
        if not is_within_last_1_year(date_obj):
            continue

        content_hash = generate_content_hash(article)
        if is_article_duplicate(article, content_hash):
            continue

        if source_slug not in ["nia", "nstda"] and not is_innovation_article(article.get('title', ''), article.get('summary', '')):
            continue

        log_message(f"  ✓ Selected new article from {source_name}: {article.get('title', '')[:50]}")
        article['source'] = source_name

        article_id = save_article_to_db(article, source_slug, source_name, content_hash)
        if not article_id:
            continue

        result['new_article'] = article
        result['new_count'] = 1

        article['benefits'] = generate_benefits(article.get('title', ''), article.get('summary', ''))

        log_message("  📣 Sending to Telegram...")
        telegram_sent = send_telegram_message(format_message(article))
        result['sent_count'] = 1 if telegram_sent else 0
        sync_wordpress_and_line(article, content_hash)

        wp_id = None
        if False and WORDPRESS_ENABLED:
            log_message("  🔄 Syncing to WordPress...")
            wp_id = save_to_wordpress(article, content_hash)
            if wp_id:
                log_message(f"  📰 Saved to WP (ID: {wp_id})")
            else:
                log_message("  ⚠️ WordPress sync failed")

        if False and LINE_ENABLED and wp_id:
            log_message("  🟢 WordPress Success. Sending to LINE (OAR Notify)...")
            if send_to_line(article):
                log_message("  ✅ Sent to LINE successfully")
            else:
                log_message("  ⚠️ Failed to send to LINE")
        elif False and LINE_ENABLED and not wp_id:
            log_message("  ⏭️ Skipped LINE Notify because WordPress sync failed")

        break

    return result

def log_source_fetch_result(source_slug: str, articles_found: int, sent_count: int, new_count: int, started_at: datetime):
    duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
    log_fetch_operation_to_db(source_slug, 'success', articles_found, sent_count, new_count, None, duration_ms)

def legacy_main():
    start_time = datetime.now()
    log_message("=== Starting innovation news fetch ===")

    # ดึงรายชื่อแหล่งที่ active จาก DB
    SOURCES = get_sources_list()
    total_sources = len(SOURCES)

    if total_sources == 0:
        log_message("❌ No active sources found in DB")
        return EXIT_OK

    # ป้องกัน IndexError จากการเพิ่ม/ลด SOURCES
    current_idx = get_current_source_index() % total_sources
    source_name, fetcher = SOURCES[current_idx]

    # ดึง slug จาก name โดยใช้ฟังก์ชันที่แก้แล้ว
    source_slug = get_slug_by_name(source_name)

    if not source_slug:
        log_message(f"  ❌ Cannot find slug for source: {source_name}")
        return

    log_message(f"🔄 Fetching from source {current_idx + 1}/{total_sources}: {source_name}")
    log_message(f"  📋 Active sources: {[s[0] for s in SOURCES]}")

    articles = fetcher(source_name)
    if len(articles) > 0:
        log_message(f"✅ {source_name}: Found {len(articles)} innovation articles")
    else:
        log_message(f"⚠️ {source_name}: No articles found")

    update_source_index(current_idx, total_sources)

    new_article = None
    sent_count = 0
    new_count = 0

    # ตัวแปรสำหรับเช็คว่าต้องลองแหล่งถัดไปหรือไม่
    check_next_source = False
    next_source_name = None
    next_source_slug = None

    for article in articles:
        date_obj = parse_date(article['date'])
        if not is_within_last_1_year(date_obj): continue
        content_hash = hashlib.md5(article['title'].encode('utf-8')).hexdigest()

        if is_article_duplicate(content_hash): continue

        # กรองเฉพาะ innovation/learning technology articles
        # (บาง source เช่น NIA, NSTDA ไม่ต้องกรองเพราะทุกข่าวเป็น innovation อยู่แล้ว)
        if source_slug not in ["nia", "nstda"] and not is_innovation_article(article['title'], article['summary']):
            continue

        log_message(f"  ✓ Selected new article: {article['title'][:50]}")

        # บันทึก source_name ลงใน article dict เพื่อใช้กับฐานข้อมูล
        article['source'] = source_name

        #1. บันทึกลง MySQL
        article_id = save_article_to_db(article, source_slug, source_name, content_hash)

        if article_id:
            new_article = article
            new_count = 1
            sent_count = 1

            # เตรียมข้อมูลประโยชน์
            article['benefits'] = generate_benefits(article['title'], article['summary'])

            # 2. ส่ง Telegram
            log_message("  📨 Sending to Telegram...")
            send_telegram_message(format_message(article))

            # 3. Sync to WordPress (เฉพาะมีข่าวใหม่)
            sync_wordpress_and_line(article, content_hash)
            wp_id = None
            if False and WORDPRESS_ENABLED:
                log_message("  🔄 Syncing to WordPress...")
                wp_id = save_to_wordpress(article, content_hash)
                if wp_id: log_message(f"  📄 Saved to WP (ID: {wp_id})")
                else: log_message("  ⚠️ WordPress sync failed")

            # 4. ส่งไป LINE เฉพาะเมื่อ WordPress บันทึกสำเร็จ (เฉพาะมีข่าวใหม่)
            if False and LINE_ENABLED and wp_id:
                log_message("  🟢 WordPress Success. Sending to LINE (OAR Notify)...")
                if send_to_line(article): log_message("  ✅ Sent to LINE successfully")
                else: log_message("  ⚠️ Failed to send to LINE")
            elif False and LINE_ENABLED and not wp_id:
                log_message("  ⏭️ Skipped LINE Notify because WordPress sync failed")

            break # พบข่าวใหม่แล้วส่งสำเร็จแล้ว หยุดการวนลูป

    # ถ้าไม่มีข่าวใหม่ → ส่ง Telegram แจ้งว่าไม่มีข่าว และตรวจสอบแหล่งถัดไป
    if not new_article:
        log_message(f"  ℹ️ No new articles found from {source_name}")
        send_telegram_message(format_no_new_articles_message(source_name))
        sent_count = 1  # ส่ง Telegram แจ้งว่าไม่มีข่าว

        # ตรวจสอบแหล่งถัดไปทันที
        check_next_source = True
        next_idx = (current_idx + 1) % total_sources
        next_source_name, next_fetcher = SOURCES[next_idx]

        # ดึง slug จาก name โดยใช้ฟังก์ชันที่แก้แล้ว
        next_source_slug = get_slug_by_name(next_source_name)

        if not next_source_slug:
            log_message(f"  ❌ Cannot find slug for next source: {next_source_name}")
            return

        log_message(f"  🔍 Checking next source: {next_source_name} ({next_idx + 1}/{total_sources})")
        next_articles = next_fetcher(next_source_name)

        if len(next_articles) > 0:
            log_message(f"  ✅ {next_source_name}: Found {len(next_articles)} innovation articles")
        else:
            log_message(f"  ⚠️ {next_source_name}: No articles found")

        # Update index ไปอันถัดไป (เตรียมสำหรับรันครั้งต่อไป)
        update_source_index(next_idx, total_sources)

        # Loop หาข่าวใหม่จากแหล่งถัดไป
        for article in next_articles:
            date_obj = parse_date(article['date'])
            if not is_within_last_1_year(date_obj): continue
            content_hash = hashlib.md5(article['title'].encode('utf-8')).hexdigest()

            if is_article_duplicate(content_hash): continue

            # กรองเฉพาะ innovation/learning technology articles
            if next_source_slug not in ["nia", "nstda"] and not is_innovation_article(article['title'], article['summary']):
                continue

            log_message(f"  ✓ Found new article from next source: {article['title'][:50]}")

            # บันทึก source_name ลงใน article dict
            article['source'] = next_source_name

            # บันทึกและส่งข่าวจากแหล่งถัดไป
            article_id = save_article_to_db(article, next_source_slug, next_source_name, content_hash)

            if article_id:
                new_article = article
                new_count = 1
                sent_count = 1

                # เตรียมข้อมูลประโยชน์
                article['benefits'] = generate_benefits(article['title'], article['summary'])

                # ส่ง Telegram
                log_message("  📨 Sending to Telegram...")
                send_telegram_message(format_message(article))

                # Sync to WordPress
                sync_wordpress_and_line(article, content_hash)
                wp_id = None
                if False and WORDPRESS_ENABLED:
                    log_message("  🔄 Syncing to WordPress...")
                    wp_id = save_to_wordpress(article, content_hash)
                    if wp_id: log_message(f"  📄 Saved to WP (ID: {wp_id})")
                    else: log_message("  ⚠️ WordPress sync failed")

                # ส่งไป LINE
                if False and LINE_ENABLED and wp_id:
                    log_message("  🟢 WordPress Success. Sending to LINE (OAR Notify)...")
                    if send_to_line(article): log_message("  ✅ Sent to LINE successfully")
                    else: log_message("  ⚠️ Failed to send to LINE")
                elif False and LINE_ENABLED and not wp_id:
                    log_message("  ⏭️ Skipped LINE Notify because WordPress sync failed")

                break # พบข่าวใหม่แล้วหยุด

    dur = int((datetime.now() - start_time).total_seconds() * 1000)
    log_fetch_operation_to_db(source_slug, 'success', len(articles), sent_count, new_count, None, dur)
    log_message("=== Completed ===")

def main():
    log_message("=== Starting innovation news fetch ===")
    if DRY_RUN:
        log_message("DRY_RUN mode is enabled: outbound integrations will be skipped")

    sources = get_sources_list()
    total_sources = len(sources)

    if total_sources == 0:
        log_message("❌ No active sources found in DB")
        return EXIT_OK

    current_idx = get_current_source_index() % total_sources
    source_name, fetcher = sources[current_idx]
    source_slug = get_slug_by_name(source_name)

    if not source_slug:
        log_message(f"  ❌ Cannot find slug for source: {source_name}")
        return

    log_message(f"🔄 Fetching from source {current_idx + 1}/{total_sources}: {source_name}")
    log_message(f"  📋 Active sources: {[s[0] for s in sources]}")

    current_started_at = datetime.now()
    articles = fetcher(source_name)
    if len(articles) > 0:
        log_message(f"✅ {source_name}: Found {len(articles)} innovation articles")
    else:
        log_message(f"⚠️ {source_name}: No articles found")

    update_source_index(current_idx, total_sources)

    current_result = process_articles_for_source(source_name, source_slug, articles)
    if not current_result['new_article']:
        log_message(f"  ℹ️ No new articles found from {source_name}")
        if send_telegram_message(format_no_new_articles_message(source_name)):
            current_result['sent_count'] = 1

    log_source_fetch_result(
        source_slug,
        len(articles),
        current_result['sent_count'],
        current_result['new_count'],
        current_started_at
    )

    if current_result['new_article']:
        log_message("=== Completed ===")
        return

    next_idx = (current_idx + 1) % total_sources
    next_source_name, next_fetcher = sources[next_idx]
    next_source_slug = get_slug_by_name(next_source_name)

    if not next_source_slug:
        log_message(f"  ❌ Cannot find slug for next source: {next_source_name}")
        log_message("=== Completed ===")
        return

    log_message(f"  🔍 Checking next source: {next_source_name} ({next_idx + 1}/{total_sources})")
    next_started_at = datetime.now()
    next_articles = next_fetcher(next_source_name)

    if len(next_articles) > 0:
        log_message(f"  ✅ {next_source_name}: Found {len(next_articles)} innovation articles")
    else:
        log_message(f"  ⚠️ {next_source_name}: No articles found")

    update_source_index(next_idx, total_sources)

    next_result = process_articles_for_source(next_source_name, next_source_slug, next_articles)
    log_source_fetch_result(
        next_source_slug,
        len(next_articles),
        next_result['sent_count'],
        next_result['new_count'],
        next_started_at
    )

    log_message("=== Completed ===")

# ============================================================
# Phase 2 Runtime Overrides
# ============================================================

FETCHER_METHODS = {
    'nia': 'html',
    'etda': 'rss',
    'techsauce': 'rss',
    'nstda': 'api',
    'ryt9': 'rss',
    'it24hrs': 'rss',
    'techtalkthai': 'rss',
    'nectec': 'html',
    'nriis': 'rss',
    'innomatter': 'rss',
    'techmovement': 'html',
}

def fetch_techmovement(source_name: str):
    """Fetch Tech Movement articles without external browser automation."""
    urls = get_source_url('techmovement')
    if not urls or not urls[0]:
        log_message("  ❌ No URL configured for TechMovement")
        return []

    try:
        response = requests.get(urls[0], timeout=30, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        cards = soup.select('div.group[data-variant]')

        articles = []
        seen_links = set()

        for card in cards:
            try:
                link_el = card.select_one('a[href*="/news/content/"]')
                link = link_el.get('href', '').strip() if link_el else ''
                if not link:
                    continue

                full_link = urllib.parse.urljoin(urls[0], link)
                if full_link in seen_links:
                    continue

                title_el = card.select_one('h3')
                title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""
                if not title:
                    continue

                excerpt_el = card.select_one('p')
                excerpt = clean_text(excerpt_el.get_text(" ", strip=True)) if excerpt_el else ""

                text_parts = [part.strip() for part in card.stripped_strings if part and part.strip()]
                time_candidates = [
                    part for part in text_parts
                    if any(keyword in part for keyword in ['ที่แล้ว', 'ชั่วโมง', 'วัน', 'เดือน'])
                ]
                time_str = time_candidates[-1] if time_candidates else ""
                summary = excerpt or title

                if not is_innovation_article(title, summary):
                    continue

                articles.append({
                    'title': title,
                    'link': full_link,
                    'date': time_str,
                    'summary': summary,
                    'source': 'TechMovement' if source_name is None else source_name,
                })
                seen_links.add(full_link)

                if len(articles) >= 10:
                    break

            except Exception as e:
                log_message(f"  ⚠️ TechMovement card parse error: {str(e)[:80]}")
                continue

        return articles
    except Exception as e:
        log_message(f"  ❌ TechMovement fetch error: {str(e)[:100]}")
        return []

FETCHER_MAP['techmovement'] = fetch_techmovement

def parse_tsv_output(raw_output: Optional[str], expected_columns: int) -> List[List[str]]:
    if not raw_output:
        return []

    rows: List[List[str]] = []
    for raw_line in raw_output.splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split('\t')
        if len(parts) >= expected_columns:
            rows.append(parts[:expected_columns])
    return rows

def get_saved_article_date_published(article_id: int) -> Optional[str]:
    try:
        out = run_mysql_query(
            f"SELECT date_published FROM innovation_news WHERE id = {int(article_id)} LIMIT 1;"
        )
        if not out:
            return None

        saved_value = out.strip().splitlines()[-1].strip()
        return saved_value or None
    except Exception as e:
        log_message(f"  Failed to read saved publish date for article {article_id}: {str(e)[:100]}")
        return None

def build_published_date_payload(article_id: int, fallback_date: str = '') -> Dict[str, str]:
    saved_date = get_saved_article_date_published(article_id) or (fallback_date or '').strip()
    parsed_date = parse_date(saved_date) if saved_date else None
    published_date_th = format_thai_date(parsed_date) if parsed_date else (saved_date or "ไม่ระบุวันที่")
    return {
        'date': saved_date,
        'published_date_th': published_date_th,
    }

def get_source_url(slug: str) -> Optional[List[str]]:
    try:
        include_inactive = env_flag('INNOVATION_NEWS_ALLOW_INACTIVE_SOURCE_URLS', False)
        active_filter = '' if include_inactive else ' AND is_active = 1'
        out = run_mysql_query(
            f"SELECT source_url FROM news_sources WHERE slug = {sql_quote(slug)}{active_filter};"
        )
        if not out:
            return None

        url_str = out.strip()
        candidate_urls = [url.strip() for url in url_str.split(',') if url.strip()]
        urls = [url for url in candidate_urls if source_url_is_allowed(url)]
        if len(urls) != len(candidate_urls):
            log_message(
                f"  Source URL rejected for {slug}: HTTPS is required and credentials must not be stored in URLs"
            )
        return urls or None
    except Exception as e:
        log_message(f"  ❌ Error fetching source URL for {slug}: {str(e)[:100]}")
        return None

def get_source_runtime_config(slug: str) -> Dict[str, str]:
    try:
        include_inactive = env_flag('INNOVATION_NEWS_ALLOW_INACTIVE_SOURCE_URLS', False)
        active_filter = '' if include_inactive else ' AND is_active = 1'
        out = run_mysql_query(
            "SELECT source_url, fetch_method, "
            "COALESCE(api_variant, ''), "
            "COALESCE(json_items_path, ''), "
            "COALESCE(json_title_field, ''), "
            "COALESCE(json_link_field, ''), "
            "COALESCE(json_date_field, ''), "
            "COALESCE(json_summary_field, '') "
            f"FROM news_sources WHERE slug = {sql_quote(slug)}{active_filter} LIMIT 1;"
        )
        rows = parse_tsv_output(out, 8)
        if not rows:
            return {}

        source_url, fetch_method, api_variant, json_items_path, json_title_field, json_link_field, json_date_field, json_summary_field = rows[0]
        return {
            'source_url': source_url,
            'fetch_method': fetch_method,
            'api_variant': api_variant or ('wordpress' if fetch_method == 'api' else ''),
            'json_items_path': json_items_path,
            'json_title_field': json_title_field,
            'json_link_field': json_link_field,
            'json_date_field': json_date_field,
            'json_summary_field': json_summary_field,
        }
    except Exception as e:
        log_message(f"  Error fetching source runtime config for {slug}: {str(e)[:100]}")
        return {}

def get_active_sources() -> List[Dict[str, str]]:
    try:
        out = run_mysql_query(
            "SELECT slug, name, fetch_method, COALESCE(api_variant, '') FROM news_sources WHERE is_active = 1 ORDER BY id;"
        )
        rows = parse_tsv_output(out, 4)
        return [
            {
                'slug': slug,
                'name': name,
                'fetch_method': fetch_method,
                'api_variant': api_variant or ('wordpress' if fetch_method == 'api' else ''),
            }
            for slug, name, fetch_method, api_variant in rows
        ]
    except Exception as e:
        log_message(f"  ❌ Error fetching active sources: {str(e)[:100]}")
        return []

def get_slug_by_name(name: str) -> Optional[str]:
    for slug, fetcher_name in FETCHER_NAMES.items():
        if fetcher_name in name or name == fetcher_name:
            return slug

    try:
        out = run_mysql_query(
            f"SELECT slug FROM news_sources WHERE name = {sql_quote(name)} LIMIT 1;"
        )
        if out:
            slug = out.strip()
            if slug:
                return slug
    except Exception as e:
        log_message(f"  ⚠️ Error fetching slug from DB for name '{name}': {str(e)[:80]}")

    return None

def extract_rss_item_text(item: ET.Element, *tag_names: str) -> str:
    for tag_name in tag_names:
        for child in item:
            local_name = child.tag.split('}', 1)[-1] if '}' in child.tag else child.tag
            if local_name.lower() == tag_name.lower():
                return (child.text or '').strip()
    return ''

def get_nested_value(value, path: str):
    current_value = value
    for part in (path or '').split('.'):
        segment = part.strip()
        if not segment:
            continue

        if isinstance(current_value, list):
            if not segment.isdigit():
                return None
            index = int(segment)
            if index < 0 or index >= len(current_value):
                return None
            current_value = current_value[index]
            continue

        if not isinstance(current_value, dict):
            return None

        if segment not in current_value:
            return None
        current_value = current_value[segment]

    return current_value

def normalize_json_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return clean_text(json.dumps(value, ensure_ascii=False))
    return clean_text(str(value))

def fetch_generic_rss_articles(slug: str, source_name: str) -> Tuple[List[Dict[str, str]], List[str]]:
    urls = get_source_url(slug)
    if not urls:
        return [], [f"No URL configured for {slug}"]

    all_articles: List[Dict[str, str]] = []
    errors: List[str] = []

    for url in urls:
        try:
            response = requests.get(url, timeout=30, headers=headers)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            items = root.findall('.//item')

            for item in items:
                title = clean_text(extract_rss_item_text(item, 'title'))
                link = extract_rss_item_text(item, 'link')
                date_value = extract_rss_item_text(item, 'pubDate', 'pubdate', 'published', 'updated')
                summary = clean_text(
                    extract_rss_item_text(item, 'description', 'encoded', 'summary', 'content')
                )

                if not title or not link:
                    continue

                all_articles.append({
                    'title': title,
                    'link': urllib.parse.urljoin(url, link.strip()),
                    'date': date_value,
                    'summary': summary or title,
                    'source': source_name,
                })
        except Exception as e:
            errors.append(f"{url}: {str(e)[:150]}")

    unique_articles: List[Dict[str, str]] = []
    seen_links = set()
    for article in all_articles:
        link = article.get('link', '').strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        unique_articles.append(article)

    unique_articles.sort(
        key=lambda article: parse_date(article.get('date', '')) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return unique_articles[:10], errors

def is_wordpress_posts_api_url(url: str) -> bool:
    if not url:
        return False

    parsed = urllib.parse.urlparse(url.strip())
    normalized_path = parsed.path.lower().rstrip('/')
    return '/wp-json/wp/v2/' in normalized_path

def build_wordpress_posts_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    if 'per_page' not in query:
        query['per_page'] = ['10']

    if '_fields' not in query:
        query['_fields'] = ['id,date,link,title,excerpt']

    return urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query, doseq=True))
    )

def fetch_generic_wordpress_api_articles(slug: str, source_name: str) -> Tuple[List[Dict[str, str]], List[str]]:
    urls = get_source_url(slug)
    if not urls:
        return [], [f"No URL configured for {slug}"]

    all_articles: List[Dict[str, str]] = []
    errors: List[str] = []

    for raw_url in urls:
        if not is_wordpress_posts_api_url(raw_url):
            errors.append(f"{raw_url}: unsupported API URL (generic API currently supports WordPress REST only)")
            continue

        request_url = build_wordpress_posts_api_url(raw_url)

        try:
            response = requests.get(request_url, timeout=30, headers=headers)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list):
                errors.append(f"{raw_url}: API response is not a list")
                continue

            for post in payload:
                title_value = post.get('title', {})
                excerpt_value = post.get('excerpt', {})
                title = clean_text(title_value.get('rendered') if isinstance(title_value, dict) else str(title_value or ''))
                link = str(post.get('link') or '').strip()
                date_value = str(post.get('date') or post.get('modified') or '')
                summary = clean_text(
                    excerpt_value.get('rendered') if isinstance(excerpt_value, dict) else str(excerpt_value or '')
                )

                if not title or not link:
                    continue

                all_articles.append({
                    'title': title,
                    'link': link,
                    'date': date_value,
                    'summary': summary or title,
                    'source': source_name,
                })
        except Exception as e:
            errors.append(f"{raw_url}: {str(e)[:150]}")

    unique_articles: List[Dict[str, str]] = []
    seen_links = set()
    for article in all_articles:
        link = article.get('link', '').strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        unique_articles.append(article)

    unique_articles.sort(
        key=lambda article: parse_date(article.get('date', '')) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return unique_articles[:10], errors

def is_generic_json_api_config_supported(config: Dict[str, str]) -> bool:
    if not config:
        return False

    source_url = str(config.get('source_url', '')).strip()
    return bool(
        source_url
        and ',' not in source_url
        and source_url_is_allowed(source_url)
        and config.get('api_variant') == 'generic_json'
        and config.get('json_items_path')
        and config.get('json_title_field')
        and config.get('json_link_field')
        and config.get('json_date_field')
    )

def fetch_generic_json_api_articles(slug: str, source_name: str) -> Tuple[List[Dict[str, str]], List[str]]:
    config = get_source_runtime_config(slug)
    if not config:
        return [], [f"No runtime config found for {slug}"]

    raw_source_url = str(config.get('source_url', '')).strip()
    if raw_source_url and not source_url_is_allowed(raw_source_url):
        return [], [
            f"{slug}: source URL rejected; use HTTPS and move credentials to the canonical environment file"
        ]

    if not is_generic_json_api_config_supported(config):
        return [], [f"{slug}: Generic JSON API config is incomplete"]

    request_url = raw_source_url
    items_path = config.get('json_items_path', '')
    title_field = config.get('json_title_field', '')
    link_field = config.get('json_link_field', '')
    date_field = config.get('json_date_field', '')
    summary_field = config.get('json_summary_field', '')

    source_env_suffix = re.sub(r'[^A-Za-z0-9]+', '_', slug).strip('_').upper()
    source_api_key = os.getenv(
        f'INNOVATION_NEWS_SOURCE_API_KEY_{source_env_suffix}',
        '',
    ).strip()
    source_api_header = os.getenv(
        f'INNOVATION_NEWS_SOURCE_API_KEY_HEADER_{source_env_suffix}',
        'X-Api-Key',
    ).strip()
    if source_api_key and not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", source_api_header):
        return [], [f"{slug}: invalid API credential header name"]
    if slug == 'newsapi' and not source_api_key:
        return [], [
            'newsapi: INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI is required in the canonical environment file'
        ]

    request_headers = dict(headers)
    if source_api_key:
        request_headers[source_api_header] = source_api_key

    try:
        response = requests.get(
            request_url,
            timeout=30,
            headers=request_headers,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise RuntimeError('redirect responses are not allowed for generic API sources')
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        return [], [truncate_error_message(f"{slug}: {str(e)}", max_length=250)]

    items = get_nested_value(payload, items_path)
    if not isinstance(items, list):
        return [], [f"{slug}: items_path '{items_path}' did not resolve to a list"]

    all_articles: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        title = normalize_json_text(get_nested_value(item, title_field))
        link = normalize_json_text(get_nested_value(item, link_field))
        date_value = normalize_json_text(get_nested_value(item, date_field))
        summary = normalize_json_text(get_nested_value(item, summary_field)) if summary_field else ''

        if not title or not link:
            continue

        all_articles.append({
            'title': title,
            'link': urllib.parse.urljoin(request_url, link.strip()),
            'date': date_value,
            'summary': summary or title,
            'source': source_name,
        })

    unique_articles: List[Dict[str, str]] = []
    seen_links = set()
    for article in all_articles:
        link = article.get('link', '').strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        unique_articles.append(article)

    unique_articles.sort(
        key=lambda article: parse_date(article.get('date', '')) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return unique_articles[:10], []

def build_runtime_fetcher(
    slug: str,
    source_name: str,
    fetch_method: str,
    fallback_fetcher,
):
    if fetch_method == 'rss':
        def fetch_via_rss_method(runtime_source_name: str):
            articles, errors = fetch_generic_rss_articles(slug, runtime_source_name)
            if articles:
                return articles

            if errors:
                safe_error = truncate_error_message(errors[0], max_length=250) or 'RSS source fetch failed'
                log_message(f"  ⚠️ RSS fetch via metadata returned no articles for {slug}; trying legacy fetcher")
                log_message(f"  ⚠️ RSS details: {safe_error}")

            if fallback_fetcher:
                fallback_articles = fallback_fetcher(runtime_source_name)
                if fallback_articles or not errors:
                    return fallback_articles

            if errors:
                raise RuntimeError(safe_error)

            return []

        return fetch_via_rss_method

    if fetch_method == 'api':
        def fetch_via_api_method(runtime_source_name: str):
            source_config = get_source_runtime_config(slug)
            api_variant = source_config.get('api_variant', 'wordpress')

            if api_variant == 'generic_json':
                articles, errors = fetch_generic_json_api_articles(slug, runtime_source_name)
            else:
                articles, errors = fetch_generic_wordpress_api_articles(slug, runtime_source_name)
            if articles:
                return articles

            if errors:
                safe_error = truncate_error_message(errors[0], max_length=250) or 'API source fetch failed'
                log_message(f"  ⚠️ API fetch via metadata returned no articles for {slug}; trying legacy fetcher")
                log_message(f"  ⚠️ API details: {safe_error}")

            if fallback_fetcher:
                fallback_articles = fallback_fetcher(runtime_source_name)
                if fallback_articles or not errors:
                    return fallback_articles

            if errors:
                raise RuntimeError(safe_error)

            return []

        return fetch_via_api_method

    return fallback_fetcher

def get_sources_list() -> List[Dict[str, object]]:
    try:
        sources_list: List[Dict[str, object]] = []
        for source in get_active_sources():
            slug = source['slug']
            name = source['name']
            fetch_method = source.get('fetch_method', '')
            fetcher = build_runtime_fetcher(
                slug,
                name,
                fetch_method,
                FETCHER_MAP.get(slug),
            )

            if not fetcher:
                log_message(f"  ⚠️ Skipping active source without fetcher implementation: {slug}")
                continue

            expected_method = FETCHER_METHODS.get(slug)
            if expected_method and fetch_method and expected_method != fetch_method:
                log_message(
                    f"  ⚠️ Source '{slug}' uses fetch_method='{fetch_method}' in DB but runtime expects '{expected_method}'"
                )

            sources_list.append({
                'slug': slug,
                'name': name,
                'fetch_method': fetch_method,
                'fetcher': fetcher,
            })

        return sources_list
    except Exception as e:
        log_message(f"  ❌ Error building sources list: {str(e)[:100]}")
        return []

def save_article_to_db(article: Dict, source_slug: str, source_name: str, content_hash: str) -> Optional[int]:
    try:
        if is_article_duplicate(article, content_hash):
            return None

        summary = article.get('summary', '').strip()
        if not summary:
            summary = article.get('title', '')[:500]
        if not summary:
            summary = 'No summary available'

        duplicate_conditions = build_duplicate_conditions(article, content_hash)
        duplicate_sql = ' OR '.join(duplicate_conditions) if duplicate_conditions else '1 = 0'
        query = (
            "START TRANSACTION; "
            f"SET @source_id := (SELECT id FROM news_sources WHERE slug = {sql_quote(source_slug)} LIMIT 1); "
            f"SET @existing_id := (SELECT id FROM innovation_news WHERE {duplicate_sql} ORDER BY id DESC LIMIT 1); "
            "INSERT INTO innovation_news "
            "("
            "source_id, title, summary, link, date_published, content_hash, "
            "date_sent, telegram_status, wordpress_status, line_status, created_at, updated_at"
            ") "
            "SELECT "
            f"@source_id, {sql_quote(article['title'])}, {sql_quote(summary[:800])}, {sql_quote(article.get('link', ''))}, "
            f"{sql_quote(article.get('date', ''))}, {sql_quote(content_hash)}, NOW(), "
            "'skipped', 'skipped', 'skipped', NOW(), NOW() "
            "FROM DUAL "
            "WHERE @source_id IS NOT NULL AND @existing_id IS NULL; "
            "SELECT COALESCE(NULLIF(LAST_INSERT_ID(), 0), 0), "
            "IF(@source_id IS NULL, 0, 1), "
            "IF(@existing_id IS NULL, 0, 1), "
            "ROW_COUNT(); "
            "COMMIT;"
        )
        out = run_mysql_query(query)
        rows = parse_tsv_output(out, 4)
        if not rows:
            return None

        article_id, source_exists, duplicate_exists, inserted_rows = rows[-1]
        if not int(source_exists):
            log_message(f"  ❌ Source slug not found in DB: {source_slug}")
            return None

        if int(duplicate_exists) or int(inserted_rows) == 0:
            return None

        inserted_article_id = int(article_id)
        if inserted_article_id:
            log_message(f"  Saved new article to DB: {article['title'][:50]}")
            return inserted_article_id

        return None
    except Exception as e:
        log_message(f"  ❌ DB save error: {str(e)[:150]}")
        return None

def is_article_duplicate(article: Dict, content_hash: Optional[str] = None) -> bool:
    conditions = build_duplicate_conditions(article, content_hash)
    if not conditions:
        return False

    out = run_mysql_query(f"SELECT COUNT(*) FROM innovation_news WHERE {' OR '.join(conditions)};")
    return int(out) > 0 if out else False

def log_fetch_operation_to_db(
    source_slug,
    status,
    found,
    sent,
    new,
    err,
    duration,
    mysql_status='skipped',
    telegram_status='skipped',
    wordpress_status='skipped',
    line_status='skipped',
):
    try:
        normalized_status = status if status in {'success', 'partial', 'failed', 'error'} else 'error'
        success_increment = 1 if normalized_status in {'success', 'partial'} else 0
        error_increment = 1 if normalized_status in {'failed', 'error'} else 0
        last_fetched_at_sql = "NOW()" if success_increment else "last_fetched_at"
        error_message = truncate_error_message(err)

        run_mysql_query(
            "START TRANSACTION; "
            "INSERT INTO fetch_logs "
            "("
            "source_id, articles_found, new_articles, mysql_status, "
            "articles_sent, telegram_status, wordpress_status, line_status, "
            "status, error_message, duration_ms, created_at"
            ") "
            "SELECT id, "
            f"{int(found)}, {int(new)}, {sql_quote(mysql_status)}, "
            f"{int(sent)}, {sql_quote(telegram_status)}, {sql_quote(wordpress_status)}, {sql_quote(line_status)}, "
            f"{sql_quote(normalized_status)}, {sql_quote(error_message)}, {int(duration)}, NOW() "
            f"FROM news_sources WHERE slug = {sql_quote(source_slug)} LIMIT 1; "
            "UPDATE news_sources "
            f"SET fetch_count = fetch_count + 1, success_count = success_count + {success_increment}, "
            f"error_count = error_count + {error_increment}, last_fetched_at = {last_fetched_at_sql}, "
            "updated_at = CURRENT_TIMESTAMP "
            f"WHERE slug = {sql_quote(source_slug)}; "
            "COMMIT;"
        )
    except Exception as e:
        log_message(f"  ⚠️ Failed to log fetch operation: {str(e)[:100]}")

def safe_fetch_articles(source_name: str, fetcher) -> Tuple[List[Dict], Optional[str]]:
    try:
        articles = fetcher(source_name) or []
        if not isinstance(articles, list):
            return [], f"Fetcher returned invalid payload for {source_name}"

        eligible_articles = []
        skipped_missing_or_unparseable = 0
        skipped_old = 0

        for article in articles:
            date_obj = parse_date(article.get('date', ''))
            if not date_obj:
                skipped_missing_or_unparseable += 1
                continue
            if not is_within_last_1_year(date_obj):
                skipped_old += 1
                continue
            eligible_articles.append(article)

        if skipped_missing_or_unparseable or skipped_old:
            log_message(
                f"  Skipped {skipped_missing_or_unparseable} article(s) without parseable source date "
                f"and {skipped_old} article(s) older than 1 year for {source_name}"
            )

        return eligible_articles, None
    except Exception as e:
        return [], truncate_error_message(f"Fetcher error for {source_name}: {str(e)}", max_length=400)

def process_articles_for_source(source_name: str, source_slug: str, articles: List[Dict]) -> Dict:
    result = {
        'new_article': None,
        'sent_count': 0,
        'new_count': 0,
        'status': 'success',
        'error_message': None,
        'issues': [],
        'mysql_status': 'skipped',
        'telegram_status': 'skipped',
        'wordpress_status': 'skipped',
        'line_status': 'skipped',
    }

    for article in articles:
        try:
            date_obj = parse_date(article.get('date', ''))
            if not is_within_last_1_year(date_obj):
                continue

            content_hash = generate_content_hash(article)
            if is_article_duplicate(article, content_hash):
                continue

            if source_slug not in ["nia", "nstda"] and not is_innovation_article(article.get('title', ''), article.get('summary', '')):
                continue

            log_message(f"  Selected new article from {source_name}: {article.get('title', '')[:50]}")
            article['source'] = source_name

            article_id = save_article_to_db(article, source_slug, source_name, content_hash)
            if not article_id:
                result['mysql_status'] = 'failed'
                result['issues'].append('Failed to save article to database')
                break

            result['new_article'] = article
            result['new_count'] = 1
            result['mysql_status'] = 'saved'
            article.update(build_published_date_payload(article_id, article.get('date', '')))
            article['benefits'] = generate_benefits(article.get('title', ''), article.get('summary', ''))
            if ENABLE_EMAIL_WORKER and not save_article_benefits_to_db(article_id, article['benefits']):
                result['issues'].append('Failed to save article benefits for email delivery')

            log_message("  Sending to Telegram...")
            telegram_sent = send_telegram_message(format_message(article))
            result['sent_count'] = 1 if telegram_sent else 0
            if telegram_sent:
                result['telegram_status'] = 'sent'
            elif DRY_RUN:
                result['telegram_status'] = 'dry_run'
            elif not ENABLE_TELEGRAM:
                result['telegram_status'] = 'disabled'
            elif not TELEGRAM_CHAT_ID:
                result['telegram_status'] = 'not_configured'
            else:
                result['telegram_status'] = 'failed'
            if not telegram_sent and not DRY_RUN and ENABLE_TELEGRAM and TELEGRAM_CHAT_ID:
                result['issues'].append('Telegram send failed')

            wp_result = sync_wordpress_and_line(article, content_hash, result['issues'])
            result['wordpress_status'] = wp_result.get('status', 'skipped')
            result['line_status'] = wp_result.get('line_status', 'skipped')
            if not update_article_delivery_statuses(
                article_id,
                result['telegram_status'],
                result['wordpress_status'],
                result['line_status'],
                wp_result.get('wordpress_url'),
            ):
                result['issues'].append('Failed to update article delivery status')
            wp_id = None
            if False and WORDPRESS_ENABLED:
                log_message("  Syncing to WordPress...")
                wp_id = save_to_wordpress(article, content_hash)
                if wp_id:
                    log_message(f"  Saved to WP (ID: {wp_id})")
                else:
                    log_message("  ⚠️ WordPress sync failed")
                    result['issues'].append('WordPress sync failed')

            if False and LINE_ENABLED and wp_id:
                log_message("  WordPress Success. Sending to LINE (OAR Notify)...")
                if send_to_line(article):
                    log_message("  Sent to LINE successfully")
                else:
                    log_message("  ⚠️ Failed to send to LINE")
                    result['issues'].append('LINE send failed')
            elif False and LINE_ENABLED and WORDPRESS_ENABLED and not wp_id:
                log_message("  Skipped LINE Notify because WordPress sync failed")

            break
        except Exception as e:
            result['issues'].append(f"Article processing error: {str(e)}")
            break

    if result['issues']:
        result['status'] = 'partial' if result['new_article'] else 'error'
        result['error_message'] = combine_error_messages(result['issues'])

    return result

def log_source_fetch_result(
    source_slug: str,
    articles_found: int,
    sent_count: int,
    new_count: int,
    started_at: datetime,
    status: str = 'success',
    error_message: Optional[str] = None,
    mysql_status: str = 'skipped',
    telegram_status: str = 'skipped',
    wordpress_status: str = 'skipped',
    line_status: str = 'skipped',
):
    duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
    log_fetch_operation_to_db(
        source_slug,
        status,
        articles_found,
        sent_count,
        new_count,
        error_message,
        duration_ms,
        mysql_status,
        telegram_status,
        wordpress_status,
        line_status,
    )

def build_fetch_error_result(error_message: str) -> Dict[str, object]:
    return {
        'new_article': None,
        'sent_count': 0,
        'new_count': 0,
        'status': 'error',
        'error_message': error_message,
        'mysql_status': 'skipped',
        'telegram_status': 'skipped',
        'wordpress_status': 'skipped',
        'line_status': 'skipped',
    }

def run_source_cycle(source: Dict[str, object], source_index: int, total_sources: int) -> Dict[str, object]:
    source_name = str(source['name'])
    source_slug = str(source['slug'])
    fetcher = source['fetcher']

    log_message(f"Fetching from source {source_index + 1}/{total_sources}: {source_name}")

    started_at = datetime.now()
    articles, fetch_error = safe_fetch_articles(source_name, fetcher)
    if fetch_error:
        log_message(f"  ❌ {fetch_error}")
        result = build_fetch_error_result(fetch_error)
    else:
        if articles:
            log_message(f"  {source_name}: Found {len(articles)} innovation articles")
        else:
            log_message(f"  {source_name}: No articles found")

        result = process_articles_for_source(source_name, source_slug, articles)
        if not result['new_article'] and result.get('status') == 'success':
            log_message(f"  No new articles found from {source_name}")

    log_source_fetch_result(
        source_slug,
        len(articles),
        result['sent_count'],
        result['new_count'],
        started_at,
        result.get('status', 'success'),
        result.get('error_message'),
        result.get('mysql_status', 'skipped'),
        result.get('telegram_status', 'skipped'),
        result.get('wordpress_status', 'skipped'),
        result.get('line_status', 'skipped'),
    )
    update_source_index(source_index, total_sources)
    return result

def _run_fetch_cycle() -> int:
    log_message("=== Starting innovation news fetch ===")
    env_source_marker = os.getenv('INNOVATION_NEWS_ENV_SOURCE', '').strip()
    discovered_env = str(ENV_FILE) if ENV_FILE else 'none'
    log_message(
        "Environment configuration: "
        f"source={env_source_marker or 'process-environment-or-unknown'}, "
        f"python_candidate={discovered_env}"
    )

    sources = get_sources_list()
    total_sources = len(sources)
    if total_sources == 0:
        log_message("❌ No active sources found in DB")
        return EXIT_OK

    log_message(f"  Active sources: {[source['name'] for source in sources]}")
    current_idx = get_current_source_index() % total_sources
    encountered_errors = False

    for offset in range(total_sources):
        source_idx = (current_idx + offset) % total_sources
        result = run_source_cycle(sources[source_idx], source_idx, total_sources)

        if result.get('status') in {'error', 'partial'} and not result.get('new_article'):
            encountered_errors = True

        if result.get('new_article'):
            log_message(
                f"  Completed after finding a new article from {sources[source_idx]['name']}"
            )
            log_message("=== Completed ===")
            return EXIT_OK

    if encountered_errors:
        log_message("  Completed full source sweep with one or more source errors; skipping summary Telegram message")
    else:
        log_message("  Completed full source sweep with no new eligible articles")
        send_telegram_message(
            format_no_new_articles_message(f"ทุกแหล่งข่าวที่เปิดใช้งาน ({total_sources} แหล่ง)")
        )

    log_message("=== Completed ===")
    return EXIT_OK


def main() -> int:
    try:
        with global_fetch_lock() as acquired:
            if not acquired:
                log_message(
                    'Fetch skipped: another process already holds the global run lock'
                )
                return EXIT_FETCH_ALREADY_RUNNING

            return _run_fetch_cycle()
    except GlobalFetchLockError as exc:
        log_message(f'Fetch aborted: global run lock unavailable ({str(exc)[:200]})')
        return EXIT_FETCH_LOCK_ERROR
    except Exception as exc:
        log_message(f'Fetch aborted by unexpected error: {str(exc)[:200]}')
        return EXIT_UNEXPECTED_ERROR

if __name__ == "__main__":
    raise SystemExit(main())
