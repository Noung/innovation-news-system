# Phase 0: Runtime Safety Baseline

เอกสารนี้แยก “โค้ดที่เตรียมใน local replica” ออกจาก “การเปลี่ยน PROD” อย่างชัดเจน การทำงานใน local ไม่ส่งข่าว ไม่แก้ฐานข้อมูล PROD และไม่แก้ crontab/PM2 บนเครื่องจริง

## สถานะปัจจุบัน

ส่วนป้องกันหลักใน local พร้อมตรวจทานแล้ว แต่ **ยังห้าม promote ไป live** จนกว่าจะผ่านรายการ `PROD acceptance gates` ด้านล่าง โดยเฉพาะการ rotate credential, ย้าย News API key ออกจาก URL และจัดทำขั้น promote/rollback ที่อนุมัติแล้ว

สิ่งที่วางไว้ใน local:

1. OS cron เป็น scheduler เจ้าของเดียว; PM2 เหลือเฉพาะ Admin API
2. ทุก entry point ของ fetch ใช้ local file lock และ MySQL advisory lock ครอบคลุมทั้งรอบ
3. เลือก environment เพียงไฟล์เดียวตามลำดับ explicit path → root `.env` → legacy `scripts/.env`; ค่าจากไฟล์ที่เลือกเป็น canonical และไม่ผสมกับไฟล์อื่น
4. WordPress/LINE ยอมรับเฉพาะ HTTPS และไม่อนุญาตปิด certificate verification; private CA ใช้ PEM bundle
5. source URL ยอมรับเฉพาะ HTTPS และห้าม userinfo/credential-like query parameter
6. News API key รองรับผ่าน header จาก root `.env` โดยไม่บันทึกลง `news_sources.source_url`
7. Admin bind ที่ loopback โดยค่าเริ่มต้น และรองรับ `0.0.0.0` แบบ explicit สำหรับ PROD เดิมที่เข้าผ่าน LAN โดยตรง พร้อมจำกัด trusted proxy, CORS, login rate, password/session minimum, CSP และใช้ CSS ที่ build/self-host เอง
8. deploy helper เป็น dry-run โดยค่าเริ่มต้น; `--apply` สร้าง patch bundle พร้อม checksum ใน `releases/phase0-*` เท่านั้น ไม่แตะ live
9. feature gates ของ subscription/email ปิดทั้งหมด

## ค่าที่ต้องมีใน canonical root `.env`

อ้างอิงชื่อ key จาก [`.env.example`](../.env.example) โดยห้ามพิมพ์ค่าจริงลง terminal, ticket หรือเอกสาร:

```dotenv
WP_VERIFY_TLS=1
WP_CA_BUNDLE=
LINE_VERIFY_TLS=1
LINE_CA_BUNDLE=
INNOVATION_NEWS_FETCH_LOCK_NAME=innovation-news:innovation_news:fetch
INNOVATION_NEWS_FETCH_LOCK_TIMEOUT_SECONDS=0
INNOVATION_NEWS_FETCH_FILE_LOCK=/home/kittisak/.openclaw/workspace/cache/innovation-news-fetch.lock
INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI=
INNOVATION_NEWS_SOURCE_API_KEY_HEADER_NEWSAPI=X-Api-Key
ADMIN_BIND_HOST=127.0.0.1
ADMIN_TRUST_PROXY=loopback
ENABLE_SUBSCRIPTION_API=0
ENABLE_EMAIL_WORKER=0
EMAIL_SEND_MODE=disabled
```

หากองค์กรใช้ private CA ให้กำหนด `WP_CA_BUNDLE`, `LINE_CA_BUNDLE` หรือ `KSSTAT_CA_BUNDLE` เป็น path ของ PEM ที่อ่านได้ ระบบไม่มีโหมดปิด TLS verification

## PROD acceptance gates (ต้องผ่านก่อน staging/promotion)

1. Rotate/revoke credential เดิมทั้งหมด: Telegram token, WordPress Application Password, LINE key, DB password, News API key, Admin passwords และ Admin session secret โดยไม่ใช้ค่าซ้ำเดิม
2. Admin password แต่ละบัญชียาวอย่างน้อย 16 ตัวอักษร, ไม่ใช่ placeholder; session secret อย่างน้อย 32 ตัวอักษร จากนั้นรัน config check ซึ่งรายงานเฉพาะสถานะ ไม่แสดงค่า:

   ```bash
   INNOVATION_NEWS_ENV_FILE=/home/kittisak/.openclaw/workspace/.env \
     node fetch-innovation-news/api/server.js --config-check
   ```

3. ย้าย News API key ออกจาก `news_sources.source_url` ไปไว้ที่ `INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI` และเก็บ URL ที่ไม่มี credential เท่านั้น ตรวจสถานะโดยไม่แสดง URL:

   ```sql
   SELECT id, slug,
          CASE
            WHEN source_url REGEXP '[?&](api[_-]?key|token|password|secret|auth)='
              OR source_url REGEXP '^https://[^/]+@'
            THEN 'BLOCKED' ELSE 'OK'
          END AS credential_state,
          CASE WHEN source_url LIKE 'https://%' THEN 'HTTPS' ELSE 'BLOCKED' END AS transport_state
   FROM news_sources
   WHERE is_active = 1;
   ```

   ค่า `credential_state` และ `transport_state` ต้องเป็น `OK`/`HTTPS` ทุกแถว การแก้ URL จริงต้องผ่าน change record และทดสอบ source ใหม่; ห้ามคัดลอก URL เดิมที่มี key ลง log

4. วาง Admin API หลัง HTTPS reverse proxy บนเครื่องเดียวกัน โดย upstream ชี้ loopback; ห้ามเปิด port `3001` ตรงสู่เครือข่าย
5. ตรวจ dependency advisory จาก registry ที่องค์กรอนุมัติ และทบทวนรายการก่อนแก้ version ห้ามใช้ `npm audit fix` อัตโนมัติบน PROD
6. กู้หรือจัดทำ signed schema baseline เพราะ local replica ไม่มี migration history เดิม ห้ามเริ่ม subscription schema ก่อน gate นี้
7. จัดทำและ peer-review ขั้น promote/rollback สำหรับ live files ก่อนทำจริง `deploy-to-prod.sh` ทำเพียง staging และ **ไม่ถือเป็นการ deploy live**
8. Credential ของ News API ที่เคยอยู่ใน tracked SQL/Git history ต้องถูก revoke และ purge history ด้วยกระบวนการที่ผู้ดูแล repository อนุมัติก่อน mirror/push repository นี้

## Read-only preflight บน PROD

คำสั่งต่อไปนี้ไม่แสดง secret value และไม่สร้างข่าว:

```bash
cd /home/kittisak/.openclaw/workspace

date
timedatectl 2>/dev/null || true

python3 -m py_compile \
  scripts/fetch-innovation-news-mysql.py \
  scripts/wordpress_integration.py \
  scripts/line_integration.py

node --check fetch-innovation-news/api/server.js

umask 077
cron_snapshot=$(mktemp)
crontab -l > "$cron_snapshot"
awk '/^[[:space:]]*#/ { next } NF { count++ } END { print "active_cron_entries=" count + 0 }' "$cron_snapshot"
cksum < "$cron_snapshot"
rm -f "$cron_snapshot"

pm2 status
```

ตรวจเฉพาะชื่อ key ของ env สองไฟล์ ไม่แสดงค่า:

```bash
sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env | sort -u
if [ -f scripts/.env ]; then
  sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' scripts/.env | sort -u
fi
```

ห้ามเก็บ raw `pm2 jlist`, raw crontab หรือ `.env` ไว้ใน workspace backup เพราะอาจมี credential หากจำเป็นต้องสำรอง secret ให้ใช้พื้นที่เข้ารหัส/ระบบจัดการ secret ที่องค์กรอนุมัติและกำหนดวันลบ

## Local verification ก่อนสร้าง patch bundle

```bash
cd /home/kittisak/.openclaw/workspace
python3 -m unittest discover -s tests -v
python3 scripts/audit-secret-sprawl.py --workspace . --env-file .env
fetch-innovation-news/deploy-to-prod.sh --dry-run
```

Secret audit จะยังรายงาน `LEGACY_ENV_FILE` ตราบใดที่ `scripts/.env` ยังมี credential copy อยู่ ต้องเหลือศูนย์ findings หลัง canary/rollback window และก่อนถือว่า Phase 0 บน PROD เสร็จสมบูรณ์

## Staging เท่านั้น

เมื่อ gates ได้รับอนุมัติแล้ว:

1. รัน `fetch-innovation-news/deploy-to-prod.sh --dry-run` ซึ่งไม่มี network call และไม่เขียนไฟล์
2. รัน `--apply` เพื่ออัปโหลด patch bundle เข้า `releases/phase0-*`
3. helper จะตรวจ SHA-256 จาก manifest ต้นทาง, Python/Node/shell syntax, Phase 0 unit tests และ Admin config โดยไม่ restart service
4. หากขั้นใดไม่ผ่าน ให้หยุดที่ release directory นั้น; live system ยังไม่เปลี่ยน จึงไม่ต้อง rollback
5. ห้ามคัดลอก release ไป live จนกว่าจะมี promote/rollback runbook ที่ peer-review และ maintenance window ได้รับอนุมัติ

## Canary acceptance หลัง promotion ที่ได้รับอนุมัติในอนาคต

- มี fetch cycle เพียงหนึ่งรอบใน log และการชน lock จบด้วย exit `75`
- ไม่มี `InsecureRequestWarning` และไม่มี credential ใน URL/error/audit log
- WordPress post มี taxonomy ครบ 3 term เหมือนเดิม
- Telegram/WordPress/LINE มีสถานะตาม flow เดิม
- source index ขยับหนึ่งครั้ง
- Admin API login ผ่าน HTTPS reverse proxy ได้; port backend ยัง bind loopback
- PM2 ไม่มี `innovation-news-fetcher` และ `it24hrs-news-fetcher`
- crontab มี managed fetch entry เพียงหนึ่งรายการ

หลัง canary ผ่านและ rollback window สิ้นสุด ให้ย้าย/ทำลาย `scripts/.env` ตามนโยบาย secret ขององค์กร เหลือ root `.env` เพียงชุดเดียว แล้วรัน secret audit จนได้ `PASS`

ห้ามรัน Python fetcher ด้วยมือถ้ายังไม่ต้องการสร้างข่าว ให้รอรอบ 09:00 เป็น canary เหมือนกระบวนการเดิม

## Phase 1 ยังปิดอยู่

```dotenv
ENABLE_SUBSCRIPTION_API=0
ENABLE_EMAIL_WORKER=0
EMAIL_SEND_MODE=disabled
```

Phase 0 ไม่สร้าง subscriber table, ไม่เปิด API รับสมัคร และไม่ส่งอีเมล
