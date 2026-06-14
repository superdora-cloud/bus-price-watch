"""
バス比較なび 日付別最安値スクレイパー（夜行便のみ）
- routes.json に登録された区間について今日から60日分の最安値を取得
- data/daily_prices.csv に記録
- docs/daily_data.json をグラフ用に再生成
"""

import calendar as cal_module
import csv
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------
# 設定
# ---------------------------------------------------------------
BASE_URL = "https://www.bushikaku.net"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.bushikaku.net/",
    # Cloudflare等のWAFがチェックすることが多いブラウザ固有ヘッダを追加
    "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24", "Google Chrome";v="125"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}
SLEEP_SEC = 10.0  # サーバー負荷軽減のため余裕を持たせる
DAYS_AHEAD = 60  # 今日から何日先まで取得するか
# 最安値カレンダーは「表示している月 + その前後の週余り数日」しかデータがないが、
# /search/{slug}/{YYYYMM}/time_division_type-night/ で任意の月の
# 「夜行便のみ」のカレンダーを取得できるため、必要な月数分だけ
# 追加フェッチしてカレンダーを結合して使用する。

# パス
ROOT_DIR = Path(__file__).parent.parent
ROUTES_PATH = Path(__file__).parent / "routes.json"
CSV_PATH = ROOT_DIR / "data" / "daily_prices.csv"
JSON_PATH = ROOT_DIR / "docs" / "daily_data.json"

CSV_HEADER = ["date", "departure_date", "departure", "arrival", "price"]


# ---------------------------------------------------------------
# セッション管理
# ---------------------------------------------------------------
_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        try:
            _session.get(BASE_URL + "/", timeout=15)
            time.sleep(SLEEP_SEC)
        except Exception:
            pass
    return _session


def fetch_html(url: str, retries: int = 3, retry_wait: float = SLEEP_SEC) -> BeautifulSoup | None:
    """
    ページを取得して BeautifulSoup を返す。
    502 などの一時的なサーバーエラーに対しては、少し待って最大3回まで再試行する。
    """
    session = get_session()
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            if attempt < retries:
                print(f"  [WARN] fetch failed (attempt {attempt}/{retries}): {url} -> {e} -> {retry_wait:.0f}秒待って再試行します")
                time.sleep(retry_wait)
            else:
                print(f"  [WARN] fetch failed (attempt {attempt}/{retries}): {url} -> {e} -> あきらめ")
    return None


# ---------------------------------------------------------------
# 価格パース
# ---------------------------------------------------------------
def parse_price(text: str) -> int | None:
    """'1,500円' -> 1500  /  '---' や空文字 -> None  /  「円」なし -> None"""
    if not text or text.strip() in ("---", ""):
        return None
    if "円" not in text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def cal_month_days(year: int, month: int) -> int:
    """指定した年月の日数を返す"""
    return cal_module.monthrange(year, month)[1]


# ---------------------------------------------------------------
# スクレイピング本体
# ---------------------------------------------------------------
def _cell_candidates(text: str) -> list[tuple[int, int | None]]:
    """
    カレンダーの <td> テキストから (日付番号, 価格 or None) の候補一覧を返す。

    例: "12,900円" は
      - day_len=1: 日付=1, 価格部分="2,900" -> 2900
      - day_len=2: 日付=12, 価格部分="900" -> 900
    の両方が構文上可能なため、両方を候補として返し、
    呼び出し側で「1,2,3,...」の連番に合う候補を選ぶ。
    価格部分は「3桁ごとに,で区切った数字」(\\d{1,3}(,\\d{3})*) の形式のときのみ有効とし、
    ",200" のようにカンマが先頭に来る不正な分割は除外する。
    """
    candidates: list[tuple[int, int | None]] = []

    if text.endswith("ー"):
        day_part = text[:-1]
        if day_part.isdigit() and 1 <= len(day_part) <= 2:
            day_num = int(day_part)
            if 1 <= day_num <= 31:
                candidates.append((day_num, None))
        return candidates

    if not text.endswith("円"):
        return candidates

    body = text[:-1]
    for day_len in (1, 2):
        if len(body) <= day_len:
            continue
        day_str = body[:day_len]
        amount_str = body[day_len:]
        if not day_str.isdigit():
            continue
        day_num = int(day_str)
        if not (1 <= day_num <= 31):
            continue
        if not re.match(r"^\d{1,3}(,\d{3})*$", amount_str):
            continue
        amount = int(amount_str.replace(",", ""))
        candidates.append((day_num, amount))
    return candidates


def extract_calendar_map(soup: BeautifulSoup, ref_year: int, ref_month: int) -> dict[date, int | None] | None:
    """
    「最安値カレンダー」(SearchLowestPriceCalendar)のテーブルを解析し、
    「出発日 -> 最安値(円) or None(データなし)」の辞書を作成する。

    ref_year/ref_month は、このカレンダーが表示している「当月」を示す。
    例: /search/{slug}/time_division_type-night/ -> 今日の月
        /search/{slug}/202607/time_division_type-night/ -> 2026年7月

    <td> のテキストは "126,200円" や "1ー" の形式だが、日付部分が1桁/2桁の
    どちらかは構文だけでは一意に決まらない（例: "12,900円" は
    "1日、2,900円" と "12日、900円" の両方が可能）。
    そのため各テキストについて(日付,価格)の候補を列挙し、
    「1,2,3,...月末日」と連番になるように各セルから候補を選ぶことで
    曖昧さを解消し、その位置を ref_year/ref_month の1日として全セルに
    日付を割り振る。
    """
    for table in soup.find_all("table", class_=re.compile(r"calend[ae]r", re.I)):
        cell_candidates: list[list[tuple[int, int | None]]] = []
        valid = True
        for td in table.find_all("td"):
            cands = _cell_candidates(td.get_text(strip=True))
            if not cands:
                valid = False
                break
            cell_candidates.append(cands)
        if not valid or not cell_candidates:
            continue

        days_in_month = cal_month_days(ref_year, ref_month)
        n = len(cell_candidates)
        for start in range(n):
            if start + days_in_month > n:
                continue
            chosen: list[tuple[int, int | None]] = []
            ok = True
            for i in range(days_in_month):
                match = next((c for c in cell_candidates[start + i] if c[0] == i + 1), None)
                if match is None:
                    ok = False
                    break
                chosen.append(match)
            if not ok:
                continue

            first_cell_date = date(ref_year, ref_month, 1) - timedelta(days=start)
            result: dict[date, int | None] = {}
            for idx in range(n):
                d = first_cell_date + timedelta(days=idx)
                if start <= idx < start + days_in_month:
                    result[d] = chosen[idx - start][1]
                else:
                    # 前月/次月の余白セル: その日付の「日」に一致する候補を選ぶ
                    cands = cell_candidates[idx]
                    match = next((c for c in cands if c[0] == d.day), cands[0])
                    result[d] = match[1]
            return result
        return None
    return None


def fetch_route_calendar(slug: str, today: date, days_ahead: int) -> dict[date, int | None]:
    """
    指定区間について、today から days_ahead 日分をカバーするのに必要な
    月のカレンダーページを取得し、「出発日 -> 最安値」の辞書にまとめて返す。

    /search/{slug}/.../time_division_type-night/ を付与することで、
    「夜行便のみ」の最安値カレンダーを取得する。
    """
    calendar_map: dict[date, int | None] = {}

    # 今月のカレンダー（日付指定なしのトップ検索ページ、夜行便のみ）
    soup = fetch_html(f"{BASE_URL}/search/{slug}/time_division_type-night/")
    if soup is not None:
        m = extract_calendar_map(soup, today.year, today.month)
        if m:
            calendar_map.update(m)
    time.sleep(SLEEP_SEC)

    # 対象期間をカバーするのに必要な月を列挙（今月を含む）
    last_date = today + timedelta(days=days_ahead - 1)
    months_needed: list[tuple[int, int]] = []
    y, m = today.year, today.month
    while (y, m) <= (last_date.year, last_date.month):
        months_needed.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # 今月分は取得済みなので、来月以降のみ追加フェッチ
    for (y, m) in months_needed[1:]:
        url = f"{BASE_URL}/search/{slug}/{y}{m:02d}/time_division_type-night/"
        soup = fetch_html(url)
        if soup is not None:
            cm = extract_calendar_map(soup, y, m)
            if cm:
                calendar_map.update(cm)
        time.sleep(SLEEP_SEC)

    return calendar_map


# ---------------------------------------------------------------
# CSV 操作
# ---------------------------------------------------------------
def load_csv() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def append_today(new_records: list[dict], today: date) -> None:
    """既存CSVから今日取得分を除いて new_records を追記して保存"""
    existing = load_csv()
    today_str = today.isoformat()
    kept = [r for r in existing if r["date"] != today_str]
    all_rows = kept + new_records
    save_csv(all_rows)
    print(f"  CSV: {len(kept)} existing + {len(new_records)} new = {len(all_rows)} total rows")


# ---------------------------------------------------------------
# JSON 生成（グラフ用）
# ---------------------------------------------------------------
def build_json() -> None:
    """
    daily_prices.csv を読み込み以下の構造の JSON を生成する。
    {
      "routes": ["東京都→京都府", ...],
      "data": {
        "東京都→京都府": {
          "2026-06-26": [
            {"date": "2026-06-10", "price": 1500},  // 取得日と価格
            {"date": "2026-06-11", "price": 1480},
            ...
          ]
        }
      },
      "updated_at": "2026-06-10T00:00:00Z"
    }
    """
    rows = load_csv()
    if not rows:
        print("  [WARN] daily CSV is empty, skip JSON generation")
        return

    data: dict[str, dict[str, list]] = {}
    for r in rows:
        route = f"{r['departure']}→{r['arrival']}"
        dep_date = r["departure_date"]
        if route not in data:
            data[route] = {}
        if dep_date not in data[route]:
            data[route][dep_date] = []
        data[route][dep_date].append({
            "date": r["date"],
            "price": int(r["price"]),
        })

    # 取得日順ソート
    for route in data:
        for dep_date in data[route]:
            data[route][dep_date].sort(key=lambda x: x["date"])

    output = {
        "routes": sorted(data.keys()),
        "data": data,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  JSON: {len(data)} routes written -> {JSON_PATH}")


# ---------------------------------------------------------------
# メイン
# ---------------------------------------------------------------
def main() -> None:
    today = date.today()
    print(f"=== DailyPriceScraper start: {today} ===")

    # routes.json を読み込む
    with open(ROUTES_PATH, encoding="utf-8") as f:
        routes = json.load(f)

    # デバッグ用: 環境変数で処理範囲を制限できるようにする
    routes_limit = os.environ.get("ROUTES_LIMIT", "").strip()
    if routes_limit:
        routes = routes[: int(routes_limit)]

    days_ahead = DAYS_AHEAD
    days_limit = os.environ.get("DAYS_LIMIT", "").strip()
    if days_limit:
        days_ahead = int(days_limit)

    # 取得対象日リスト（今日から指定日数後まで）
    target_dates = [today + timedelta(days=i) for i in range(days_ahead)]

    # 必要な月数（今月を含む）を見積もってリクエスト数を表示
    last_date = target_dates[-1]
    months_count = (last_date.year - today.year) * 12 + (last_date.month - today.month) + 1
    print(f"Routes: {len(routes)} 区間 × 最大{months_count}ヶ月分のカレンダー = 最大{len(routes) * months_count} リクエスト予定")
    print(f"対象期間: {target_dates[0]} 〜 {target_dates[-1]} ({days_ahead}日分)")

    all_records: list[dict] = []
    failed = 0
    total = len(routes) * len(target_dates)

    for route in routes:
        slug = route["slug"]
        departure = route["departure"]
        arrival = route["arrival"]
        print(f"\n[{departure}→{arrival}] ({slug})")

        calendar_map = fetch_route_calendar(slug, today, days_ahead)

        for dep_date in target_dates:
            price = calendar_map.get(dep_date)

            if price is not None:
                all_records.append({
                    "date": today.isoformat(),
                    "departure_date": dep_date.isoformat(),
                    "departure": departure,
                    "arrival": arrival,
                    "price": price,
                })
                print(f"  {dep_date}: {price:,}円")
            else:
                failed += 1
                print(f"  {dep_date}: 取得失敗")

    failure_rate = failed / total if total > 0 else 0
    print(f"\nTotal: {len(all_records)} records, failed: {failed}/{total} ({failure_rate:.0%})")

    if failure_rate > 0.5:
        print(f"[ERROR] Failure rate {failure_rate:.0%} exceeds 50%. Aborting.")
        raise SystemExit(1)

    if all_records:
        append_today(all_records, today)
        build_json()
    else:
        print("[ERROR] No records scraped at all.")
        raise SystemExit(1)

    print("=== Done ===")


if __name__ == "__main__":
    main()
