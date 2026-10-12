# -*- coding: utf-8 -*-
"""用 quotes.js 的最新价与截图参考价（成本价）重算实时收益，并与截图累计涨幅交叉校验。"""
import io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q_txt = io.open(os.path.join(ROOT, "quotes.js"), encoding="utf-8").read()
q = json.loads(q_txt[q_txt.index("=") + 1:].strip().rstrip(";"))
data = json.loads(io.open(os.path.join(ROOT, "holdings.json"), encoding="utf-8").read())

print("行情日期：%s %s\n" % (q.get("date"), q.get("time")))
print("%-14s %-8s %8s %8s %9s %9s %8s" % ("名称", "代码", "成本价", "最新价", "截图涨幅", "实时收益", "差异"))
rows = []
for pf in data["portfolios"]:
    for h in pf["holdings"]:
        c = q["stocks"].get(h["code"])
        if not c:
            continue
        cost = h["ref"]
        rt = (c["price"] / cost - 1) * 100
        diff = rt - h["pct"]
        rows.append((abs(diff), h["name"], h["code"], cost, c["price"], h["pct"], rt, diff))

rows.sort(reverse=True)
for _, name, code, cost, px, pct, rt, diff in rows:
    flag = "  ⚠ 差异大" if abs(diff) > 8 else ""
    print("%-14s %-8s %8.3f %8.3f %8.2f%% %8.2f%% %+7.2f%s" % (name, code, cost, px, pct, rt, diff, flag))

print("\n共 %d 只 | 平均差异 %+.2f 个百分点 | 差异 >8 个百分点的：%d 只"
      % (len(rows), sum(r[7] for r in rows) / len(rows), sum(1 for r in rows if r[0] > 8)))
