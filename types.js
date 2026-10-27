import { sql, auth } from './_lib.js';

export default async function handler(req, res) {
  if (!auth(req, res)) return;
  try {
    const rows = await sql`SELECT name FROM expense_types ORDER BY id`;
    res.json(rows.map(r => r.name));
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
