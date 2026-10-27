import { neon } from '@neondatabase/serverless';
export const sql = neon(process.env.DATABASE_URL);

// ป้องกันคนนอกเข้าแก้ข้อมูล: ตรวจรหัสผ่านจาก header
export function auth(req, res) {
  const pw = process.env.APP_PASSWORD;
  if (pw && req.headers['x-app-password'] !== pw) {
    res.status(401).json({ error: 'รหัสผ่านไม่ถูกต้อง' });
    return false;
  }
  return true;
}
