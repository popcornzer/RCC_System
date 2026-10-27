import { sql, auth } from './_lib.js';
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export default async function handler(req, res) {
  if (!auth(req, res)) return;
  try {
    const year = Number(req.query.year) || new Date().getFullYear();
    const rows = await sql`
      SELECT EXTRACT(MONTH FROM date)::int AS m, COALESCE(NULLIF(name,''),'อื่นๆ') AS name, SUM(amount)::float AS total
      FROM expenses WHERE EXTRACT(YEAR FROM date) = ${year} GROUP BY 1,2`;
    const out = MONTHS.map(month => ({ month, total: 0, byName: {} }));
    rows.forEach(r => {
      const o = out[r.m - 1];
      o.total += r.total;
      o.byName[r.name] = (o.byName[r.name] || 0) + r.total;
    });
    res.json(out);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}
