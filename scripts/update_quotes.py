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
    """拉取日K，返回 [(日期, 收盘), ...]。腾讯前复权优先，失败回退新浪（不被 WAF 封）。"""
    txt = http_get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,40,qfq" % sym)
    if txt:
        try:
            js = json.loads(txt)
            node = js.get("data", {}).get(sym, {})
            rows = node.get("qfqday") or node.get("day") or []
            out = [(r[0], float(r[2])) for r in rows if len(r) > 2]
            if out:
                return out
        except Exception:
            pass
    # 新浪日K回退
    url = ("https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
           "?symbol=%s&scale=240&ma=no&datalen=40" % sym)
    req_headers = dict(UA)
    req_headers["Referer"] = "https://finance.sina.com.cn"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            out = [(x["day"], float(x["close"])) for x in data]
            if out:
                return out
        except Exception:
            time.sleep(1 + i)
    return []


TARGET_DATE = None  # --date YYYY-MM-DD：锚定目标交易日（周末/盘中更新时必传）


def main():
    global TARGET_DATE
    args = sys.argv[1:]
    if "--date" in args:
        TARGET_DATE = args[args.index("--date") + 1]
    codes, names = load_codes()
    print("共 %d 只标的待更新" % len(codes))
    syms = [mkt(c) + c for c in codes]
    quotes = fetch_quotes(syms)
    stocks, last_date = {}, None

    for idx, (code, sym) in enumerate(zip(codes, syms), 1):
        rows = fetch_kline(sym)
        if TARGET_DATE:
            rows = [r for r in rows if r[0] <= TARGET_DATE]  # 锚定目标交易日，丢弃盘中行
        closes = [c for _, c in rows]
        price = closes[-1] if closes else quotes.get(code, {}).get("price")
        kdate = rows[-1][0] if rows else None
        if kdate and (last_date is None or kdate > last_date):
            last_date = kdate
        ma5 = ma10 = None
        if closes:
            series = closes  # 已锚定目标日，直接用收盘序列算均线
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
    date_str = last_date or now.strftime("%Y-%m-%d")  # 优先用K线锚定交易日
    time_str = "15:30" if (last_date and last_date != now.strftime("%Y-%m-%d")) else now.strftime("%H:%M")
    payload = {"date": date_str, "time": time_str, "stocks": stocks}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.TDX_QUOTES=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    print("已写入 %s，共 %d 只，日期 %s %s" % (OUT, len(stocks), date_str, time_str))


if __name__ == "__main__":
    main()
