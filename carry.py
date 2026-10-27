from collections import Counter


def prev_period(p):
    """'2026-01' -> '2025-12'"""
    y, m = map(int, p.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def plan_carry(src_rows, existing_keys):
    """รายการจากงวดก่อนที่ต้องยกมา: ผ่อน/เก็บต่อเนื่อง (งวดที่ +1 ข้ามถ้าครบแล้ว) และรายการประจำ
    ข้ามรายการที่งวดนี้มีอยู่แล้ว (เทียบ item+type+name) จึงกดซ้ำได้โดยไม่ซ้ำซ้อน"""
    remaining = Counter(existing_keys)
    out = []
    for r in src_rows:
        no, tot = r.get("inst_no"), r.get("inst_total")
        new_no = no + 1 if no is not None else None
        if new_no is not None and tot is not None and new_no > tot:
            continue                      # ผ่อนครบแล้ว
        key = (r["item"], r["type"], r["name"])
        if remaining[key] > 0:
            remaining[key] -= 1           # มีอยู่แล้วในงวดนี้
            continue
        out.append(dict(date=r["date"], item=r["item"], type=r["type"], name=r["name"],
                        amount=r["amount"], description=r["description"],
                        inst_no=new_no, inst_total=tot, recurring=r["recurring"]))
    return out
