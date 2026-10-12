# -*- coding: utf-8 -*-
"""
每日收盘后更新行情数据：读取 holdings.json 中的持仓代码，
从腾讯公开行情接口拉取收盘价与日K，计算 MA5 / MA10，写入 quotes.js。
仅供内部风控监控工作台使用。
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOLDINGS = os.path.join(ROOT, "holdings.json")
OUT = os.path.join(ROOT, "quotes.js")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CST = timezone(timedelta(hours=8))


def mkt(code):
    return "sh" if code[:1] in ("6", "5", "9") else "sz"


def http_get(url, decode="utf-8", retry=3):
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode(decode, "ignore")
        except Exception as e:
            if i == retry - 1:
                print("  [warn] 请求失败: %s -> %s" % (url[:80], e))
                return ""
            time.sleep(2)
    return ""


def load_codes():
    with open(HOLDINGS, "r", encoding="utf-8") as f:
        data = json.load(f)
    codes, names = [], {}
    for pf in data.get("portfolios", []):
        for h in pf.get("holdings", []):
            c = str(h.get("code", "")).strip()
            if c and c not in codes:
                codes.append(c)
                names[c] = h.get("name", "")
    return codes, names


def fetch_quotes(syms):
    """批量拉实时/收盘快照，返回 {code: {name, price}}"""
    out = {}
    for i in range(0, len(syms), 40):
        chunk = syms[i:i + 40]
        txt = http_get("https://qt.gtimg.cn/q=" + ",".join(chunk), decode="gbk")
        if not txt:
            continue
        for line in txt.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            try:
                key, val = line.split("=", 1)
                sym = key.strip().replace("v_", "")
                f = val.strip().strip('"').split("~")
                if len(f) > 6:
                    out[sym[2:]] = {"name": f[1], "price": float(f[3]), "prevClose": float(f[4])}
            except Exception:
                continue
    return out


def fetch_kline(sym):
    """拉取前复权日K，返回收盘价列表"""
    txt = http_get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,40,qfq" % sym)
    if not txt:
        return []
    try:
        js = json.loads(txt)
        node = js.get("data", {}).get(sym, {})
        rows = node.get("qfqday") or node.get("day") or []
        return [float(r[2]) for r in rows if len(r) > 2]
    except Exception:
        return []


def main():
    codes, names = load_codes()
    print("共 %d 只标的待更新" % len(codes))
    syms = [mkt(c) + c for c in codes]
    quotes = fetch_quotes(syms)
    stocks, last_date = {}, None

    for idx, (code, sym) in enumerate(zip(codes, syms), 1):
        price = quotes.get(code, {}).get("price")
        closes = fetch_kline(sym)
        ma5 = ma10 = None
        if closes:
            px = price if price is not None else closes[-1]
            series = closes + ([px] if len(closes) >= 1 and price is not None else [])
            # 用最近10个值（含当日）计算均线
            ma5 = round(sum(series[-5:]) / 5, 4) if len(series) >= 5 else None
            ma10 = round(sum(series[-10:]) / 10, 4) if len(series) >= 10 else None
        if price is None and closes:
            price = closes[-1]
        if price is None:
            print("  [skip] %s 无行情" % code)
            continue
        stocks[code] = {
            "name": names.get(code) or quotes.get(code, {}).get("name", code),
            "price": round(price, 4),
            "close": round(price, 4),
            "ma5": ma5,
            "ma10": ma10,
        }
        print("  [%d/%d] %s %s 现价=%.3f MA5=%s MA10=%s" %
              (idx, len(codes), code, stocks[code]["name"], price, ma5, ma10))

    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    payload = {"date": date_str, "time": time_str, "stocks": stocks}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.TDX_QUOTES=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    print("已写入 %s，共 %d 只，日期 %s %s" % (OUT, len(stocks), date_str, time_str))


if __name__ == "__main__":
    main()
