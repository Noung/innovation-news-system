# Quick Deploy (retired)

ขั้นตอนเดิมถูกยกเลิก เพราะคัดลอก secret, ปิด TLS verification และเขียนทับ crontab ทั้งชุด

ใช้ staged workflow ใน [Phase 0 rollout](../docs/phase0-rollout.md) เท่านั้น โดยเริ่มจาก `deploy-to-prod.sh --dry-run` และต้องมีการอนุมัติก่อน `--apply`
