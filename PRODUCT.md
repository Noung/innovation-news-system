# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- เจ้าหน้าที่ภายในองค์กร (ทีมสื่อสาร/นวัตกรรม) ที่ตรวจสอบข่าวที่ระบบดึงมาและอนุมัติก่อนเผยแพร่
- ผู้ดูแลระบบ (Dev/IT) ที่เฝ้าดู sources, fetch logs และสถานะ health ของระบบ

## Product Purpose

Admin UI (Innovation News Management System) ควบคุมและติดตามระบบที่ดึง กรอง จัดเก็บ และเผยแพร่ข่าวสารด้านการวิจัยและนวัตกรรมโดยอัตโนมัติ ความสำเร็จคือเจ้าหน้าที่ตรวจสอบ/อนุมัติข่าวได้เร็วและถูกต้อง และผู้ดูแลระบบเห็นสถานะ sources/fetch logs/integrations ได้ชัดเจนโดยไม่ต้องเข้าฐานข้อมูลตรง

## Positioning

ดึง กรอง จัดเก็บ และเผยแพร่ข่าวนวัตกรรมไปหลายช่องทางพร้อมกันโดยอัตโนมัติ (WordPress, Telegram, LINE) จากจุดจัดการเดียว ต่างจากการเผยแพร่ทีละช่องทางด้วยมือ

## Operating Context

- ใช้งานผ่าน Docker Compose ในสภาพแวดล้อม local development เท่านั้น ณ ตอนนี้ (ไม่แตะ PROD)
- fetch jobs รันผ่าน OS cron; Admin API/UI รันผ่าน PM2 บน PROD
- ข่าวที่ดึงมาต้องผ่านการตรวจสอบ/อนุมัติจากเจ้าหน้าที่ก่อนเผยแพร่จริงไปยัง WordPress/Telegram/LINE
- WordPress production เป็นระบบเดิม PHP 5.6 / WordPress 6.2.9 แยกเครื่อง

## Capabilities and Constraints

- UI ต้องเป็นภาษาไทยทั้งหมด และใช้ฟอนต์ Noto Sans Thai
- Tailwind CSS ที่ compile แบบ pinned dependency ไว้แล้ว (ไม่ใช่ CDN)
- Backend เป็น Node.js Admin API + MySQL; หน้าเว็บปัจจุบันเป็น single-page (`fetch-innovation-news/public/index.html`)
- การพัฒนา/ทดสอบ UI ทั้งหมดต้องทำใน Docker local stack ที่ใช้ synthetic/sanitized data เท่านั้น ห้ามชี้ไป PROD database หรือ credentials

## Brand Commitments

ยังไม่มี brand guideline อย่างเป็นทางการนอกจากภาษาไทยและฟอนต์ Noto Sans Thai ที่ต้องคงไว้

## Evidence on Hand

- โค้ด UI ปัจจุบันอยู่ที่ `fetch-innovation-news/public/index.html` และ `fetch-innovation-news/public/admin.css`
- เอกสารระบบที่ `README.md`, `PROJECT_HANDOFF.md`, `docs/local-development.md`
- ยังไม่มี testimonial, โลโก้ลูกค้า หรือ benchmark ต้องไม่สร้างขึ้นมาเอง

## Product Principles

- ความถูกต้องและความน่าเชื่อถือของข่าวมาก่อนความสวยงาม เพราะเป็นเครื่องมือ operate ที่ใช้ตัดสินใจอนุมัติเผยแพร่
- สื่อสารสถานะ (source, fetch log, integration) ให้ชัดเจนและตรวจสอบได้ทันทีโดยไม่ต้องเดา
- คงภาษาไทยและฟอนต์ Noto Sans Thai ไว้เสมอ ไม่แทนที่ด้วยค่า default ของ AI
- ทุกการเปลี่ยนแปลง UI ต้องทดสอบใน Docker local ก่อน ไม่กระทบ PROD

## Accessibility & Inclusion

ยังไม่มีมาตรฐานหรือความต้องการเฉพาะที่ยืนยันจากผู้ใช้ นอกเหนือจากภาษาไทยเป็นภาษาหลักของ UI
