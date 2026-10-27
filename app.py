import os
from datetime import date

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

from carry import plan_carry, prev_period

st.set_page_config(page_title="RCC Tracker", page_icon="⚡", layout="wide")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PEOPLE = ["", "Pop", "Tim", "Mom", "k-bank", "EXAT"]
dash = lambda x: x if x else "-"


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key)


def run(query, params=None, fetch=False, many=False):
    conn = psycopg2.connect(secret("DATABASE_URL"))
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if many:
                cur.executemany(query, params)
                return None
            cur.execute(query, params)
            return cur.fetchall() if fetch else None
    finally:
        conn.close()


def plabel(p):
    try:
        y, m = p.split("-")
        return f"{MONTHS[int(m) - 1]} {y}"
    except Exception:
        return p


def has(x):
    return x is not None and not pd.isna(x)


def iv(x):
    return int(x) if has(x) else 0


def fmt_d(d):
    return d.strftime("%d/%m") if has(d) else "-"


def inst_txt(no, tot):
    if not has(no):
        return ""
    return f"{int(no)}/{int(tot)}" if has(tot) else f"#{int(no)}"


def blank(s):
    return s.fillna("").astype(str).str.strip().isin(["", "-"])


# ---------- รหัสผ่าน ----------
pw = secret("APP_PASSWORD")
if pw and not st.session_state.get("ok"):
    st.title("⚡ RCC Tracker")
    x = st.text_input("รหัสผ่าน", type="password")
    if x:
        if x == pw:
            st.session_state["ok"] = True
            st.rerun()
        else:
            st.error("รหัสผ่านไม่ถูกต้อง")
    st.stop()

run("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

if msg := st.session_state.pop("msg", None):
    st.success(msg)

# ---------- Sidebar ----------
st.sidebar.title("⚡ RCC Tracker")
db_periods = {x["period"] for x in run("SELECT DISTINCT period FROM expenses", fetch=True)}
years = sorted({int(p[:4]) for p in db_periods if p[:4].isdigit()} | {date.today().year, date.today().year + 1})
year = st.sidebar.selectbox("เลือกปี", years, index=years.index(date.today().year))
periods_y = [f"{year}-{m:02d}" for m in range(1, 13)]
all_periods = sorted({f"{y}-{m:02d}" for y in years for m in range(1, 13)} | db_periods)
today_p = date.today().strftime("%Y-%m")
period = st.sidebar.selectbox(
    "เลือกงวด", periods_y, format_func=plabel, key=f"period_{year}",
    index=periods_y.index(today_p) if today_p in periods_y else 0)

# ---------- ฐานเงินเดือนแยกรายงวด (ล็อก) ----------
run("CREATE TABLE IF NOT EXISTS period_salary (period TEXT PRIMARY KEY, salary NUMERIC NOT NULL)")
exact = run("SELECT salary::float AS s FROM period_salary WHERE period=%s", (period,), fetch=True)
if exact:
    salary, saved = exact[0]["s"], True
else:   # งวดที่ยังไม่เคยตั้งค่า: ใช้ค่าของงวดก่อนหน้าล่าสุดไปพลาง (ยังไม่บันทึก)
    fb = run("SELECT salary::float AS s FROM period_salary WHERE period < %s ORDER BY period DESC LIMIT 1",
             (period,), fetch=True)
    legacy = run("SELECT value FROM settings WHERE key='salary'", fetch=True)
    salary = fb[0]["s"] if fb else (float(legacy[0]["value"]) if legacy else 0.0)
    saved = False

st.sidebar.markdown(f"**ฐานเงินเดือน {plabel(period)}**")
if saved:
    st.sidebar.caption(f"🔒 ล็อกแล้ว ฿{salary:,.0f} (แก้งวดอื่นไม่กระทบงวดนี้)")
    editing = st.sidebar.checkbox("🔓 ปลดล็อกเพื่อแก้ไข", key=f"unlock_{period}")
else:
    st.sidebar.caption(f"ยังไม่ได้ตั้งค่า ใช้ค่าของงวดก่อนหน้า ฿{salary:,.0f}")
    editing = True
if editing:
    new_salary = st.sidebar.number_input("ฐานเงินเดือน (฿)", min_value=0.0, value=float(salary),
                                         step=100.0, key=f"sal_{period}")
    if st.sidebar.button("🔒 บันทึกและล็อก", key=f"save_sal_{period}"):
        run("INSERT INTO period_salary (period, salary) VALUES (%s,%s) "
            "ON CONFLICT (period) DO UPDATE SET salary=EXCLUDED.salary", (period, new_salary))
        st.session_state.pop(f"unlock_{period}", None)
        st.session_state["msg"] = f"ล็อกฐานเงินเดือน {plabel(period)} = ฿{new_salary:,.0f} แล้ว"
        st.rerun()

st.sidebar.divider()
prev_p = prev_period(period)
if st.sidebar.button(f"📥 ยกรายการต่อเนื่องจาก {plabel(prev_p)}",
                     help="ยกรายการประจำ + ผ่อน/เก็บต่อเนื่อง (งวดที่ +1, ผ่อนครบแล้วไม่ยก, กดซ้ำไม่ซ้ำซ้อน)"):
    src = run("SELECT * FROM expenses WHERE period=%s AND (recurring OR inst_no IS NOT NULL) ORDER BY id",
              (prev_p,), fetch=True)
    have = [(x["item"], x["type"], x["name"]) for x in
            run("SELECT item,type,name FROM expenses WHERE period=%s", (period,), fetch=True)]
    new = plan_carry(src, have)
    if new:
        run("INSERT INTO expenses (period,date,item,type,name,amount,description,inst_no,inst_total,recurring) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(period, n["date"], n["item"], n["type"], n["name"], n["amount"], n["description"],
              n["inst_no"], n["inst_total"], n["recurring"]) for n in new], many=True)
    st.session_state["msg"] = f"ยกมา {len(new)} รายการจาก {plabel(prev_p)} (ข้ามรายการที่มีอยู่แล้วและที่ผ่อนครบ)"
    st.rerun()

types = [""] + [t["name"] for t in run("SELECT name FROM expense_types ORDER BY id", fetch=True)]

# ---------- โหลดข้อมูลของงวดที่เลือก ----------
rows = run(
    """SELECT id, period, date, item, type, name, amount::float AS amount, description,
              inst_no, inst_total, recurring
       FROM expenses WHERE period = %s ORDER BY date NULLS FIRST, id""", (period,), fetch=True)
df = pd.DataFrame(rows, columns=["id", "period", "date", "item", "type", "name", "amount",
                                 "description", "inst_no", "inst_total", "recurring"])

tab1, tab2, tab3 = st.tabs(["📋 รายการ", "✏️ เพิ่ม / แก้ไข / ลบ", "📊 ภาพรวมทั้งปี"])

# ---------- Tab 1 ----------
with tab1:
    # บิลแบ่งหลายคน: แถวยอดรวมมีแต่บัตร (ไม่มีชื่อ) แถวแบ่งมีแต่ชื่อ (ไม่มีบัตร) จึงรวมแยกกัน
    by_card = df[~blank(df["type"])]
    by_person = df[~blank(df["name"])]
    pop = df.loc[df["name"] == "Pop", "amount"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ยอดรวมทุกบัตร", f"฿{by_card['amount'].sum():,.2f}")
    c2.metric("ยอดรวมทุกคน", f"฿{by_person['amount'].sum():,.2f}")
    c3.metric("ยอดเรียกเก็บ Pop", f"฿{pop:,.2f}")
    c4.metric("เงินเดือนคงเหลือ", f"฿{salary - pop:,.2f}")

    q = st.text_input("🔍 ค้นหา", "")
    view = df
    if q:
        mask = df[["item", "type", "name", "description"]].fillna("").apply(
            lambda col: col.astype(str).str.contains(q, case=False)).any(axis=1)
        view = df[mask]
    view = view.copy()
    view["date"] = pd.to_datetime(view["date"])
    view["ผ่อน"] = [inst_txt(a, b) for a, b in zip(view["inst_no"], view["inst_total"])]
    st.dataframe(
        view[["id", "date", "item", "type", "name", "amount", "ผ่อน", "recurring", "description"]],
        hide_index=True, use_container_width=True,
        column_config={
            "id": "ID", "date": st.column_config.DateColumn("วันที่", format="DD/MM/YYYY"),
            "item": "รายการ", "type": "บัตร/ประเภท", "name": "ผู้จ่าย",
            "amount": st.column_config.NumberColumn("จำนวนเงิน", format="฿%.2f"),
            "recurring": st.column_config.CheckboxColumn("ประจำ"), "description": "หมายเหตุ"})

    a, b = st.columns(2)
    a.subheader("สรุปตามบัตร")
    a.dataframe(by_card.groupby("type")["amount"].sum().rename("รวม"), use_container_width=True)
    b.subheader("ยอดแยกรายบุคคล")
    b.dataframe(by_person.groupby("name")["amount"].sum().rename("รวม"), use_container_width=True)

# ---------- Tab 2 ----------
with tab2:
    mode = st.radio("เลือกการทำงาน", ["เพิ่มรายการ", "แก้ไข", "ลบ"], horizontal=True)
    rec = None
    if mode != "เพิ่มรายการ":
        if df.empty:
            st.info("งวดนี้ยังไม่มีรายการ")
        else:
            labels = {x.id: f"#{x.id}  {fmt_d(x.date)}  {x.item}  {dash(x.name)}  ฿{x.amount:,.2f}"
                      for x in df.itertuples()}
            pick = st.selectbox("เลือกรายการ", list(labels), format_func=labels.get)
            rec = df[df["id"] == pick].iloc[0]

    if mode == "ลบ" and rec is not None:
        st.warning(f"ลบ: {rec['item']} ฿{rec['amount']:,.2f} (กู้คืนไม่ได้)")
        if st.button("ยืนยันลบ", type="primary"):
            run("DELETE FROM expenses WHERE id=%s", (int(rec["id"]),))
            st.session_state["msg"] = "ลบรายการสำเร็จ"
            st.rerun()

    elif mode == "เพิ่มรายการ" or rec is not None:
        with st.form("record_form"):
            c0, c00, c01 = st.columns([2, 2, 1])
            d = c0.date_input("วันที่จ่ายจริง", rec["date"] if rec is not None and has(rec["date"]) else date.today())
            no_date = c01.checkbox("ไม่ระบุวันที่", value=rec is not None and not has(rec["date"]))
            p_default = rec["period"] if rec is not None and rec["period"] in all_periods else period
            per = c00.selectbox("งวดตัดยอด", all_periods, index=all_periods.index(p_default), format_func=plabel)
            amount = st.number_input("จำนวนเงิน (฿)", min_value=0.0, step=1.0, format="%.2f",
                                     value=float(rec["amount"]) if rec is not None else 0.0)
            item = st.text_input("รายการ", rec["item"] if rec is not None else "")
            c1, c2 = st.columns(2)
            t_idx = types.index(rec["type"]) if rec is not None and rec["type"] in types else 0
            n_idx = PEOPLE.index(rec["name"]) if rec is not None and rec["name"] in PEOPLE else 0
            typ = c1.selectbox("บัตร/ประเภท (เว้นว่างได้ เช่น แถวแบ่งคน)", types, index=t_idx, format_func=dash)
            name = c2.selectbox("ผู้รับผิดชอบ (เว้นว่างได้ เช่น แถวยอดรวมบัตร)", PEOPLE, index=n_idx, format_func=dash)
            i1, i2, i3 = st.columns(3)
            inst_no = i1.number_input("ผ่อน/เก็บ งวดที่ (0 = ไม่มี)", 0, 999, iv(rec["inst_no"]) if rec is not None else 0)
            inst_total = i2.number_input("จากทั้งหมด (0 = ไม่กำหนด)", 0, 999, iv(rec["inst_total"]) if rec is not None else 0)
            recurring = i3.checkbox("รายการประจำทุกงวด", value=bool(rec["recurring"]) if rec is not None else False)
            desc = st.text_area("หมายเหตุ", rec["description"] if rec is not None and rec["description"] else "")
            if st.form_submit_button("บันทึกข้อมูล", type="primary"):
                if not item.strip() or amount <= 0:
                    st.error("กรุณากรอกรายการและจำนวนเงิน")
                elif inst_total and inst_no > inst_total:
                    st.error("งวดที่ต้องไม่มากกว่าจำนวนงวดทั้งหมด")
                else:
                    vals = (per, None if no_date else d, item.strip(), typ, name, amount, desc.strip(),
                            inst_no or None, inst_total or None, recurring)
                    if rec is None:
                        run("INSERT INTO expenses (period,date,item,type,name,amount,description,"
                            "inst_no,inst_total,recurring) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", vals)
                    else:
                        run("UPDATE expenses SET period=%s,date=%s,item=%s,type=%s,name=%s,amount=%s,"
                            "description=%s,inst_no=%s,inst_total=%s,recurring=%s WHERE id=%s",
                            vals + (int(rec["id"]),))
                    st.session_state["msg"] = "บันทึกสำเร็จ ✓"
                    st.rerun()

# ---------- Tab 3 ----------
with tab3:
    by = st.radio("สรุปตาม", ["ผู้จ่าย", "บัตร"], horizontal=True)
    col = "name" if by == "ผู้จ่าย" else "type"          # whitelist เท่านั้น
    rows = run(
        f"""SELECT period, {col} AS grp, SUM(amount)::float AS total
            FROM expenses WHERE period LIKE %s AND {col} NOT IN ('', '-') GROUP BY 1,2""",
        (f"{year}-%",), fetch=True)
    s = pd.DataFrame(rows, columns=["period", "grp", "total"])
    if s.empty:
        st.info("ยังไม่มีข้อมูลของปีนี้")
    else:
        pivot = s.pivot_table(index="period", columns="grp", values="total", aggfunc="sum", fill_value=0)
        pivot = pivot.reindex(periods_y, fill_value=0)
        pivot.index = MONTHS
        pivot.insert(0, "รวม", pivot.sum(axis=1))
        st.metric(f"รวมทั้งปี {year} (ตาม{by})", f"฿{pivot['รวม'].sum():,.2f}")
        st.bar_chart(pivot["รวม"])
        st.subheader(f"สะสมทั้งปีแยกตาม{by}")
        st.dataframe(pivot.drop(columns="รวม").sum().rename("รวม"), use_container_width=True)
        st.subheader("รายละเอียดแต่ละงวด")
        st.dataframe(pivot.style.format("{:,.2f}"), use_container_width=True)
