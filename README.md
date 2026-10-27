# RCC 2026 Tracker → Vercel + Neon

## โครงสร้าง
```
rcc-tracker/
├─ api/ (_lib.js, records.js, summary.js, types.js)   ← backend (Vercel Functions)
├─ public/ (index.html, gas-shim.js)                  ← frontend
├─ schema.sql
└─ package.json
```

## 1) เตรียมฐานข้อมูลที่ Neon
1. สมัคร/ล็อกอิน https://neon.tech → Create project (เลือก region ใกล้ไทย เช่น Singapore)
2. เปิด **SQL Editor** → วางเนื้อหา `schema.sql` → Run
   (แก้รายการใน `expense_types` ให้ตรงกับชีต Dropdown เดิม)
3. หน้า Dashboard กด **Connect** → คัดลอก connection string (`postgresql://...?sslmode=require`)

## 2) เตรียม frontend
1. คัดลอก `index.html` เดิมไปไว้ที่ `public/index.html`
2. เพิ่มบรรทัดนี้ **ก่อน** แท็ก `<script>` หลักของหน้า:
   `<script src="/gas-shim.js"></script>`
3. (ไม่บังคับ) ให้เปิดมาที่เดือนปัจจุบัน ใน `window.onload` หลังบรรทัด `selector.innerHTML = ...` เพิ่ม:
   `selector.value = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][new Date().getMonth()];`

## 3) Deploy ขึ้น Vercel
1. สร้าง repo บน GitHub แล้ว push โฟลเดอร์นี้ขึ้นไป
2. https://vercel.com → Add New → Project → เลือก repo
   - Framework Preset: **Other**, ไม่ต้องใส่ Build Command
3. ใน Environment Variables ใส่
   - `DATABASE_URL` = connection string จาก Neon
   - `APP_PASSWORD` = รหัสผ่านที่ตั้งเอง (กันคนนอกเข้ามาแก้ข้อมูลการเงิน)
4. กด Deploy จะได้ URL แบบ `https://ชื่อโปรเจกต์.vercel.app` ครั้งแรกที่เปิดจะมีช่องถามรหัสผ่าน

ทดสอบบนเครื่องก่อนได้: `npm i -g vercel && vercel dev` (ใส่ env ใน `.env.local`)

## 4) ย้ายข้อมูลเก่าจาก Google Sheet
รันฟังก์ชันนี้ใน Apps Script เดิม แล้วคัดลอก SQL จาก Logs ไปรันใน Neon SQL Editor
(ถ้าข้อมูลเยอะจน Logs ตัด ให้รันทีละไม่กี่ชีต)
```js
function exportSQL() {
  const q = v => "'" + String(v || '').replace(/'/g, "''") + "'";
  const out = [];
  SpreadsheetApp.getActiveSpreadsheet().getSheets().forEach(s => {
    if (['Dropdown', 'ค่าใช้จ่าย'].includes(s.getName())) return;
    s.getDataRange().getValues().slice(1).forEach(r => {
      if (!r[2] || r[0] === '' || !(r[1] instanceof Date)) return;
      const d = Utilities.formatDate(r[1], 'GMT+7', 'yyyy-MM-dd');
      out.push(`(${q(d)},${q(r[2])},${q(r[3])},${q(r[4])},${parseFloat(r[5]) || 0},${q(r[6])})`);
    });
  });
  Logger.log('INSERT INTO expenses (date,item,type,name,amount,description) VALUES\n' + out.join(',\n') + ';');
}
```

## ข้อสังเกต
- เดิมแต่ละเดือนเป็นชีตแยก ตอนนี้เป็นตารางเดียว กรองตามวันที่ ปีกำหนดที่ `YEAR` ใน `gas-shim.js`
- เงินเดือน (ฐานเงินเดือน) ยังเก็บใน localStorage ของเบราว์เซอร์เหมือนเดิม ถ้าอยากให้ซิงค์ข้ามเครื่องต้องเพิ่มตาราง settings
- Neon free tier จะ suspend เมื่อไม่ได้ใช้งาน การเปิดครั้งแรกอาจช้า 1–2 วินาที
