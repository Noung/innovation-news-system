# WordPress taxonomy: ประโยชน์ต่อองค์กร

## โครงสร้างที่ใช้

ระบบใช้ **1 taxonomy และ 20 terms** ไม่ใช่ 20 taxonomies:

| รายการ | ค่า |
|---|---|
| Post type | `innovation-tip` |
| Taxonomy key ภายใน WordPress | `organization_benefit` |
| ชื่อที่แสดง | ประโยชน์ต่อองค์กร |
| REST base และชื่อ field ใน post payload | `organization-benefits` |
| จำนวน terms ต่อข่าว | 3 รายการที่ไม่ซ้ำกัน |

Term ID ของ WordPress ไม่ถูก hard-code เพราะแต่ละเครื่องมี ID ไม่เหมือนกัน สคริปต์จะค้นหาด้วย slug ที่คงที่ แล้วส่ง ID ทั้ง 3 ค่าใน payload เช่น:

```json
{
  "title": "ตัวอย่างข่าว",
  "status": "publish",
  "organization-benefits": [31, 42, 57]
}
```

## ติดตั้งปลั๊กอินบน WordPress

ปลั๊กอินอยู่ที่:

```text
wordpress-plugin/innovation-tip-benefit-taxonomy/
```

นำทั้งโฟลเดอร์ไปไว้ที่ `wp-content/plugins/` หรือบีบอัดโฟลเดอร์เป็น ZIP แล้วติดตั้งผ่าน **Plugins → Add New → Upload Plugin** จากนั้น activate ปลั๊กอิน `Innovation Tip Benefit Taxonomy`

เมื่อ activate แล้ว ปลั๊กอินจะ:

- ผูก taxonomy `organization_benefit` เข้ากับ `innovation-tip`
- เปิด taxonomy ผ่าน WordPress REST API
- สร้าง/ปรับชื่อ 20 terms ตาม controlled vocabulary และ slug ที่กำหนด
- แสดงคอลัมน์ “ประโยชน์ต่อองค์กร” ในหน้ารายการ Innovation Tips
- เปิด term archive ที่รูปแบบ URL `/organization-benefit/{slug}/`

บัญชีที่ใช้ Application Password ต้องมีสิทธิ์สร้าง `innovation-tip` และ assign/create terms ของ taxonomy นี้

## ตรวจสอบ post type ก่อนใช้งาน

เปิด URL ต่อไปนี้บน WordPress เป้าหมาย:

```text
https://your-site.example/wp-json/wp/v2/types/innovation-tip
```

ต้องไม่ตอบ `rest_no_route` และค่า `slug` ต้องชี้ไปยัง post type ที่ระบบใช้งานจริง หาก internal post type key ไม่ใช่ `innovation-tip` ให้แก้ค่า `OAR_INNOVATION_TIP_POST_TYPE` ในไฟล์ปลั๊กอินก่อน activate ห้ามสร้าง taxonomy ชื่อเดียวกันซ้ำผ่าน Post Type Builder

## ตั้งค่าฝั่งสคริปต์

เพิ่มหรือคงค่าใน `.env`:

```dotenv
WP_API_URL=https://your-site.example/wp-json
WP_USERNAME=innovation-bot
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WP_BENEFIT_TAXONOMY_REST_BASE=organization-benefits
```

`WP_BENEFIT_TAXONOMY_REST_BASE` มีค่าเริ่มต้นเป็น `organization-benefits` จึงละไว้ได้ แต่แนะนำให้ระบุชัดเจนใน production

## วิธีเลือก 3 terms

`fetch-innovation-news-mysql.py` ให้คะแนนจาก keyword ที่พบในชื่อข่าวและบทสรุป โดย keyword ในชื่อข่าวมีน้ำหนักมากกว่า จากนั้นเลือก 3 รายการที่คะแนนสูงสุดแบบไม่ซ้ำกัน

ถ้าพบหมวดที่ตรงเนื้อหาไม่ครบ 3 รายการ ระบบจะเติมจากค่าเริ่มต้นตามลำดับ:

1. การสร้างนวัตกรรมและการเปลี่ยนแปลง
2. การวิจัยและพัฒนาองค์ความรู้
3. การปรับตัวต่อเทรนด์และตลาด

ก่อน publish สคริปต์จะค้นหา term ID ด้วย slug และสร้าง term ที่ขาด หากไม่สามารถยืนยัน ID ที่ไม่ซ้ำกันได้ครบ 3 ค่า ระบบจะหยุดเฉพาะการ sync ข่าวนั้นเข้า WordPress เพื่อไม่ให้เผยแพร่โพสต์ที่ไม่มีหมวด สำหรับโพสต์ซ้ำที่ตรวจพบจากชื่อ ระบบจะอัปเดต taxonomy ให้โพสต์เดิมด้วย

## ตรวจสอบหลังติดตั้ง

1. เปิดรายการ 20 terms:

   ```text
   https://your-site.example/wp-json/wp/v2/organization-benefits?per_page=100
   ```

2. รัน integration smoke test จากโฟลเดอร์ `scripts`:

   ```bash
   python test-integrations.py
   ```

   คำสั่งนี้จะส่งข้อความทดสอบไป Telegram และ LINE ด้วยหากตั้งค่าช่องทางดังกล่าวไว้ จึงควรแจ้งกลุ่มผู้รับหรือปิด channel ที่ไม่ต้องการทดสอบชั่วคราว

3. ทดสอบบน staging ด้วยข่าวหนึ่งรายการ แล้วตรวจ REST response ของโพสต์:

   ```text
   https://your-site.example/wp-json/wp/v2/innovation-tip/{post-id}?_fields=id,title,organization-benefits
   ```

   ค่า `organization-benefits` ต้องมี integer IDs จำนวน 3 ค่าและไม่ซ้ำกัน

4. ตรวจใน WordPress Admin ว่าโพสต์มี “ประโยชน์ต่อองค์กร” 3 รายการ

## ทำให้ผู้อ่านกดดูข่าวตามหมวดได้

การผูก taxonomy ทำให้ WordPress มี term archive แล้ว แต่ธีมหรือ Post Type Builder ยังต้องนำลิงก์มาแสดง ปลั๊กอินมี shortcode ให้ใช้ดังนี้:

- วาง `[innovation_tip_benefits]` ใน single template ของ `innovation-tip` เพื่อแสดง 3 หมวดที่กดได้
- วาง `[innovation_benefit_filter]` บนหน้ารวมข่าว เพื่อแสดงหมวดที่มีข่าวพร้อมจำนวนโพสต์และลิงก์ไป term archive
- วาง `[innovation_tip_search]` บน Page ปกติ เพื่อแสดงแบบฟอร์มเดียวที่ค้นจากคำค้น ประโยชน์ต่อองค์กร และช่วงวันที่เผยแพร่บนเว็บไซต์ พร้อมผลลัพธ์และ pagination ในหน้าเดียวกัน

สามารถตกแต่งผ่าน CSS classes `.innovation-benefits`, `.innovation-benefit` และ `.innovation-benefit-filter` ได้โดยไม่ต้องแก้ปลั๊กอิน

หาก template builder ไม่รองรับ shortcode ให้ใช้ `get_the_term_list()` ใน child theme/template แทน:

```php
<?php
echo get_the_term_list(
    get_the_ID(),
    'organization_benefit',
    '<div class="innovation-benefits">',
    ' · ',
    '</div>'
);
?>
```

ควรตรวจหน้า archive และ pagination บน staging ก่อนนำลิงก์ขึ้นเมนูจริง เพราะรูปแบบการแสดงผลขึ้นกับ theme ที่เว็บไซต์ใช้อยู่

## แบบฟอร์มค้นหาเดียวโดยไม่พึ่ง PTB Search

ปลั๊กอินตั้งแต่เวอร์ชัน 1.1.0 มี shortcode:

```text
[innovation_tip_search]
```

แนวทางที่ปลอดภัยคือสร้าง WordPress Page ใหม่แล้วตั้งสถานะเป็น **Private** เพื่อทดสอบ จากนั้นใส่ Shortcode block ข้างต้น แบบฟอร์มและผลลัพธ์จะอยู่หน้าเดียวกัน และใช้ `WP_Query` แยกจาก main query ของธีม/PTB จึงไม่ต้องสร้าง taxonomy ซ้ำใน PTB และไม่ใช้โมดูล Tags ที่เคยดึง `post_tag` มาปะปน ไม่แนะนำให้ทดสอบผ่าน Draft Preview เพราะ query string สำหรับ preview อาจหมดอายุหรือสูญหายเมื่อส่งแบบฟอร์ม

สามารถกำหนดค่าเพิ่มเติมได้:

```text
[innovation_tip_search posts_per_page="12" hide_empty="1" show_excerpt="1"]
```

| ตัวเลือก | ค่าเริ่มต้น | ความหมาย |
|---|---:|---|
| `posts_per_page` | `12` | จำนวนผลลัพธ์ต่อหน้า สูงสุด 24 |
| `hide_empty` | `1` | แสดงเฉพาะหมวดที่มีโพสต์; ใช้ `0` หากต้องการเห็น controlled terms ทั้ง 20 รายการ |
| `show_excerpt` | `1` | แสดงข้อความย่อของข่าว; ใช้ `0` เพื่อซ่อน |

ตั้งแต่ปลั๊กอินเวอร์ชัน 1.1.4 รูปแบบเริ่มต้นของ shortcode จะกลมกลืนกับรายการ PTB เดิมมากขึ้น ได้แก่ฟอร์มพื้นขาวที่ล็อกตำแหน่งคำค้น ประโยชน์ต่อองค์กร วันที่ และปุ่มไว้ในบรรทัดเดียวกันบนจอใหญ่ ป้องกัน clearfix/pseudo-element ของธีมดันตัวกรองลงบรรทัดใหม่ บรรทัดวันที่เผยแพร่พร้อมชื่อผู้เขียนโดยไม่แสดง avatar ไม่แสดงลิงก์ “อ่านเพิ่มเติม” ซ้ำใต้ผลลัพธ์ และจัด pagination ที่หน้าปัจจุบันเป็นวงกลมสีเขียวไว้กึ่งกลางหน้า โดยยังยุบเป็นสองคอลัมน์และหนึ่งคอลัมน์บน tablet/mobile ตามลำดับ ไม่ต้องเปลี่ยน shortcode เดิม

ข้อควรทราบ:

- ช่องวันที่กรองด้วย `post_date` หรือ **วันที่เผยแพร่บนเว็บไซต์ WordPress** ไม่ใช่วันที่เผยแพร่ของแหล่งข่าวต้นฉบับ
- ตัวกรองประโยชน์ต่อองค์กรใช้ taxonomy `organization_benefit` โดยตรงและรับเฉพาะ 20 slugs ที่กำหนดไว้ จึงไม่ดึง Tags เช่น `COVID-19` มาแสดง
- โพสต์เก่าที่มี `organization-benefits: []` ยังปรากฏเมื่อเลือก “ทั้งหมด” แต่จะไม่ปรากฏเมื่อกรองด้วยหมวด จนกว่าจะทำ backfill taxonomy
- ช่องคำค้นใช้ระบบค้นหามาตรฐานของ WordPress กับชื่อเรื่อง excerpt และ content; ไม่ค้น arbitrary PTB custom-field meta
- ควรวาง shortcode นี้เพียงหนึ่งครั้งต่อ Page และไม่วางใน loop/template ของ `innovation-tip`
- หากใช้ page cache/CDN ต้องตรวจว่าระบบแยก cache ตาม query string `it_*` เพื่อไม่ให้ผลการค้นหาของผู้ใช้หนึ่งถูกนำไปแสดงให้อีกคน

### อัปเดตปลั๊กอินบน Production

เวอร์ชัน 1.2.0 คงฟังก์ชัน taxonomy และหน้า search เดิม พร้อมเพิ่ม authenticated
guarded REST contract สำหรับงาน backfill เท่านั้น การทำงานรายวันจะไม่เรียก
endpoint นี้เอง และ endpoint เขียนต้องผ่าน Application Password, สิทธิ์แก้โพสต์,
สิทธิ์ assign terms และ expected-state checks ครบก่อน

ปลั๊กอินมีไฟล์ในโฟลเดอร์ `includes/` และ `assets/` จึงต้องอัปโหลดหรือ replace
**ทั้งโฟลเดอร์ปลั๊กอิน** ไม่ใช่คัดลอกเฉพาะไฟล์ PHP หลัก:

```text
innovation-tip-benefit-taxonomy/
├── innovation-tip-benefit-taxonomy.php
├── includes/
│   └── frontend-search.php
└── assets/
    └── innovation-tip-search.css
```

การอัปเดตนี้ไม่มี database migration และไม่เปลี่ยน REST payload หรือ cron
รับข่าวเดิม หลังอัปเดตให้ตรวจ endpoint capability แบบ authenticated และทดสอบ
หน้า search เดิมก่อนเสมอ หากต้องย้อนปลั๊กอิน ให้คืนโฟลเดอร์เวอร์ชัน 1.1.4
ที่สำรองไว้ทั้งโฟลเดอร์ การย้อนเวอร์ชันปลั๊กอินจะไม่ลบ taxonomy, terms หรือ
ความสัมพันธ์ที่มีอยู่

## ชุดทดสอบใน repository

รันจาก root ของโครงการ:

```bash
python -m unittest discover -s tests -v
```

ชุดทดสอบตรวจทั้งกติกาเลือก 3 terms, slug 20 รายการ, payload ตอนสร้างโพสต์, การอัปเดตโพสต์ซ้ำ, การหยุด publish เมื่อ resolve term ไม่ครบ และความตรงกันระหว่าง Python กับปลั๊กอิน WordPress
