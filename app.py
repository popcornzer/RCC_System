import os
from datetime import date

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

st.set_page_config(page_title="RCC 2026 Tracker", page_icon="⚡", layout="wide")

YEAR = 2026
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PEOPLE = ["-", "Pop", "Mom", "Tim", "k-bank"]


def secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key)


def run(query, params=None, fetch=False):
    conn = psycopg2.connect(secret("DATABASE_URL"))
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall() if fetch else None
    finally:
        conn.close()


def plabel(p):
    """'2026-11' -> 'Nov 2026'"""
    try:
        y, m = p.split("-")
        return f"{MONTHS[int(m) - 1]} {y}"
    except Exception:
        return p


# ---------- รหัสผ่าน ----------
pw = secret("APP_PASSWORD")
if pw and not st.session_state.get("ok"):
    st.title("⚡ RCC 2026")
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

# ---------- Sidebar: เลือกงวด (ไม่อิงวันที่) ----------
st.sidebar.title("⚡ RCC 2026")
db_periods = {x["period"] for x in run("SELECT DISTINCT period FROM expenses", fetch=True)}
periods = sorted({f"{YEAR}-{m:02d}" for m in range(1, 13)} | db_periods)
today_p = date.today().strftime("%Y-%m")
period = st.sidebar.selectbox(
    "เลือกงวด", periods, format_func=plabel,
    index=periods.index(today_p) if today_p in periods else 0)

r = run("SELECT value FROM settings WHERE key='salary'", fetch=True)
salary = float(r[0]["value"]) if r else 28300.0
new_salary = st.sidebar.number_input("ฐานเงินเดือน (฿)", min_value=0.0, value=salary, step=100.0)
if new_salary != salary and st.sidebar.button("บันทึกเงินเดือน"):
    run("INSERT INTO settings (key,value) VALUES ('salary',%s) "
        "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (str(new_salary),))
    st.session_state["msg"] = "บันทึกเงินเดือนแล้ว"
    st.rerun()

types = [t["name"] for t in run("SELECT name FROM expense_types ORDER BY id", fetch=True)] or [""]

# ---------- โหลดข้อมูลของงวดที่เลือก ----------
rows = run(
    """SELECT id, period, date, item, type, name, amount::float AS amount, description
       FROM expenses WHERE period = %s ORDER BY date, id""", (period,), fetch=True)
df = pd.DataFrame(rows, columns=["id", "period", "date", "item", "type", "name", "amount", "description"])

tab1, tab2, tab3 = st.tabs(["📋 รายการ", "✏️ เพิ่ม / แก้ไข / ลบ", "📊 ภาพรวมทั้งปี"])

# ---------- Tab 1: รายการ ----------
with tab1:
    total = df["amount"].sum()
    pop = df.loc[df["name"] == "Pop", "amount"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric(f"รวมค่าใช้จ่ายงวด {plabel(period)}", f"฿{total:,.2f}")
    c2.metric("ยอดเรียกเก็บ Pop", f"฿{pop:,.2f}")
    c3.metric("เงินเดือนคงเหลือ", f"฿{salary - pop:,.2f}")

    q = st.text_input("🔍 ค้นหา", "")
    view = df
    if q:
        mask = df[["item", "type", "name", "description"]].fillna("").apply(
            lambda col: col.astype(str).str.contains(q, case=False)).any(axis=1)
        view = df[mask]
    st.dataframe(
        view.drop(columns="period"), hide_index=True, use_container_width=True,
        column_config={
            "id": "ID", "date": st.column_config.DateColumn("วันที่", format="DD/MM/YYYY"),
            "item": "รายการ", "type": "ประเภท", "name": "ผู้จ่าย",
            "amount": st.column_config.NumberColumn("จำนวนเงิน", format="฿%.2f"),
            "description": "หมายเหตุ"})

    a, b = st.columns(2)
    a.subheader("สรุปตามประเภท")
    a.dataframe(df.groupby("type", dropna=False)["amount"].sum().rename("รวม"), use_container_width=True)
    b.subheader("ยอดแยกรายบุคคล")
    b.dataframe(df.groupby("name", dropna=False)["amount"].sum().rename("รวม"), use_container_width=True)

# ---------- Tab 2: เพิ่ม / แก้ไข / ลบ ----------
with tab2:
    mode = st.radio("เลือกการทำงาน", ["เพิ่มรายการ", "แก้ไข", "ลบ"], horizontal=True)
    rec = None
    if mode != "เพิ่มรายการ":
        if df.empty:
            st.info("งวดนี้ยังไม่มีรายการ")
        else:
            labels = {x.id: f"#{x.id}  {x.date:%d/%m}  {x.item}  ฿{x.amount:,.2f}" for x in df.itertuples()}
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
            c0, c00 = st.columns(2)
            d = c0.date_input("วันที่จ่ายจริง", rec["date"] if rec is not None else date.today())
            p_default = rec["period"] if rec is not None and rec["period"] in periods else period
            per = c00.selectbox("งวดตัดยอด", periods, index=periods.index(p_default), format_func=plabel)
            amount = st.number_input("จำนวนเงิน (฿)", min_value=0.0, step=1.0, format="%.2f",
                                     value=float(rec["amount"]) if rec is not None else 0.0)
            item = st.text_input("รายการ", rec["item"] if rec is not None else "")
            c1, c2 = st.columns(2)
            t_idx = types.index(rec["type"]) if rec is not None and rec["type"] in types else 0
            n_idx = PEOPLE.index(rec["name"]) if rec is not None and rec["name"] in PEOPLE else 0
            typ = c1.selectbox("จ่ายผ่าน", types, index=t_idx)
            name = c2.selectbox("ผู้รับผิดชอบ", PEOPLE, index=n_idx)
            desc = st.text_area("หมายเหตุ", rec["description"] if rec is not None and rec["description"] else "")
            if st.form_submit_button("บันทึกข้อมูล", type="primary"):
                if not item.strip() or amount <= 0:
                    st.error("กรุณากรอกรายการและจำนวนเงิน")
                else:
                    if rec is None:
                        run("INSERT INTO expenses (period,date,item,type,name,amount,description) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (per, d, item.strip(), typ, name, amount, desc.strip()))
                    else:
                        run("UPDATE expenses SET period=%s,date=%s,item=%s,type=%s,name=%s,amount=%s,"
                            "description=%s WHERE id=%s",
                            (per, d, item.strip(), typ, name, amount, desc.strip(), int(rec["id"])))
                    st.session_state["msg"] = "บันทึกสำเร็จ ✓"
                    st.rerun()

# ---------- Tab 3: ภาพรวมทั้งปี (ตามงวด) ----------
with tab3:
    rows = run(
        """SELECT period, COALESCE(NULLIF(name,''),'อื่นๆ') AS name, SUM(amount)::float AS total
           FROM expenses WHERE period LIKE %s GROUP BY 1,2""", (f"{YEAR}-%",), fetch=True)
    s = pd.DataFrame(rows, columns=["period", "name", "total"])
    if s.empty:
        st.info("ยังไม่มีข้อมูลของปีนี้")
    else:
        pivot = s.pivot_table(index="period", columns="name", values="total", aggfunc="sum", fill_value=0)
        pivot = pivot.reindex([f"{YEAR}-{m:02d}" for m in range(1, 13)], fill_value=0)
        pivot.index = MONTHS
        pivot.insert(0, "รวม", pivot.sum(axis=1))
        st.metric("รวมค่าใช้จ่ายทั้งปี", f"฿{pivot['รวม'].sum():,.2f}")
        st.bar_chart(pivot["รวม"])
        st.subheader("สรุปรายบุคคลสะสมทั้งปี")
        st.dataframe(pivot.drop(columns="รวม").sum().rename("รวม"), use_container_width=True)
        st.subheader("รายละเอียดแต่ละงวด")
        st.dataframe(pivot.style.format("{:,.2f}"), use_container_width=True)
