import { sql, auth } from './_lib.js';

export default async function handler(req, res) {
  if (!auth(req, res)) return;
  try {
    if (req.method === 'GET') {
      const month = String(req.query.month || '');
      if (!/^\d{4}-\d{2}$/.test(month)) return res.status(400).json({ error: 'month ไม่ถูกต้อง' });
      const start = `${month}-01`;
      const rows = await sql`
        SELECT id AS "ID", to_char(date,'DD/MM/YYYY') AS "Date", to_char(date,'YYYY-MM-DD') AS "InputDate",
               item AS "Item", type AS "Type", name AS "Name", amount::float AS "Amount", description AS "Description"
        FROM expenses
        WHERE date >= ${start}::date AND date < (${start}::date + interval '1 month')
        ORDER BY date, id`;
      return res.json(rows);
    }

    const b = req.body || {};
    if (req.method === 'POST') {
      await sql`INSERT INTO expenses (date,item,type,name,amount,description)
                VALUES (${b.Date}::date, ${b.Item}, ${b.Type || ''}, ${b.Name || '-'}, ${Number(b.Amount) || 0}, ${b.Description || ''})`;
      return res.json({ ok: true });
    }
    if (req.method === 'PUT') {
      await sql`UPDATE expenses SET date=${b.Date}::date, item=${b.Item}, type=${b.Type || ''},
                name=${b.Name || '-'}, amount=${Number(b.Amount) || 0}, description=${b.Description || ''}
                WHERE id=${Number(b.ID)}`;
      return res.json({ ok: true });
    }
    if (req.method === 'DELETE') {
      const r = await sql`DELETE FROM expenses WHERE id=${Number(req.query.id)} RETURNING id`;
      if (!r.length) return res.status(404).json({ error: 'ไม่พบรายการ ID: ' + req.query.id });
      return res.json({ ok: true });
    }
    res.status(405).json({ error: 'Method not allowed' });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message });
  }
}
