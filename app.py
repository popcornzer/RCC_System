import json
import os
from datetime import date
from html import escape as h

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

from carry import period_for, plan_carry, prev_period, split_amounts

st.set_page_config(page_title="RCC Tracker", page_icon="⚡", layout="centered",
                   initial_sidebar_state="collapsed")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TH_M = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
NAMES = ["Pop", "Tim", "Mom", "k-bank", "EXAT"]
PEOPLE = [""] + NAMES
PCLS = {"Pop": "pop", "Tim": "tim", "Mom": "mom", "k-bank": "kb", "EXAT": "ex"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');
.stApp, .stApp p, .stApp label, .stApp button, .stApp input, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3 {font-family:'Kanit',sans-serif;}
#MainMenu, footer {visibility:hidden;}
.block-container {padding:.8rem .8rem 7rem !important; max-width:720px;}

/* แถวที่ต้องอยู่บรรทัดเดียวกันแม้บนมือถือ */
.st-key-topbar [data-testid="stHorizontalBlock"],
div[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {
  flex-direction:row !important; flex-wrap:nowrap !important; gap:.4rem !important; align-items:center;}
.st-key-topbar [data-testid="stColumn"],
div[class*="st-key-row_"] [data-testid="stColumn"] {min-width:0 !important;}
.st-key-topbar [data-testid="stColumn"]:first-child {flex:0 0 34% !important; width:34% !important;}
.st-key-topbar [data-testid="stColumn"]:last-child {flex:1 1 0 !important; width:auto !important;}
div[class*="st-key-row_"] [data-testid="stColumn"]:first-child {flex:1 1 auto !important; width:auto !important;}
div[class*="st-key-row_"] [data-testid="stColumn"]:not(:first-child) {flex:0 0 40px !important; width:40px !important;}

/* การ์ดรายการ */
div[class*="st-key-row_"] {background:#fff; border-radius:18px; padding:10px 12px; margin-bottom:8px;
  box-shadow:0 1px 4px rgba(15,23,42,.08);}
div[class*="st-key-row_"] button {min-height:36px; width:36px; padding:0; border-radius:12px; border:none; background:#f1f5f9;}
.tx {display:flex; justify-content:space-between; align-items:flex-start; gap:8px;}
.tx-title {font-weight:500; font-size:.98rem; color:#0f172a; word-break:break-word;}
.tx-amt {font-weight:600; font-size:1rem; color:#1d4ed8; white-space:nowrap;}
.tx-meta {display:flex; flex-wrap:wrap; gap:4px; margin-top:4px;}
.tx-desc {color:#94a3b8; font-size:.72rem; margin-top:3px;}
.chip {border-radius:999px; padding:1px 8px; font-size:.68rem; background:#f1f5f9; color:#475569;}
.chip.card {background:#e0e7ff; color:#3730a3;}
.chip.inst {background:#fef3c7; color:#92400e;}
.chip.p-pop {background:#e0f2fe; color:#0369a1;}
.chip.p-tim {background:#ede9fe; color:#6d28d9;}
.chip.p-mom {background:#d1fae5; color:#047857;}
.chip.p-kb {background:#ffedd5; color:#c2410c;}
.chip.p-ex {background:#e2e8f0; color:#334155;}

/* การ์ดสรุปด้านบน */
.hero {background:linear-gradient(135deg,#0ea5e9,#2563eb); color:#fff; border-radius:24px; padding:18px 20px;
  box-shadow:0 10px 25px rgba(37,99,235,.25); margin:.5rem 0 .8rem;}
.hero-top {display:flex; justify-content:space-between; align-items:center; font-size:.85rem;}
.hero-pill {background:rgba(255,255,255,.2); border-radius:999px; padding:2px 10px; font-size:.75rem;}
.hero-label {font-size:.8rem; opacity:.85; margin-top:10px;}
.hero-amt {font-size:2.2rem; font-weight:600; line-height:1.1;}
.hero-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:14px;}
.hero-grid div {background:rgba(255,255,255,.16); border-radius:14px; padding:8px 10px;}
.hero-grid small {display:block; font-size:.68rem; opacity:.85;}
.hero-grid b {font-size:.92rem; font-weight:500;}
.sec {font-size:.78rem; font-weight:600; color:#64748b; margin:.7rem 0 .3rem;}
.hscroll {display:flex; gap:8px; overflow-x:auto; padding:2px 2px 8px; scrollbar-width:none;}
.hscroll::-webkit-scrollbar {display:none;}
.mini {flex:0 0 auto; background:#fff; border-radius:14px; padding:8px 12px; min-width:110px;
  box-shadow:0 1px 3px rgba(15,23,42,.08);}
.mini small {display:block; color:#64748b; font-size:.7rem;}
.mini b {font-size:.95rem;}

/* ปุ่มเพิ่มรายการลอยมุมขวาล่าง */
.st-key-fab {position:fixed !important; right:16px; bottom:calc(16px + env(safe-area-inset-bottom));
  z-index:1000; width:auto !important;}
.st-key-fab button {background:linear-gradient(135deg,#06b6d4,#2563eb); border:none; border-radius:999px;
  padding:.75rem 1.3rem; box-shadow:0 10px 24px rgba(37,99,235,.45);}
.st-key-fab button p {color:#fff !important; font-weight:600; font-size:1.05rem; margin:0;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


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


def dash(x):
    return x if x else "-"


def money(x):
    return f"฿{x:,.2f}"


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


@st.cache_resource
def init_db():
    run("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    run("CREATE TABLE IF NOT EXISTS period_salary (period TEXT PRIMARY KEY, salary NUMERIC NOT NULL)")
    run("ALTER TABLE expense_types ADD COLUMN IF NOT EXISTS bill_day INT")
    return True


init_db()

if msg := st.session_state.pop("msg", None):
    st.toast(msg, icon="✅")

# ---------- เลือกปี / งวด ----------
db_periods = {x["period"] for x in run("SELECT DISTINCT period FROM expenses", fetch=True)}
years = sorted({int(p[:4]) for p in db_periods if p[:4].isdigit()} | {date.today().year, date.today().year + 1})
all_periods = sorted({f"{y}-{m:02d}" for y in years for m in range(1, 13)} | db_periods)
today_p = date.today().strftime("%Y-%m")
with st.container(key="topbar"):
    cy, cp = st.columns([1, 2])
    year = cy.selectbox("ปี", years, index=years.index(date.today().year), key="year",
                        label_visibility="collapsed")
    periods_y = [f"{year}-{m:02d}" for m in range(1, 13)]
    period = cp.selectbox("งวด", periods_y, key=f"period_{year}", label_visibility="collapsed",
                          format_func=lambda p: f"งวด {MONTHS[int(p[5:]) - 1]}",
                          index=periods_y.index(today_p) if today_p in periods_y else 0)

# ---------- ฐานเงินเดือนแยกรายงวด ----------
exact = run("SELECT salary::float AS s FROM period_salary WHERE period=%s", (period,), fetch=True)
if exact:
    salary, saved = exact[0]["s"], True
else:
    fb = run("SELECT salary::float AS s FROM period_salary WHERE period < %s ORDER BY period DESC LIMIT 1",
             (period,), fetch=True)
    legacy = run("SELECT value FROM settings WHERE key='salary'", fetch=True)
    salary = fb[0]["s"] if fb else (float(legacy[0]["value"]) if legacy else 0.0)
    saved = False

trows = run("SELECT name, bill_day FROM expense_types ORDER BY id", fetch=True)
cards = [t["name"] for t in trows]
bill_days = {t["name"]: t["bill_day"] for t in trows if t["bill_day"]}
types = [""] + cards

rows = run(
    """SELECT id, period, date, item, type, name, amount::float AS amount, description,
              inst_no, inst_total, recurring
       FROM expenses WHERE period = %s ORDER BY date NULLS FIRST, id""", (period,), fetch=True)
df = pd.DataFrame(rows, columns=["id", "period", "date", "item", "type", "name", "amount",
                                 "description", "inst_no", "inst_total", "recurring"])


# ---------- ฟอร์ม / dialog ----------
def do_carry():
    prev_p = prev_period(period)
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
    st.session_state["msg"] = f"ยกมา {len(new)} รายการจาก {plabel(prev_p)}"
    st.rerun()


@st.dialog("➕ เพิ่มรายการ")
def add_dialog():
    r = run("SELECT value FROM settings WHERE key='last_add'", fetch=True)
    last = json.loads(r[0]["value"]) if r else {}
    with st.form("quick_add", clear_on_submit=True):
        amount = st.number_input("จำนวนเงิน (฿)", min_value=0.0, step=1.0, format="%.2f")
        item = st.text_input("รายการ", placeholder="เช่น Tops, เติมน้ำมัน")
        typ = st.pills("บัตร", cards, selection_mode="single",
                       default=last.get("type") if last.get("type") in cards else None)
        who = st.pills("ผู้จ่าย", NAMES, selection_mode="single",
                       default=last.get("name") if last.get("name") in NAMES else None)
        split = st.toggle("แบ่งจ่ายหลายคน (สร้างแถวยอดรวมบัตร + แถวแบ่งให้เอง)")
        split_who = st.multiselect("แบ่งระหว่าง (ใช้เมื่อเปิดแบ่งจ่าย)", NAMES, default=["Pop", "Tim"])
        d = st.date_input("วันที่จ่ายจริง", date.today())
        with st.expander("ตัวเลือกเพิ่มเติม (งวด / ผ่อน / หมายเหตุ)"):
            per_sel = st.selectbox("งวดตัดยอด", ["auto"] + all_periods, index=0,
                                   format_func=lambda p: "อัตโนมัติ (ตามวันตัดบัตร)" if p == "auto" else plabel(p))
            i1, i2 = st.columns(2)
            inst_no = i1.number_input("ผ่อน/เก็บ งวดที่ (0 = ไม่มี)", 0, 999, 0)
            inst_total = i2.number_input("จากทั้งหมด (0 = ไม่กำหนด)", 0, 999, 0)
            recurring = st.checkbox("รายการประจำทุกงวด")
            desc = st.text_input("หมายเหตุ")
        if st.form_submit_button("บันทึก", type="primary", width="stretch"):
            typ, who = typ or "", who or ""
            if not item.strip() or amount <= 0:
                st.error("กรุณากรอกรายการและจำนวนเงิน")
            elif inst_total and inst_no > inst_total:
                st.error("งวดที่ต้องไม่มากกว่าจำนวนงวดทั้งหมด")
            elif split and len(split_who) < 2:
                st.error("แบ่งจ่ายต้องเลือกอย่างน้อย 2 คน")
            else:
                per = period_for(d, bill_days.get(typ), period) if per_sel == "auto" else per_sel

                def row(t, n, a):
                    return (per, d, item.strip(), t, n, a, desc.strip(),
                            inst_no or None, inst_total or None, recurring)

                new_rows = []
                if split:
                    if typ:
                        new_rows.append(row(typ, "", amount))          # แถวยอดรวมบัตร
                    new_rows += [row("", n, a) for n, a in zip(split_who, split_amounts(amount, len(split_who)))]
                else:
                    new_rows.append(row(typ, who, amount))
                run("INSERT INTO expenses (period,date,item,type,name,amount,description,inst_no,inst_total,"
                    "recurring) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", new_rows, many=True)
                keep = {"type": typ or last.get("type"), "name": who if (who and not split) else last.get("name")}
                run("INSERT INTO settings (key,value) VALUES ('last_add',%s) "
                    "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (json.dumps(keep),))
                st.session_state["msg"] = f"บันทึกแล้ว → งวด {plabel(per)}"
                st.rerun()


def record_form(rec):
    k = f"edit_{int(rec['id'])}"
    with st.form(k):
        c0, c01 = st.columns([2, 1])
        d = c0.date_input("วันที่จ่ายจริง", rec["date"] if has(rec["date"]) else date.today(), key=f"{k}_d")
        no_date = c01.checkbox("ไม่ระบุวันที่", value=not has(rec["date"]), key=f"{k}_nd")
        p_default = rec["period"] if rec["period"] in all_periods else period
        per = st.selectbox("งวดตัดยอด", all_periods, index=all_periods.index(p_default),
                           format_func=plabel, key=f"{k}_p")
        amount = st.number_input("จำนวนเงิน (฿)", min_value=0.0, step=1.0, format="%.2f",
                                 value=float(rec["amount"]), key=f"{k}_a")
        item = st.text_input("รายการ", rec["item"], key=f"{k}_i")
        c1, c2 = st.columns(2)
        typ = c1.selectbox("บัตร/ประเภท", types, format_func=dash, key=f"{k}_t",
                           index=types.index(rec["type"]) if rec["type"] in types else 0)
        name = c2.selectbox("ผู้รับผิดชอบ", PEOPLE, format_func=dash, key=f"{k}_n",
                            index=PEOPLE.index(rec["name"]) if rec["name"] in PEOPLE else 0)
        i1, i2, i3 = st.columns(3)
        inst_no = i1.number_input("ผ่อน งวดที่", 0, 999, iv(rec["inst_no"]), key=f"{k}_in")
        inst_total = i2.number_input("จากทั้งหมด", 0, 999, iv(rec["inst_total"]), key=f"{k}_it")
        recurring = i3.checkbox("ประจำ", value=bool(rec["recurring"]), key=f"{k}_r")
        desc = st.text_area("หมายเหตุ", rec["description"] or "", key=f"{k}_ds")
        if st.form_submit_button("บันทึกข้อมูล", type="primary", width="stretch"):
            if not item.strip() or amount <= 0:
                st.error("กรุณากรอกรายการและจำนวนเงิน")
            elif inst_total and inst_no > inst_total:
                st.error("งวดที่ต้องไม่มากกว่าจำนวนงวดทั้งหมด")
            else:
                run("UPDATE expenses SET period=%s,date=%s,item=%s,type=%s,name=%s,amount=%s,description=%s,"
                    "inst_no=%s,inst_total=%s,recurring=%s WHERE id=%s",
                    (per, None if no_date else d, item.strip(), typ, name, amount, desc.strip(),
                     inst_no or None, inst_total or None, recurring, int(rec["id"])))
                st.session_state["msg"] = "บันทึกสำเร็จ"
                st.rerun()


@st.dialog("✏️ แก้ไขรายการ")
def edit_dialog(rec):
    record_form(rec)


@st.dialog("🗑️ ยืนยันการลบ")
def delete_dialog(rec):
    st.warning(f"ลบ: {rec['item']}  {money(rec['amount'])}\n\nลบแล้วกู้คืนไม่ได้")
    b1, b2 = st.columns(2)
    if b1.button("ลบรายการ", type="primary", width="stretch"):
        run("DELETE FROM expenses WHERE id=%s", (int(rec["id"]),))
        st.session_state["msg"] = "ลบรายการสำเร็จ"
        st.rerun()
    if b2.button("ยกเลิก", width="stretch"):
        st.rerun()


# ---------- การ์ดสรุปด้านบน ----------
by_card = df[~blank(df["type"])]
by_person = df[~blank(df["name"])]
pop = df.loc[df["name"] == "Pop", "amount"].sum()
remain = salary - pop
pill = f"🔒 ฐานเงินเดือน ฿{salary:,.0f}" if saved else f"ฐานเงินเดือน ฿{salary:,.0f}"
st.markdown(f"""
<div class="hero">
  <div class="hero-top"><b>{plabel(period)}</b><span class="hero-pill">{pill}</span></div>
  <div class="hero-label">เงินเดือนคงเหลือ (หักยอด Pop)</div>
  <div class="hero-amt" style="{'color:#fecaca' if remain < 0 else ''}">{money(remain)}</div>
  <div class="hero-grid">
    <div><small>ยอด Pop</small><b>{money(pop)}</b></div>
    <div><small>รวมทุกบัตร</small><b>{money(by_card['amount'].sum())}</b></div>
    <div><small>รวมทุกคน</small><b>{money(by_person['amount'].sum())}</b></div>
  </div>
</div>""", unsafe_allow_html=True)

with st.container(key="fab"):
    if st.button("＋ เพิ่มรายการ", key="fab_btn"):
        add_dialog()

tab1, tab2, tab3 = st.tabs(["📋 รายการ", "📊 ภาพรวมทั้งปี", "⚙️ ตั้งค่า"])

# ---------- Tab 1: รายการ ----------
with tab1:
    if df.empty:
        st.info("งวดนี้ยังไม่มีรายการ กด ＋ เพิ่มรายการ หรือยกรายการผ่อน/รายการประจำจากงวดก่อน")
        if st.button(f"📥 ยกรายการต่อเนื่องจาก {plabel(prev_period(period))}", key="carry_empty", width="stretch"):
            do_carry()
    else:
        if not by_card.empty:
            st.markdown('<div class="sec">ยอดตามบัตร</div><div class="hscroll">' + "".join(
                f'<div class="mini"><small>{h(c)}{" · ตัด " + str(bill_days[c]) if c in bill_days else ""}</small>'
                f'<b>{money(v)}</b></div>'
                for c, v in by_card.groupby("type")["amount"].sum().sort_values(ascending=False).items())
                + "</div>", unsafe_allow_html=True)
        if not by_person.empty:
            st.markdown('<div class="sec">ยอดรายบุคคล</div><div class="hscroll">' + "".join(
                f'<div class="mini"><small>{h(n)}</small><b>{money(v)}</b></div>'
                for n, v in by_person.groupby("name")["amount"].sum().sort_values(ascending=False).items())
                + "</div>", unsafe_allow_html=True)

        with st.expander("🔎 ค้นหา / กรอง"):
            q = st.text_input("ค้นหา", placeholder="ค้นหารายการ…", label_visibility="collapsed")
            f1, f2 = st.columns(2)
            fc = f1.selectbox("บัตร", ["ทั้งหมด"] + cards)
            fp = f2.selectbox("ผู้จ่าย", ["ทั้งหมด"] + NAMES)
        view = df
        if q:
            mask = df[["item", "type", "name", "description"]].fillna("").apply(
                lambda col: col.astype(str).str.contains(q, case=False)).any(axis=1)
            view = view[mask]
        if fc != "ทั้งหมด":
            view = view[view["type"] == fc]
        if fp != "ทั้งหมด":
            view = view[view["name"] == fp]

        PAGE = 40
        pages = max(1, -(-len(view) // PAGE))
        pg = st.number_input(f"หน้า (ทั้งหมด {pages})", 1, pages, 1) if pages > 1 else 1
        st.markdown(f'<div class="sec">{len(view)} รายการ · รวม {money(view["amount"].sum())}</div>',
                    unsafe_allow_html=True)

        for r in view.iloc[(pg - 1) * PAGE: pg * PAGE].itertuples():
            chips = []
            if r.type:
                chips.append(f'<span class="chip card">{h(r.type)}</span>')
            if r.name:
                chips.append(f'<span class="chip p-{PCLS.get(r.name, "oth")}">{h(r.name)}</span>')
            if has(r.inst_no):
                chips.append(f'<span class="chip inst">ผ่อน {inst_txt(r.inst_no, r.inst_total)}</span>')
            if has(r.date):
                chips.append(f'<span class="chip">{r.date.day} {TH_M[r.date.month - 1]}</span>')
            desc = f'<div class="tx-desc">{h(r.description)}</div>' if r.description else ""
            with st.container(key=f"row_{r.id}"):
                c = st.columns([1, 0.1, 0.1], vertical_alignment="center")
                c[0].markdown(
                    f'<div class="tx"><div><div class="tx-title">{h(r.item)}{" 🔁" if r.recurring else ""}</div>'
                    f'<div class="tx-meta">{"".join(chips)}</div>{desc}</div>'
                    f'<div class="tx-amt">{money(r.amount)}</div></div>', unsafe_allow_html=True)
                if c[1].button("✏️", key=f"e{r.id}", help="แก้ไข"):
                    edit_dialog(df[df["id"] == r.id].iloc[0])
                if c[2].button("🗑️", key=f"d{r.id}", help="ลบ"):
                    delete_dialog(df[df["id"] == r.id].iloc[0])

# ---------- Tab 2: ภาพรวมทั้งปี ----------
with tab2:
    by = st.radio("สรุปตาม", ["ผู้จ่าย", "บัตร"], horizontal=True)
    col = "name" if by == "ผู้จ่าย" else "type"          # whitelist เท่านั้น
    srows = run(
        f"""SELECT period, {col} AS grp, SUM(amount)::float AS total
            FROM expenses WHERE period LIKE %s AND {col} NOT IN ('', '-') GROUP BY 1,2""",
        (f"{year}-%",), fetch=True)
    s = pd.DataFrame(srows, columns=["period", "grp", "total"])
    if s.empty:
        st.info("ยังไม่มีข้อมูลของปีนี้")
    else:
        pivot = s.pivot_table(index="period", columns="grp", values="total", aggfunc="sum", fill_value=0)
        pivot = pivot.reindex(periods_y, fill_value=0)
        pivot.index = MONTHS
        pivot.insert(0, "รวม", pivot.sum(axis=1))
        st.metric(f"รวมทั้งปี {year} (ตาม{by})", money(pivot["รวม"].sum()))
        st.bar_chart(pivot["รวม"])
        st.subheader(f"สะสมทั้งปีแยกตาม{by}")
        st.dataframe(pivot.drop(columns="รวม").sum().rename("รวม").to_frame().style.format("{:,.2f}"),
                     width="stretch")
        st.subheader("รายละเอียดแต่ละงวด")
        st.dataframe(pivot.style.format("{:,.2f}"), width="stretch")

# ---------- Tab 3: ตั้งค่า ----------
with tab3:
    st.subheader(f"ฐานเงินเดือน {plabel(period)}")
    if saved:
        st.caption(f"🔒 ล็อกแล้ว ฿{salary:,.0f} (แก้งวดอื่นไม่กระทบงวดนี้)")
        editing = st.checkbox("🔓 ปลดล็อกเพื่อแก้ไข", key=f"unlock_{period}")
    else:
        st.caption(f"ยังไม่ได้ตั้งค่า ใช้ค่าของงวดก่อนหน้า ฿{salary:,.0f}")
        editing = True
    if editing:
        new_salary = st.number_input("ฐานเงินเดือน (฿)", min_value=0.0, value=float(salary), step=100.0,
                                     key=f"sal_{period}")
        if st.button("🔒 บันทึกและล็อก", key=f"save_sal_{period}"):
            run("INSERT INTO period_salary (period, salary) VALUES (%s,%s) "
                "ON CONFLICT (period) DO UPDATE SET salary=EXCLUDED.salary", (period, new_salary))
            st.session_state.pop(f"unlock_{period}", None)
            st.session_state["msg"] = f"ล็อกฐานเงินเดือน {plabel(period)} = ฿{new_salary:,.0f}"
            st.rerun()

    st.divider()
    st.subheader("ยกรายการต่อเนื่อง")
    st.caption("ยกรายการประจำ + ผ่อน/เก็บต่อเนื่องจากงวดก่อน (งวดที่ +1, ผ่อนครบไม่ยก, กดซ้ำไม่ซ้ำซ้อน)")
    if st.button(f"📥 ยกรายการจาก {plabel(prev_period(period))} มา {plabel(period)}", key="carry_set"):
        do_carry()

    st.divider()
    with st.expander("💳 วันตัดบัตร (ใช้เลือกงวดอัตโนมัติตอนเพิ่มรายการ)"):
        bd_df = pd.DataFrame([{"บัตร": c, "วันตัด": bill_days.get(c)} for c in cards])
        ed = st.data_editor(bd_df, hide_index=True, disabled=["บัตร"], key="bd_editor", width="stretch",
                            column_config={"วันตัด": st.column_config.NumberColumn(min_value=1, max_value=31, step=1)})
        if st.button("บันทึกวันตัดบัตร"):
            run("UPDATE expense_types SET bill_day=%s WHERE name=%s",
                [(None if pd.isna(v) else int(v), n) for n, v in zip(ed["บัตร"], ed["วันตัด"])], many=True)
            st.session_state["msg"] = "บันทึกวันตัดบัตรแล้ว"
            st.rerun()
