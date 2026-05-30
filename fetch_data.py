"""
fetch_data.py
매일 아침 GitHub Actions가 이 스크립트를 실행합니다.
US10Y, DXY, WTI, Gold 데이터를 무료 API에서 가져와서
data/market-data.json 파일을 업데이트합니다.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ─── 한국시간 기준 ───
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d %H:%M KST")

print(f"[{TODAY}] 데이터 수집 시작...")

# ─── Yahoo Finance에서 시세 가져오기 ───
def fetch_yahoo(symbol):
    """Yahoo Finance v8 API — 무료, 키 불필요"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=13mo"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        timestamps = result["timestamp"]

        # None 제거
        pairs = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
        if not pairs:
            return None

        # 최신값
        current = pairs[-1][1]

        # 과거 기준값 찾기 (인덱스 기반)
        def get_ago(days):
            target = pairs[-1][0] - days * 86400
            closest = min(pairs, key=lambda x: abs(x[0] - target))
            return closest[1]

        prev_day   = pairs[-2][1] if len(pairs) >= 2 else current
        prev_week  = get_ago(7)
        prev_month = get_ago(30)
        prev_year  = get_ago(365)

        # 최근 12개 종가 (스파크라인용)
        history = [round(c, 4) for _, c in pairs[-12:]]

        return {
            "value":      round(current, 4),
            "prev_day":   round(prev_day, 4),
            "prev_week":  round(prev_week, 4),
            "prev_month": round(prev_month, 4),
            "prev_year":  round(prev_year, 4),
            "history":    history
        }
    except Exception as e:
        print(f"  ⚠ Yahoo fetch 실패 ({symbol}): {e}")
        return None

# ─── 경제 지표 (FRED API) ───
def fetch_fred(series_id, api_key):
    """FRED API — 무료, 키 필요 (아래 안내 참고)"""
    if not api_key:
        return None
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={api_key}&file_type=json"
           f"&sort_order=desc&limit=2")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        obs = data["observations"]
        latest = obs[0]["value"] if obs else "."
        prev   = obs[1]["value"] if len(obs) > 1 else "."
        return {"latest": latest, "previous": prev}
    except Exception as e:
        print(f"  ⚠ FRED fetch 실패 ({series_id}): {e}")
        return None

# ─── 뉴스 (NewsAPI) ───
def fetch_news(api_key):
    """NewsAPI — 무료 플랜 가능, 키 필요"""
    if not api_key:
        return []
    url = (f"https://newsapi.org/v2/top-headlines"
           f"?category=business&language=en&pageSize=5"
           f"&apiKey={api_key}")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
        articles = data.get("articles", [])
        news = []
        for a in articles[:3]:
            news.append({
                "title":  a.get("title", "")[:80],
                "body":   a.get("description", "") or "",
                "tag":    "market",
                "impact": "뉴스 원문을 확인하세요."
            })
        return news
    except Exception as e:
        print(f"  ⚠ 뉴스 fetch 실패: {e}")
        return []

# ─── 환경변수에서 API 키 읽기 ───
FRED_API_KEY  = os.environ.get("FRED_API_KEY", "")
NEWS_API_KEY  = os.environ.get("NEWS_API_KEY", "")

# ─── 시세 수집 ───
print("  📈 US10Y 수집 중...")
us10y = fetch_yahoo("^TNX")   # 10년 국채 수익률
time.sleep(1)

print("  💵 DXY 수집 중...")
dxy = fetch_yahoo("DX-Y.NYB") # 달러 인덱스
time.sleep(1)

print("  🛢  WTI 수집 중...")
wti = fetch_yahoo("CL=F")     # WTI 원유
time.sleep(1)

print("  🥇 Gold 수집 중...")
gold = fetch_yahoo("GC=F")    # 금 선물
time.sleep(1)

# 수집 실패 시 이전 데이터 유지
def fallback(new_data, key, existing):
    if new_data:
        print(f"  ✅ {key} 수집 성공: {new_data['value']}")
        return new_data
    print(f"  ⚠ {key} 수집 실패 — 이전 데이터 유지")
    return existing.get("metrics", {}).get(key, {"value": 0})

# ─── 기존 데이터 로드 (실패시 빈 dict) ───
existing = {}
data_path = os.path.join(os.path.dirname(__file__), "data", "market-data.json")
try:
    with open(data_path, "r", encoding="utf-8") as f:
        existing = json.load(f)
    print("  📂 기존 데이터 로드 완료")
except:
    print("  📂 기존 데이터 없음 — 새로 생성")

# ─── 경제 지표 (FRED) ───
econ = existing.get("economic_announcements", [])
if FRED_API_KEY:
    print("  📊 경제 지표 수집 중...")
    fed_rate  = fetch_fred("FEDFUNDS", FRED_API_KEY)
    core_pce  = fetch_fred("PCEPILFE", FRED_API_KEY)
    jobless   = fetch_fred("ICSA", FRED_API_KEY)

    econ = []
    if fed_rate:
        econ.append({
            "name": "Fed 기준금리",
            "actual": f"{fed_rate['latest']}%",
            "forecast": "동결",
            "previous": f"{fed_rate['previous']}%",
            "status": "inline"
        })
    if core_pce:
        val = float(core_pce['latest']) if core_pce['latest'] != '.' else 0
        prev_val = float(core_pce['previous']) if core_pce['previous'] != '.' else 0
        status = "beat" if val < prev_val else "miss" if val > prev_val else "inline"
        econ.append({
            "name": "Core PCE (YoY)",
            "actual": f"{val:.1f}%",
            "forecast": "—",
            "previous": f"{prev_val:.1f}%",
            "status": status
        })
    if jobless:
        econ.append({
            "name": "신규 실업수당 청구",
            "actual": f"{int(float(jobless['latest'])):,}K" if jobless['latest'] != '.' else "—",
            "forecast": "—",
            "previous": f"{int(float(jobless['previous'])):,}K" if jobless['previous'] != '.' else "—",
            "status": "inline"
        })

# ─── 뉴스 ───
news = existing.get("key_news", [])
if NEWS_API_KEY:
    print("  📰 뉴스 수집 중...")
    news = fetch_news(NEWS_API_KEY)

# ─── US10Y note 자동 생성 ───
def us10y_note(data):
    if not data:
        return ""
    v = data["value"]
    if v >= 5.0:
        return f"{v:.2f}% — 고금리 주의 / Gold 불리"
    elif v >= 4.5:
        return f"{v:.2f}% — 금리 부담 구간"
    elif v >= 4.0:
        return f"{v:.2f}% — 중립 구간"
    else:
        return f"{v:.2f}% — 금리 완화 / Gold 유리"

def wti_note(data):
    if not data:
        return ""
    v = data["value"]
    if v > 100:
        return f"${v:.2f} — 고유가 인플레 경계"
    elif v > 85:
        return f"${v:.2f} — 정상 범위 상단"
    elif v > 70:
        return f"${v:.2f} — 적정 범위 (70~85)"
    else:
        return f"${v:.2f} — 저유가 구간"

if us10y:
    us10y["note"] = us10y_note(us10y)
if wti:
    wti["note"] = wti_note(wti)
if dxy:
    dxy["note"] = f"{dxy['value']:.2f} — DXY 기준 100 상회시 달러강세"
if gold:
    gold["note"] = f"${gold['value']:,.0f} — 금리 하락 시 강세 전망"

# ─── 최종 JSON 조합 ───
output = {
    "updated_at": TODAY,
    "metrics": {
        "us10y": fallback(us10y, "us10y", existing),
        "dxy":   fallback(dxy,   "dxy",   existing),
        "wti":   fallback(wti,   "wti",   existing),
        "gold":  fallback(gold,  "gold",  existing),
    },
    "economic_announcements": econ,
    "key_news": news
}

# ─── 파일 저장 ───
os.makedirs(os.path.dirname(data_path), exist_ok=True)
with open(data_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 완료! data/market-data.json 업데이트됨")
print(f"   US10Y : {output['metrics']['us10y'].get('value', '—')}")
print(f"   DXY   : {output['metrics']['dxy'].get('value', '—')}")
print(f"   WTI   : {output['metrics']['wti'].get('value', '—')}")
print(f"   Gold  : {output['metrics']['gold'].get('value', '—')}")
