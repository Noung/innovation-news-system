#!/opt/scrapling-venv/bin/python3
"""
TechMovement.co.th Scraper
ดึงข้อมูลข่าวจากหน้าแรก
"""

import sys
import json

sys.path.insert(0, '/opt/scrapling-venv/lib/python3.12/site-packages')

from scrapling.fetchers import DynamicFetcher

def scrape_techmovement():
    """ดึงข่าวจากหน้าแรก TechMovement"""

    page = DynamicFetcher.fetch('https://techmovement.co.th', headless=True, network_idle=True)

    # หา card ข่าวทั้งหมด
    cards = page.css('div.group[data-variant]')

    news_items = []

    for card in cards:
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

        # ดึงรูปภาพ
        img_url = card.css('img::attr(src)').get() or ""
        img_alt = card.css('img::attr(alt)').get() or ""

        # ดึง excerpt
        excerpt = card.css('p::text').get() or ""
        excerpt = excerpt.strip()

        if link and title:
            news_items.append({
                'category': category.strip(),
                'title': title,
                'excerpt': excerpt,
                'time': time_str,
                'link': f'https://techmovement.co.th{link}',
                'image': img_url,
                'image_alt': img_alt
            })

    return news_items

def main():
    print("📰 กำลังดึงข่าวจาก TechMovement.co.th...")
    news = scrape_techmovement()

    # ลบข่าวซ้ำโดยใช้ link เป็น reference
    seen_links = set()
    unique_news = []
    for item in news:
        if item['link'] not in seen_links:
            seen_links.add(item['link'])
            unique_news.append(item)

    news = unique_news

    print(f"\n✅ ดึงข้อมูลสำเร็จ {len(news)} ข่าว (ซ้ำ {len(seen_links) - len(unique_news)} ข่าว)\n")
    print("=" * 80)

    for i, item in enumerate(news, 1):
        print(f"\n📌 ข่าวที่ {i}")
        print(f"   หมวดหมู่: {item['category']}")
        print(f"   หัวข้อ: {item['title']}")
        print(f"   เวลา: {item['time']}")
        if item['excerpt']:
            print(f"   เนื้อหา: {item['excerpt'][:100]}...")
        print(f"   ลิงก์: {item['link']}")

    print("\n" + "=" * 80)

    # บันทึกเป็น JSON
    with open('/tmp/techmovement-news.json', 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=2)

    print(f"\n💾 บันทึกข้อมูลไปที่: /tmp/techmovement-news.json")

if __name__ == '__main__':
    main()
