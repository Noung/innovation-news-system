# 🐛 แก้ปัญหา "Cannot GET /"

## สาเหตุ

Server รันจาก `api/` folder แต่ static files อยู่ที่ `../public/` (parent directory) ทำให้ Express ไม่พบไฟล์ `index.html`

## วิธีแก้

### 1. ใช้ `path.join()` สำหรับ static files
```javascript
const path = require('path');

app.use(express.static(path.join(__dirname, '../public')));
```

### 2. เพิ่ม Root Route สำหรับ index.html
```javascript
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '../public/index.html'));
});
```

### 3. แก้ start.sh ให้รันจาก directory ที่ถูก
```bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}/api"
```

## ไฟล์ที่แก้

- ✅ `api/server.js` - เพิ่ม path module + แก้ static path
- ✅ `api/server.js` - เพิ่ม root route สำหรับ index.html
- ✅ `start.sh` - แก้ working directory

## ทดสอบ

```bash
./start.sh
# Server should start and serve index.html at:
# http://localhost:3001
```

การเข้าจากเครื่องอื่นต้องผ่าน HTTPS reverse proxy ที่อนุมัติแล้ว ห้ามเปิด port `3001` โดยตรงต่อเครือข่าย

## หมายเตือน

⚠️ **อย่าเรียก `app.use(express.static('public'))`** เมื่อ server รันจาก `api/` folder
⚠️ **ต้องใช้ absolute path หรือ path.join()** ให้ถูกต้อง
