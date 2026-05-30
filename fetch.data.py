"""
fetch_data.py — FRED 없는 버전
경제 캘린더: investing.com 스크래핑 (키 불필요)
시세:        Yahoo Finance (키 불필요)
뉴스:        NewsAPI (키 있으면 사용, 없으면 스킵)
"""

import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

KST   = timezone(timedelta(hours=9))
NOW   = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d %H:%M KST")
print(f"[{TODAY}] 데이터 수집 시작...\n")

# ════════════════════════════════════════
# 1. Yahoo Finance — 시세 (키 불필요)
# ════════════════════════════════════════
def fetch_yahoo(symbol, label):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval=1d&range=13mo")
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        timestamps = result["timestamp"]
        pairs = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
        if not pairs:
            raise ValueError("빈 데이터")

        current = pairs[-1][1]

        def get_ago(days):
            target = pairs[-1][0] - days * 86400
            return min(pairs, key=lambda x: abs(x[0] - target))[1]

        result_data = {
            "value":      round(current, 4),
            "prev_day":   round(pairs[-2][1], 4) if len(pairs) >= 2 else round(current, 4),
            "prev_week":  round(get_ago(7),   4),
            "prev_month": round(get_ago(30),  4),
            "prev_year":  round(get_ago(365), 4),
            "history":    [round(c, 4) for _, c in pairs[-12:]],
        }
        print(f"  ✅ {label}: {result_data['value']}")
        return result_data
    except Exception as e:
        print(f"  ⚠  {label} 실패: {e}")
        return None

# ════════════════════════════════════════
# 2. 경제 캘린더 — investing.com 스크래핑
#    키 불필요 / GDP·CPI·NFP·PCE 등 포함
# ════════════════════════════════════════

# 직접 파싱 대신 공개 JSON 엔드포인트 사용
# (investing.com 모바일 API — 공개 접근 가능)
def fetch_econ_calendar():
    """
    investing.com 의 공개 경제 캘린더 엔드포인트를 사용합니다.
    주요 미국 지표만 필터링해서 반환합니다.
    """
    today_str  = NOW.strftime("%Y-%m-%d")
    # 오늘 + 향후 3일치 캘린더
    date_to    = (NOW + timedelta(days=3)).strftime("%Y-%m-%d")

    url = (
        "https://economic-calendar.tradingview.com/events"
        f"?from={today_str}T00%3A00%3A00.000Z"
        f"&to={date_to}T23%3A59%3A59.000Z"
        "&countries=US"
        "&importance=1,2,3"          # 1=하 2=중 3=상
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept":     "application/json",
        "Origin":     "https://www.tradingview.com",
        "Referer":    "https://www.tradingview.com/",
    }

    # 관심 키워드 (영문 기준)
    KEYWORDS = [
        "GDP", "CPI", "NFP", "Nonfarm", "PCE", "Unemployment",
        "Jobless", "Fed", "FOMC", "Interest Rate", "Inflation",
        "Retail Sales", "ISM", "PMI", "Housing", "Durable"
    ]

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read())

        events = raw.get("result", [])
        items  = []
        for ev in events:
            title = ev.get("title", "") or ev.get("indicator", "") or ""
            if not any(kw.lower() in title.lower() for kw in KEYWORDS):
                continue

            actual   = ev.get("actual",   "")
            forecast = ev.get("forecast", "")
            previous = ev.get("previous", "")

            # 발표 전이면 "upcoming"
            if actual in (None, "", "—"):
                status = "upcoming"
                actual = "미발표"
            else:
                try:
                    a_f = float(str(actual).replace("%","").replace("K","").replace("M",""))
                    f_f = float(str(forecast).replace("%","").replace("K","").replace("M",""))
                    # 실업/청구는 낮을수록 좋음
                    invert = any(w in title for w in ["Jobless","Unemployment","Claims"])
                    if invert:
                        status = "beat" if a_f < f_f else "miss" if a_f > f_f else "inline"
                    else:
                        status = "beat" if a_f > f_f else "miss" if a_f < f_f else "inline"
                except:
                    status = "inline"

            items.append({
                "name":     title[:40],
                "actual":   str(actual)   if actual   else "—",
                "forecast": str(forecast) if forecast else "—",
                "previous": str(previous) if previous else "—",
                "status":   status,
            })

        print(f"  ✅ 경제 캘린더: {len(items)}개 항목")
        return items[:8]   # 최대 8개

    except Exception as e:
        print(f"  ⚠  경제 캘린더 실패: {e}")
        return []


# ════════════════════════════════════════
# 3. 뉴스 — NewsAPI (키 있을 때만)
# ════════════════════════════════════════
def fetch_news(_api_key=None):
    """
    무료 RSS 피드에서 금융 뉴스를 가져옵니다. API 키 불필요.
    CNBC, Reuters, Yahoo Finance 순서로 시도합니다.
    """
    import xml.etree.ElementTree as ET

    RSS_FEEDS = [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "market"),
        ("https://feeds.reuters.com/reuters/businessNews", "macro"),
        ("https://www.cnbc.com/id/10001147/device/rss/rss.html", "market"),
        ("https://feeds.bbci.co.uk/news/business/rss.xml", "macro"),
    ]

    # 시장 구조 변화와 관련된 키워드
    KEYWORDS = [
        "fed", "rate", "inflation", "gdp", "jobs", "treasury", "yield",
        "dollar", "oil", "gold", "tariff", "trade", "recession", "market",
        "stock", "economy", "debt", "bank", "crude", "powell", "interest"
    ]

    out = []
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml"}

    for feed_url, tag in RSS_FEEDS:
        if len(out) >= 3:
            break
        try:
            req = urllib.request.Request(feed_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
            root = ET.fromstring(raw)
            # RSS 네임스페이스 처리
            items = root.findall(".//item")
            for item in items:
                if len(out) >= 3:
                    break
                title = (item.findtext("title") or "").strip()
                desc  = (item.findtext("description") or "").strip()
                # HTML 태그 간단 제거
                import re
                desc = re.sub(r"<[^>]+>", "", desc)[:200]

                # 키워드 필터링
                combined = (title + " " + desc).lower()
                if not any(kw in combined for kw in KEYWORDS):
                    continue

                out.append({
                    "title":  title[:80],
                    "body":   desc or "원문을 확인하세요.",
                    "tag":    tag,
                    "impact": "뉴스 원문을 확인하세요.",
                })
            print(f"  OK RSS ({feed_url.split('/')[2]}): {len(items)}개 중 필터링")
        except Exception as e:
            print(f"  FAIL RSS ({feed_url.split('/')[2]}): {e}")
            continue

    print(f"  OK 뉴스 최종: {len(out)}개")
    return out


# ════════════════════════════════════════
# 4. 자동 note 생성
# ════════════════════════════════════════
def note_us10y(v):
    if v >= 5.0: return f"{v:.2f}% — 고금리 / Gold 불리"
    if v >= 4.5: return f"{v:.2f}% — 금리 부담 구간"
    if v >= 4.0: return f"{v:.2f}% — 중립 구간"
    return         f"{v:.2f}% — 금리 완화 / Gold 유리"

def note_wti(v):
    if v > 100: return f"${v:.2f} — 고유가 / 인플레 경계"
    if v > 85:  return f"${v:.2f} — 정상 범위 상단"
    if v > 70:  return f"${v:.2f} — 적정 범위 (70~85)"
    return         f"${v:.2f} — 저유가 구간"

def note_dxy(v):
    if v > 103: return f"{v:.2f} — 달러 강세 / 신흥국 부담"
    if v > 100: return f"{v:.2f} — 달러 강세 구간"
    if v > 97:  return f"{v:.2f} — 중립 구간"
    return         f"{v:.2f} — 달러 약세 / 원자재 유리"

def note_gold(v):
    return f"${v:,.0f} — US10Y·DXY 하락 시 강세"


# ════════════════════════════════════════
# 5. 기존 데이터 로드
# ════════════════════════════════════════
data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market-data.json")
existing  = {}
try:
    with open(data_path, encoding="utf-8") as f:
        existing = json.load(f)
    print("  📂 기존 데이터 로드\n")
except:
    print("  📂 기존 데이터 없음 — 새로 생성\n")


# ════════════════════════════════════════
# 6. 수집 실행
# ════════════════════════════════════════
print("── 시세 수집 ──")
us10y = fetch_yahoo("^TNX",    "US10Y")  ; time.sleep(1)
dxy   = fetch_yahoo("DX-Y.NYB","DXY")   ; time.sleep(1)
wti   = fetch_yahoo("CL=F",    "WTI")   ; time.sleep(1)
gold  = fetch_yahoo("GC=F",    "Gold")  ; time.sleep(1)

print("\n── 경제 캘린더 수집 ──")
econ = fetch_econ_calendar()
# 수집 실패 시 기존 데이터 유지
if not econ:
    econ = existing.get("economic_announcements", [])
    print("  → 기존 경제 캘린더 유지")

print("\n── 뉴스 수집 ──")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
news = fetch_news(NEWS_API_KEY)
if not news:
    news = existing.get("key_news", [])
    print("  → 기존 뉴스 유지")


# ════════════════════════════════════════
# 7. note 부착 & 실패 시 기존값 유지
# ════════════════════════════════════════
def keep(new, key):
    """새 데이터가 없으면 기존 데이터 유지"""
    if new:
        return new
    old = existing.get("metrics", {}).get(key)
    if old:
        print(f"  → {key} 기존 데이터 유지")
        return old
    return {"value": 0, "prev_day": 0, "prev_week": 0,
            "prev_month": 0, "prev_year": 0, "history": [], "note": ""}

us10y = keep(us10y, "us10y")
dxy   = keep(dxy,   "dxy")
wti   = keep(wti,   "wti")
gold  = keep(gold,  "gold")

if us10y.get("value"): us10y["note"] = note_us10y(us10y["value"])
if dxy.get("value"):   dxy["note"]   = note_dxy(dxy["value"])
if wti.get("value"):   wti["note"]   = note_wti(wti["value"])
if gold.get("value"):  gold["note"]  = note_gold(gold["value"])


# ════════════════════════════════════════
# 8. JSON 저장
# ════════════════════════════════════════
output = {
    "updated_at": TODAY,
    "metrics": {
        "us10y": us10y,
        "dxy":   dxy,
        "wti":   wti,
        "gold":  gold,
    },
    "economic_announcements": econ,
    "key_news": news,
}

os.makedirs(os.path.dirname(data_path), exist_ok=True)
with open(data_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'='*40}")
print(f"✅ market-data.json 업데이트 완료")
print(f"   US10Y : {us10y.get('value','—')}")
print(f"   DXY   : {dxy.get('value','—')}")
print(f"   WTI   : {wti.get('value','—')}")
print(f"   Gold  : {gold.get('value','—')}")
print(f"   경제지표: {len(econ)}개")
print(f"   뉴스  : {len(news)}개")
print(f"{'='*40}")
