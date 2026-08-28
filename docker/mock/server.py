#!/usr/bin/env python3
"""HTTPS-only local mocks for source, WordPress, and LINE integrations."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CERT_DIR = Path(os.getenv("MOCK_CERT_DIR", "/certs"))
CA_CERT = CERT_DIR / "local-ca.crt"
CA_KEY = CERT_DIR / "local-ca.key"
SERVER_CERT = CERT_DIR / "mock-integrations.crt"
SERVER_KEY = CERT_DIR / "mock-integrations.key"

BENEFIT_TERMS = [
    ("ความสามารถในการแข่งขัน", "competitiveness"),
    ("การลดต้นทุนและเพิ่มประสิทธิภาพ", "cost-efficiency"),
    ("การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน", "digital-transformation"),
    ("การพัฒนาทักษะและการเรียนรู้", "skills-learning"),
    ("การใช้งาน AI และเทคโนโลยีขั้นสูง", "ai-advanced-technology"),
    ("ความปลอดภัยและความเป็นส่วนตัว", "security-privacy"),
    ("การสร้างนวัตกรรมและการเปลี่ยนแปลง", "innovation-change"),
    ("การปรับตัวต่อเทรนด์และตลาด", "trends-market-adaptation"),
    ("การจัดการข้อมูลและวิเคราะห์ข้อมูล", "data-management-analytics"),
    ("การสร้างประสบการณ์ลูกค้าและบริการ", "customer-experience-service"),
    ("การเชื่อมต่อและการทำงานร่วมกัน", "connectivity-collaboration"),
    ("การพัฒนาเทคโนโลยีและโครงสร้าง", "technology-infrastructure"),
    ("การสนับสนุนนวัตกรรมและสตาร์ทอัพ", "innovation-startup-support"),
    ("การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน", "blockchain-fintech"),
    ("การใช้เทคโนโลยีสีเขียวและยั่งยืน", "green-technology-sustainability"),
    ("การพัฒนาสุขภาพและการดูแลโรงพยาบาล", "healthcare-hospital-care"),
    ("การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์", "generative-ai"),
    ("การพัฒนาภาคศึกษาและเมืองอัจฉริยะ", "education-smart-city"),
    ("การทำธุรกิจในยุคดิจิทัล", "digital-business"),
    ("การวิจัยและพัฒนาองค์ความรู้", "research-knowledge-development"),
]

STATE_LOCK = threading.Lock()
TERMS = [
    {"id": index, "name": name, "slug": slug}
    for index, (name, slug) in enumerate(BENEFIT_TERMS, start=1)
]
POSTS: list[dict] = []


def run_openssl(*args: str) -> None:
    subprocess.run(
        ["openssl", *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def ensure_certificates() -> None:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    if all(path.exists() for path in (CA_CERT, CA_KEY, SERVER_CERT, SERVER_KEY)):
        certificate_is_current = subprocess.run(
            ["openssl", "x509", "-checkend", "86400", "-noout", "-in", str(SERVER_CERT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if certificate_is_current:
            return

    for path in (CA_CERT, CA_KEY, SERVER_CERT, SERVER_KEY, CERT_DIR / "local-ca.srl"):
        path.unlink(missing_ok=True)

    csr_path = CERT_DIR / "mock-integrations.csr"
    ext_path = CERT_DIR / "mock-integrations.ext"
    run_openssl(
        "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(CA_KEY), "-out", str(CA_CERT),
        "-sha256", "-days", "30", "-subj", "/CN=Innovation News Local CA",
    )
    run_openssl(
        "req", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(SERVER_KEY), "-out", str(csr_path),
        "-subj", "/CN=mock-integrations",
    )
    ext_path.write_text(
        "subjectAltName=DNS:mock-integrations,DNS:localhost,IP:127.0.0.1\n"
        "extendedKeyUsage=serverAuth\n",
        encoding="utf-8",
    )
    run_openssl(
        "x509", "-req", "-in", str(csr_path),
        "-CA", str(CA_CERT), "-CAkey", str(CA_KEY), "-CAcreateserial",
        "-out", str(SERVER_CERT), "-days", "30", "-sha256",
        "-extfile", str(ext_path),
    )
    csr_path.unlink(missing_ok=True)
    ext_path.unlink(missing_ok=True)
    CA_KEY.chmod(0o600)
    SERVER_KEY.chmod(0o600)
    CA_CERT.chmod(0o644)
    SERVER_CERT.chmod(0o644)


class MockHandler(BaseHTTPRequestHandler):
    server_version = "InnovationNewsLocalMock/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"mock-integrations: {self.command} {self.path} - {fmt % args}", flush=True)

    def send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            return payload if isinstance(payload, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_OPTIONS(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path == "/wp-json/wp/v2/innovation-tip":
            self.send_json(200, {
                "schema": {
                    "properties": {
                        "title": {"type": "object"},
                        "content": {"type": "object"},
                        "organization-benefits": {"type": "array"},
                    }
                }
            })
            return
        self.send_json(404, {"error": "not_found"})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/health":
            self.send_json(200, {"status": "ok", "service": "local-mock"})
            return

        if path == "/api/news":
            now = datetime.now(timezone.utc).isoformat()
            self.send_json(200, {
                "items": [
                    {
                        "title": "นวัตกรรม AI สำหรับการวิจัยในสภาพแวดล้อมจำลอง",
                        "summary": "ข้อมูลตัวอย่างสังเคราะห์สำหรับทดสอบระบบ local เท่านั้น",
                        "link": "https://mock-integrations:8443/articles/local-001",
                        "published_at": now,
                    },
                    {
                        "title": "เทคโนโลยีสีเขียวตัวอย่างสำหรับ local development",
                        "summary": "ไม่มีข้อมูล บุคคล หรือเนื้อหาจากระบบจริง",
                        "link": "https://mock-integrations:8443/articles/local-002",
                        "published_at": now,
                    },
                ]
            })
            return

        if path.startswith("/articles/"):
            body = b"<html><body>Local synthetic article</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/wp-json/wp/v2/organization-benefits":
            slug = (query.get("slug") or [""])[0]
            with STATE_LOCK:
                payload = [term for term in TERMS if not slug or term["slug"] == slug]
            self.send_json(200, payload)
            return

        if path == "/wp-json/wp/v2/innovation-tip":
            search = (query.get("search") or [""])[0].casefold()
            with STATE_LOCK:
                payload = [
                    post for post in POSTS
                    if not search or search in str(post.get("title", {}).get("rendered", "")).casefold()
                ]
            self.send_json(200, payload)
            return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        payload = self.read_json()

        if path == "/api/notify":
            self.send_json(200, {"success": True, "mock": True})
            return

        if path == "/wp-json/wp/v2/organization-benefits":
            slug = str(payload.get("slug", "")).strip()
            name = str(payload.get("name", "")).strip()
            with STATE_LOCK:
                existing = next((term for term in TERMS if term["slug"] == slug), None)
                if existing:
                    self.send_json(400, {
                        "code": "term_exists",
                        "message": "Term already exists",
                        "data": {"term_id": existing["id"]},
                    })
                    return
                term = {"id": len(TERMS) + 1, "name": name, "slug": slug}
                TERMS.append(term)
            self.send_json(201, term)
            return

        if path == "/wp-json/wp/v2/innovation-tip":
            with STATE_LOCK:
                post_id = len(POSTS) + 1
                title = payload.get("title", "")
                post = {
                    "id": post_id,
                    "title": {"rendered": title},
                    "link": f"https://mock-integrations:8443/innovation-tip/{post_id}",
                    "organization-benefits": payload.get("organization-benefits", []),
                }
                POSTS.append(post)
            self.send_json(201, post)
            return

        if path.startswith("/wp-json/wp/v2/innovation-tip/"):
            try:
                post_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self.send_json(400, {"error": "invalid_post_id"})
                return
            with STATE_LOCK:
                post = next((item for item in POSTS if item["id"] == post_id), None)
                if post is None:
                    self.send_json(404, {"error": "not_found"})
                    return
                post["organization-benefits"] = payload.get("organization-benefits", [])
            self.send_json(200, post)
            return

        self.send_json(404, {"error": "not_found"})


def main() -> None:
    ensure_certificates()
    server = ThreadingHTTPServer(("0.0.0.0", 8443), MockHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print("mock-integrations: listening on https://0.0.0.0:8443", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
