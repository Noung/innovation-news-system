#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure benefit classification helpers for migration and audit tooling.

This module mirrors the current deterministic classifier in
``fetch-innovation-news-mysql.py`` while exposing evidence and fallback
details that the live fetcher does not currently return.
"""

import re
import unicodedata
from typing import Dict, List


CLASSIFIER_VERSION = 'benefit-keywords-2026-07-26-v2'
BENEFITS_PER_ARTICLE = 3

# These tokens have well-known false-positive substrings in ordinary prose.
# For example, ``defi`` must not match the Design Thinking stage ``define``.
# Legacy-compatible mode remains available so the live fetcher is unchanged;
# the backfill planner opts in to strict matching.
STRICT_TOKEN_KEYWORDS = frozenset({
    'defi',
})

DEFAULT_BENEFITS = [
    'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
    'การวิจัยและพัฒนาองค์ความรู้',
    'การปรับตัวต่อเทรนด์และตลาด',
]

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

BENEFIT_KEYWORDS = {
    'ความสามารถในการแข่งขัน': [
        'competitiveness', 'competitive', 'แข่งขัน', 'ขีดความสามารถ',
        'ระดับโลก', 'global competitiveness',
    ],
    'การลดต้นทุนและเพิ่มประสิทธิภาพ': [
        'cost reduction', 'cost saving', 'saving', 'ลดต้นทุน',
        'ประสิทธิภาพ', 'efficiency', 'productivity', 'lean',
        'optimization', 'budget', 'value for money',
    ],
    'การปรับตัวสู่ดิจิทัลทรานส์ฟอร์เมชัน': [
        'digital transformation', 'digitalization', 'digitization',
        'digitize', 'ดิจิทัลทรานส์ฟอร์เมชัน', 'เปลี่ยนผ่านดิจิทัล',
        'ดิจิทัล',
    ],
    'การพัฒนาทักษะและการเรียนรู้': [
        'skill', 'reskill', 'upskill', 'training', 'learning', 'learn',
        'ทักษะ', 'การเรียนรู้', 'อบรม', 'หลักสูตร', 'edtech',
        'education technology',
    ],
    'การใช้งาน AI และเทคโนโลยีขั้นสูง': [
        'ai', 'artificial intelligence', 'ปัญญาประดิษฐ์',
        'machine learning', 'deep learning', 'neural network', 'llm',
        'large language model', 'generative ai', 'foundation model',
    ],
    'ความปลอดภัยและความเป็นส่วนตัว': [
        'security', 'cybersecurity', 'cyber', 'privacy', 'data privacy',
        'protection', 'trust', 'zero trust', 'ความปลอดภัย',
        'ความเป็นส่วนตัว', 'คุ้มครองข้อมูล',
    ],
    'การสร้างนวัตกรรมและการเปลี่ยนแปลง': [
        'innovation', 'innovative', 'innovat', 'disruption', 'disruptive',
        'transformation', 'change', 'นวัตกรรม', 'การเปลี่ยนแปลง',
    ],
    'การปรับตัวต่อเทรนด์และตลาด': [
        'trend', 'market trend', 'market', 'future of', 'future trend',
        'emerging', 'consumer behavior', 'ทิศทาง', 'แนวโน้ม', 'ตลาด',
    ],
    'การจัดการข้อมูลและวิเคราะห์ข้อมูล': [
        'data', 'analytics', 'data analytics', 'big data', 'predictive',
        'business intelligence', 'insight', 'dashboard', 'วิเคราะห์ข้อมูล',
        'ข้อมูลเชิงลึก',
    ],
    'การสร้างประสบการณ์ลูกค้าและบริการ': [
        'customer', 'customer experience', 'cx', 'service',
        'user experience', 'ux', 'ลูกค้า', 'ประสบการณ์ลูกค้า', 'การบริการ',
    ],
    'การเชื่อมต่อและการทำงานร่วมกัน': [
        'collaboration', 'collaborate', 'connect', 'connected',
        'partnership', 'partner', 'ecosystem', 'ร่วมมือ', 'ความร่วมมือ',
        'เครือข่าย',
    ],
    'การพัฒนาเทคโนโลยีและโครงสร้าง': [
        'technology', 'infrastructure', 'cloud', 'iot', 'smart',
        'automation', 'robotics', 'remote work', 'hybrid work',
        'digital workplace', 'workplace technology', 'โครงสร้างพื้นฐาน',
        'ระบบอัตโนมัติ',
    ],
    'การสนับสนุนนวัตกรรมและสตาร์ทอัพ': [
        'startup', 'start-up', 'entrepreneur', 'venture', 'incubator',
        'accelerator', 'ecosystem', 'สตาร์ทอัพ', 'ผู้ประกอบการ',
        'ระบบนิเวศนวัตกรรม',
    ],
    'การใช้เทคโนโลยีสีเขียวและยั่งยืน': [
        'green technology', 'green tech', 'sustainable', 'sustainability',
        'carbon', 'carbon neutral', 'circular economy', 'esg',
        'เทคโนโลยีสีเขียว', 'ยั่งยืน', 'เศรษฐกิจหมุนเวียน',
    ],
    'การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน': [
        'blockchain', 'fintech', 'digital asset', 'crypto',
        'cryptocurrency', 'defi', 'web3', 'บล็อกเชน', 'ฟินเทค',
        'สินทรัพย์ดิจิทัล',
    ],
    'การพัฒนาสุขภาพและการดูแลโรงพยาบาล': [
        'healthtech', 'digital health', 'telemedicine', 'wellness',
        'healthcare', 'hospital', 'medical ai', 'เฮลท์เทค',
        'สุขภาพดิจิทัล', 'การแพทย์ทางไกล',
    ],
    'การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์': [
        'generative ai', 'copilot', 'ai assistant', 'agentic ai',
        'autonomous agent', 'ai agent', 'ผู้ช่วยอัจฉริยะ',
    ],
    'การพัฒนาภาคศึกษาและเมืองอัจฉริยะ': [
        'smart city', 'urban tech', 'digital economy', 'metaverse',
        'virtual reality', 'augmented reality', 'vr', 'ar',
        'เมืองอัจฉริยะ', 'เศรษฐกิจดิจิทัล',
    ],
    'การทำธุรกิจในยุคดิจิทัล': [
        'ecommerce', 'e-commerce', 'retailtech', 'marketplace',
        'digital business', 'online business', 'อีคอมเมิร์ซ',
        'ธุรกิจดิจิทัล', 'รีเทลเทค',
    ],
    'การวิจัยและพัฒนาองค์ความรู้': [
        'research', 'research and development', 'r&d', 'ศึกษา',
        'ศึกษาวิจัย', 'งานวิจัย', 'paper', 'academic', 'scholar',
        'journal', 'publication', 'ตีพิมพ์', 'บทความวิชาการ',
        'peer review', 'literature review', 'methodology', 'experimental',
        'experiment', 'hypothesis', 'องค์ความรู้', 'ฐานความรู้',
        'knowledge creation', 'knowledge base', 'การวิจัยและพัฒนา',
        'การสร้างองค์ความรู้',
    ],
}


def _keyword_matches(
    text: str,
    keyword: str,
    *,
    strict: bool = False,
) -> bool:
    """Avoid false positives for short or known-ambiguous Latin tokens."""
    normalized_keyword = keyword.lower().strip()
    is_ascii_token = (
        normalized_keyword.isascii()
        and re.fullmatch(r'[a-z0-9+#.&-]+', normalized_keyword)
    )
    if (
        is_ascii_token
        and (
            len(normalized_keyword) <= 3
            or (
                strict
                and normalized_keyword in STRICT_TOKEN_KEYWORDS
            )
        )
    ):
        return bool(re.search(
            rf'(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])',
            text,
        ))
    return normalized_keyword in text


def classify_benefits(
    title: str,
    summary: str,
    *,
    strict: bool = False,
) -> Dict[str, object]:
    """Return the selected benefits plus deterministic matching evidence."""
    title_text = unicodedata.normalize('NFKC', str(title or '')).lower()
    summary_text = unicodedata.normalize('NFKC', str(summary or '')).lower()

    ranked = []
    for order, (benefit, keywords) in enumerate(BENEFIT_KEYWORDS.items()):
        title_matches = [
            keyword for keyword in keywords
            if _keyword_matches(title_text, keyword, strict=strict)
        ]
        summary_matches = [
            keyword for keyword in keywords
            if keyword not in title_matches
            and _keyword_matches(summary_text, keyword, strict=strict)
        ]
        if not title_matches and not summary_matches:
            continue

        score = (
            (len(title_matches) * 300)
            + sum(len(keyword) for keyword in title_matches)
            + (len(summary_matches) * 100)
            + sum(len(keyword) for keyword in summary_matches)
        )
        ranked.append({
            'benefit': benefit,
            'score': score,
            'order': order,
            'title_keywords': title_matches,
            'summary_keywords': summary_matches,
            'origin': 'matched',
        })

    ranked.sort(key=lambda item: (-item['score'], item['order']))
    selected_details = [dict(item) for item in ranked[:BENEFITS_PER_ARTICLE]]

    fallback_benefits = []
    for fallback_benefit in DEFAULT_BENEFITS:
        if len(selected_details) >= BENEFITS_PER_ARTICLE:
            break
        if any(
            item['benefit'] == fallback_benefit
            for item in selected_details
        ):
            continue
        fallback_benefits.append(fallback_benefit)
        selected_details.append({
            'benefit': fallback_benefit,
            'score': 0,
            'order': list(BENEFIT_KEYWORDS).index(fallback_benefit),
            'title_keywords': [],
            'summary_keywords': [],
            'origin': 'fallback',
        })

    selected_details = selected_details[:BENEFITS_PER_ARTICLE]
    return {
        'classifier_version': CLASSIFIER_VERSION,
        'matching_mode': 'strict' if strict else 'legacy-compatible',
        'selected': [item['benefit'] for item in selected_details],
        'selected_details': selected_details,
        'ranked_matches': ranked,
        'fallback_benefits': fallback_benefits,
        'fallback_count': len(fallback_benefits),
    }


def generate_benefits(title: str, summary: str) -> List[str]:
    """Compatibility wrapper returning exactly three controlled benefits."""
    return list(classify_benefits(title, summary)['selected'])
