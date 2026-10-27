CREATE TABLE IF NOT EXISTS expenses (
  id          SERIAL PRIMARY KEY,
  date        DATE NOT NULL,
  item        TEXT NOT NULL,
  type        TEXT DEFAULT '',
  name        TEXT DEFAULT '-',
  amount      NUMERIC(12,2) NOT NULL DEFAULT 0,
  description TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);

CREATE TABLE IF NOT EXISTS expense_types (
  id   SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);
-- แก้เป็นค่าเดียวกับคอลัมน์ B ของชีต Dropdown เดิม
INSERT INTO expense_types (name) VALUES ('เงินสด'), ('บัตรเครดิต'), ('โอน')
ON CONFLICT DO NOTHING;
