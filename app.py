import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import requests
import datetime
import io
import os
import glob
import re
import time
from zoneinfo import ZoneInfo
from pathlib import Path

# --- 0. BILINGUAL LOCALIZATION (i18n) ---
L = {
    "EN": {
        "title": "Japan sentinel surveillance",
        "subtitle": "",
        "sidebar_header": "Dashboard Settings",
        "lang_selector": "Language / 言語:",
        "disease_selector": "Select Diseases (Checkboxes):",
        "metric_selector": "Display Metric:",
        "metric_rate": "Cases per Sentinel Clinic (定点当たり)",
        "metric_count": "Total Reported Cases (報告数)",
        "week_slider": "Timeline Position:",
        "backfill_header": "Data Management",
        "backfill_btn": "Run Full Backfill (2023 W19 → Present)",
        "nat_avg_label": "National",
        "vs_last_week": "{val:+.2f} vs prev week",
        "legal_status_flu": "Flu Status",
        "trans_level_covid": "COVID-19 Status",
        "hist_trend": "Multi-Year Trend: {metric}",
        "heatmap": "Prefectural Distribution ({year} Week {week})",
        "table_pref": "Prefecture",
        "status_warning": "Warning (警報 >=30) 🔴",
        "status_advisory": "Advisory (注意報 >=10) 🟡",
        "status_normal": "Baseline (<10) 🟢",
        "status_high": "Wave Peak (>=15) 🔴",
        "status_low": "Baseline (<15) 🟢",
        "chart_advisory": "Flu Advisory (10.0)",
        "chart_warning": "Flu Warning (30.0)",
        "covid_wave": "COVID Wave (15.0)",
        "slider_lbl": "Position",
        "week_lbl": "Week",
        "date_lbl": "Date",
        "click_hint": " (Click to jump to this week)",
        "no_data": "Database empty. Run the backfill button in the sidebar or upload a CSV.",
        "source_data_lbl": "Source Data & References",
        "source_desc": "Data sourced directly from the Japan Institute for Health Security (JIHS) IDWR provisional sentinel feeds.",
        "download_csv": "Download Official CSV for {year}-W{week:02d}",
        "clear_sel": "Reset Map View (Show All Japan)",
        "map_mode_combined": "Dual-Color Map (Magenta vs Green)",
        "map_mode_split": "Side-by-Side Maps",
        "dominant_lbl": "Higher Burden",
        "select_at_least_one": "Please check at least one disease."
    },
    "JA": {
        "title": "🇯🇵 日本感染症サーベイランス・ダッシュボード (2023–2026)",
        "subtitle": "",
        "sidebar_header": "設定・操作",
        "lang_selector": "言語 / Language:",
        "disease_selector": "対象疾患（複数選択可）:",
        "metric_selector": "表示指標:",
        "metric_rate": "定点当たり報告数（定当）",
        "metric_count": "報告数（患者総数）",
        "week_slider": "タイムライン位置:",
        "backfill_header": "データ管理",
        "backfill_btn": "全履歴バックフィルを実行 (2023年19週〜)",
        "nat_avg_label": "全国平均",
        "vs_last_week": "前週比 {val:+.2f}",
        "legal_status_flu": "インフル流行状況",
        "trans_level_covid": "COVID警戒レベル",
        "hist_trend": "全期間推移（{metric}）",
        "heatmap": "都道府県別マップ ({year}年 第{week}週)",
        "table_pref": "都道府県",
        "status_warning": "警報レベル (>=30) 🔴",
        "status_advisory": "注意報レベル (>=10) 🟡",
        "status_normal": "平常レベル 🟢",
        "status_high": "警戒水準 (>=15) 🔴",
        "status_low": "平常水準 🟢",
        "chart_advisory": "インフル注意報 (10.0)",
        "chart_warning": "インフル警報 (30.0)",
        "covid_wave": "COVID波基準 (15.0)",
        "slider_lbl": "位置",
        "week_lbl": "週",
        "date_lbl": "日付",
        "click_hint": " (クリックでこの週に移動)",
        "no_data": "データベースが空です。サイドバーのバックフィルを実行するかCSVを読み込んでください。",
        "source_data_lbl": "データソース・参照元",
        "source_desc": "国立健康危機管理研究機構（JIHS）の感染症発生動向調査（IDWR）速報データを使用しています。",
        "download_csv": "{year}年第{week:02d}週の公式CSVをダウンロード",
        "clear_sel": "ズーム解除（全国表示に戻す）",
        "map_mode_combined": "2色比較マップ (マゼンタ vs グリーン)",
        "map_mode_split": "並列マップ表示",
        "dominant_lbl": "優勢疾患",
        "select_at_least_one": "少なくとも1つの疾患にチェックを入れてください。"
    }
}

# Stable database IDs, source column names and bilingual labels.
DISEASES = {
    "COVID-19": ("COVID-19", "COVID-19", "新型コロナ (COVID-19)"),
    "Influenza": ("インフルエンザ", "Influenza", "インフルエンザ"),
    "RSV": ("ＲＳウイルス感染症", "RS virus infection", "RSウイルス感染症"),
    "Pharyngoconjunctival fever": ("咽頭結膜熱", "Pharyngoconjunctival fever", "咽頭結膜熱"),
    "Group A streptococcal pharyngitis": ("Ａ群溶血性レンサ球菌咽頭炎", "Group A streptococcal pharyngitis", "A群溶血性レンサ球菌咽頭炎"),
    "Infectious gastroenteritis": ("感染性胃腸炎", "Infectious gastroenteritis", "感染性胃腸炎"),
    "Varicella": ("水痘", "Chickenpox", "水痘"),
    "Hand, foot and mouth disease": ("手足口病", "Hand, foot and mouth disease", "手足口病"),
    "Erythema infectiosum": ("伝染性紅斑", "Erythema infectiosum", "伝染性紅斑"),
    "Exanthema subitum": ("突発性発しん", "Exanthema subitum", "突発性発しん"),
    "Herpangina": ("ヘルパンギーナ", "Herpangina", "ヘルパンギーナ"),
    "Mumps": ("流行性耳下腺炎", "Mumps", "流行性耳下腺炎"),
    "Acute hemorrhagic conjunctivitis": ("急性出血性結膜炎", "Acute hemorrhagic conjunctivitis", "急性出血性結膜炎"),
    "Epidemic keratoconjunctivitis": ("流行性角結膜炎", "Epidemic keratoconjunctivitis", "流行性角結膜炎"),
    "Bacterial meningitis": ("細菌性髄膜炎", "Bacterial meningitis", "細菌性髄膜炎"),
    "Aseptic meningitis": ("無菌性髄膜炎", "Aseptic meningitis", "無菌性髄膜炎"),
    "Mycoplasma pneumonia": ("マイコプラズマ肺炎", "Mycoplasma pneumonia", "マイコプラズマ肺炎"),
    "Chlamydial pneumonia": ("クラミジア肺炎", "Chlamydial pneumonia", "クラミジア肺炎"),
    "Rotavirus gastroenteritis": ("感染性胃腸炎（ロタウイルス）", "Rotavirus gastroenteritis", "感染性胃腸炎（ロタウイルス）"),
}
DISEASE_TRANSLATIONS = {key: {"EN": value[1], "JA": value[2]} for key, value in DISEASES.items()}
RECORDS_PER_WEEK = 48 * len(DISEASES)

COLOR_COVID = "#c026d3"  # Vibrant Magenta
COLOR_FLU = "#16a34a"    # Vibrant Green

PREFECTURES = [
    ("北海道", "Hokkaido"), ("青森県", "Aomori"), ("岩手県", "Iwate"), ("宮城県", "Miyagi"),
    ("秋田県", "Akita"), ("山形県", "Yamagata"), ("福島県", "Fukushima"), ("茨城県", "Ibaraki"),
    ("栃木県", "Tochigi"), ("群馬県", "Gunma"), ("埼玉県", "Saitama"), ("千葉県", "Chiba"),
    ("東京都", "Tokyo"), ("神奈川県", "Kanagawa"), ("新潟県", "Niigata"), ("富山県", "Toyama"),
    ("石川県", "Ishikawa"), ("福井県", "Fukui"), ("山梨県", "Yamanashi"), ("長野県", "Nagano"),
    ("岐阜県", "Gifu"), ("静岡県", "Shizuoka"), ("愛知県", "Aichi"), ("三重県", "Mie"),
    ("滋賀県", "Shiga"), ("京都府", "Kyoto"), ("大阪府", "Osaka"), ("兵庫県", "Hyogo"),
    ("奈良県", "Nara"), ("和歌山県", "Wakayama"), ("鳥取県", "Tottori"), ("島根県", "Shimane"),
    ("岡山県", "Okayama"), ("広島県", "Hiroshima"), ("山口県", "Yamaguchi"), ("徳島県", "Tokushima"),
    ("香川県", "Kagawa"), ("愛媛県", "Ehime"), ("高知県", "Kochi"), ("福岡県", "Fukuoka"),
    ("佐賀県", "Saga"), ("長崎県", "Nagasaki"), ("熊本県", "Kumamoto"), ("大分県", "Oita"),
    ("宮崎県", "Miyazaki"), ("鹿児島県", "Kagoshima"), ("沖縄県", "Okinawa")
]
PREF_JP_TO_EN = {jp: en for jp, en in PREFECTURES}

PREF_COORDS = {
    "北海道": {"lat": 43.4, "lon": 142.3}, "青森県": {"lat": 40.8, "lon": 140.7}, "岩手県": {"lat": 39.7, "lon": 141.1},
    "宮城県": {"lat": 38.3, "lon": 140.9}, "秋田県": {"lat": 39.7, "lon": 140.1}, "山形県": {"lat": 38.2, "lon": 140.4},
    "福島県": {"lat": 37.7, "lon": 140.5}, "茨城県": {"lat": 36.3, "lon": 140.4}, "栃木県": {"lat": 36.6, "lon": 139.9},
    "群馬県": {"lat": 36.4, "lon": 139.1}, "埼玉県": {"lat": 35.9, "lon": 139.6}, "千葉県": {"lat": 35.5, "lon": 140.2},
    "東京都": {"lat": 35.7, "lon": 139.7}, "神奈川県": {"lat": 35.4, "lon": 139.5}, "新潟県": {"lat": 37.7, "lon": 138.9},
    "富山県": {"lat": 36.7, "lon": 137.2}, "石川県": {"lat": 36.8, "lon": 136.7}, "福井県": {"lat": 35.9, "lon": 136.2},
    "山梨県": {"lat": 35.7, "lon": 138.6}, "長野県": {"lat": 36.2, "lon": 138.1}, "岐阜県": {"lat": 35.7, "lon": 137.0},
    "静岡県": {"lat": 35.0, "lon": 138.3}, "愛知県": {"lat": 35.0, "lon": 137.0}, "三重県": {"lat": 34.6, "lon": 136.5},
    "滋賀県": {"lat": 35.2, "lon": 136.1}, "京都府": {"lat": 35.2, "lon": 135.5}, "大阪府": {"lat": 34.7, "lon": 135.5},
    "兵庫県": {"lat": 35.0, "lon": 134.8}, "奈良県": {"lat": 34.3, "lon": 135.8}, "和歌山県": {"lat": 33.9, "lon": 135.4},
    "鳥取県": {"lat": 35.4, "lon": 133.8}, "島根県": {"lat": 34.9, "lon": 132.5}, "岡山県": {"lat": 34.9, "lon": 133.8},
    "広島県": {"lat": 34.5, "lon": 132.8}, "山口県": {"lat": 34.2, "lon": 131.5}, "徳島県": {"lat": 33.9, "lon": 134.3},
    "香川県": {"lat": 34.2, "lon": 134.0}, "愛媛県": {"lat": 33.7, "lon": 132.8}, "高知県": {"lat": 33.4, "lon": 133.4},
    "福岡県": {"lat": 33.6, "lon": 130.6}, "佐賀県": {"lat": 33.3, "lon": 130.1}, "長崎県": {"lat": 33.0, "lon": 129.8},
    "熊本県": {"lat": 32.6, "lon": 130.7}, "大分県": {"lat": 33.2, "lon": 131.4}, "宮崎県": {"lat": 32.1, "lon": 131.3},
    "鹿児島県": {"lat": 31.6, "lon": 130.5}, "沖縄県": {"lat": 26.3, "lon": 127.8}
}

DB_NAME = "japan_surveillance_verified.db"

# --- 1. PERSISTENCE ENGINE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS weekly_records (
            year INTEGER,
            week INTEGER,
            jis_id INTEGER,
            prefecture_jp TEXT,
            prefecture_en TEXT,
            disease TEXT,
            cases_count REAL,
            cases_per_sentinel REAL,
            PRIMARY KEY (year, week, prefecture_jp, disease)
        )
    ''')
    c.execute("""CREATE TABLE IF NOT EXISTS weekly_sources (
        year INTEGER, week INTEGER, source TEXT, updated_at TEXT,
        PRIMARY KEY (year, week))""")
    c.execute("""CREATE TABLE IF NOT EXISTS update_state (
        id INTEGER PRIMARY KEY CHECK (id = 1), attempted_at TEXT, status TEXT)""")
    conn.commit()
    conn.close()

# --- 2. CSV PARSER & INGESTION ---
def parse_teiten_csv(raw_bytes, fallback_year=None, fallback_week=None):
    text = None
    for enc in ['cp932', 'shift_jis', 'utf-8']:
        try:
            text = raw_bytes.decode(enc)
            break
        except Exception:
            continue
    if not text:
        return None, None, []

    import csv
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r]

    year, week = None, None
    for r in rows[:4]:
        for cell in r:
            m = re.search(r'(\d{4})年\s*(\d+)週', cell)
            if m:
                year, week = int(m.group(1)), int(m.group(2))
                break
        if year:
            break

    if year is None:
        year, week = fallback_year, fallback_week

    disease_row_idx = None
    for idx, r in enumerate(rows[:5]):
        if any('インフルエンザ' in c for c in r):
            disease_row_idx = idx
            break
    if disease_row_idx is None:
        return None, None, []

    disease_row = rows[disease_row_idx]
    columns = {name.strip(): i for i, name in enumerate(disease_row) if name.strip()}
    if any(source not in columns for source, _, _ in DISEASES.values()):
        raise ValueError("Missing expected disease column")

    pref_start_idx = None
    for idx, r in enumerate(rows):
        if len(r) > 0 and '北海道' in r[0]:
            pref_start_idx = idx
            break
    if pref_start_idx is None:
        return None, None, []

    def safe_val(value):
        clean = str(value).strip().replace(',', '')
        if clean in ('-', '', '***'):
            return None
        try:
            return float(clean)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc

    national = next((r for r in rows if r and r[0].strip() == '総数'), None)
    pref_rows = rows[pref_start_idx:pref_start_idx + 47]
    if national is None or [r[0].strip() for r in pref_rows] != [jp for jp, _ in PREFECTURES]:
        raise ValueError("Missing national row or unexpected prefecture rows")
    if year is None or week is None:
        raise ValueError("Missing reporting week")
    datetime.date.fromisocalendar(int(year), int(week), 1)
    if fallback_year is not None and (year, week) != (fallback_year, fallback_week):
        raise ValueError("CSV reporting week does not match requested week")
    parsed_records = []
    for jis_id, row in [(0, national)] + list(enumerate(pref_rows, 1)):
        if len(row) <= max(columns[source] for source, _, _ in DISEASES.values()) + 1:
            raise ValueError("Incomplete data row")
        pref_jp = row[0].strip()
        pref_en = 'Japan' if jis_id == 0 else PREF_JP_TO_EN[pref_jp]
        for disease, (source, _, _) in DISEASES.items():
            col = columns[source]
            parsed_records.append((year, week, jis_id, pref_jp, pref_en, disease,
                                   safe_val(row[col]), safe_val(row[col + 1])))

    return year, week, parsed_records

def ingest_records(records):
    if not records:
        return
    init_db()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.executemany('''
        INSERT OR REPLACE INTO weekly_records 
        (year, week, jis_id, prefecture_jp, prefecture_en, disease, cases_count, cases_per_sentinel)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()

def load_local_csvs():
    for filepath in Path("data").glob("*teiten*.csv"):
        try:
            match = re.search(r'(\d{4})[-_](\d+)', filepath.name)
            if not match:
                continue
            year, week = map(int, match.groups())
            with sqlite3.connect(DB_NAME) as conn:
                known = conn.execute("SELECT source FROM weekly_sources WHERE year=? AND week=?", (year, week)).fetchone()
                count = conn.execute("SELECT COUNT(*) FROM weekly_records WHERE year=? AND week=?", (year, week)).fetchone()[0]
            if known and count == RECORDS_PER_WEEK:
                continue
            _, _, records = parse_teiten_csv(filepath.read_bytes(), year, week)
            if records:
                save_week(year, week, records, known[0] if known else str(filepath))
        except (OSError, ValueError, IndexError) as exc:
            st.warning(f"{filepath}: {exc}")


def save_week(year, week, records, source):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM weekly_records WHERE year=? AND week=?", (year, week))
        conn.executemany("INSERT INTO weekly_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)", records)
        conn.execute("INSERT OR REPLACE INTO weekly_sources VALUES (?, ?, ?, ?)",
                     (year, week, source, datetime.datetime.now(datetime.timezone.utc).isoformat()))


def fetch_week(y, w):
    """Fetch and validate one source; distinguish unpublished weeks from failures."""
    urls = [
        f"https://id-info.jihs.go.jp/surveillance/idwr/provisional/{y}/{w:02d}/{y}-{w:02d}-teiten.csv",
        f"https://www.niid.go.jp/niid/images/idwr/sokuho/idwr-{y}/{y}{w:02d}/{y}-{w:02d}-teiten.csv",
        f"https://www.niid.go.jp/niid/images/idwr/sokuho/idwr-{y}/{str(y)[2:]}{w:02d}/{str(y)[2:]}-{w:02d}-teiten.csv"]
    errors = []
    for url in urls:
        try:
            response = requests.get(url, timeout=8)
            if response.status_code in (404, 410):
                continue
            response.raise_for_status()
            _, _, records = parse_teiten_csv(response.content, y, w)
            if len(records) != RECORDS_PER_WEEK:
                raise ValueError("Incomplete CSV")
            Path("data").mkdir(exist_ok=True)
            Path(f"data/{y}-{w:02d}-teiten.csv").write_bytes(response.content)
            save_week(y, w, records, url)
            return True, None
        except (requests.RequestException, ValueError, IndexError, OSError) as exc:
            errors.append(str(exc))
    return False, "; ".join(errors) if errors else None


def automatic_update():
    """Check at most every six hours across sessions and processes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    with sqlite3.connect(DB_NAME, timeout=30) as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = conn.execute("SELECT attempted_at, status FROM update_state WHERE id=1").fetchone()
        interval = datetime.timedelta(minutes=15) if state and state[1] == "checking" else datetime.timedelta(hours=6)
        if state and now - datetime.datetime.fromisoformat(state[0]) < interval:
            return False
        conn.execute("INSERT OR REPLACE INTO update_state VALUES (1, ?, ?)", (now.isoformat(), "checking"))
        latest = conn.execute("SELECT year, week FROM weekly_records GROUP BY year, week HAVING COUNT(*) = ? ORDER BY year DESC, week DESC LIMIT 1", (RECORDS_PER_WEEK,)).fetchone()
    today = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).date()
    last_complete = today - datetime.timedelta(days=today.weekday() + 7)
    if latest:
        start = max(datetime.date.fromisocalendar(2023, 19, 1), datetime.date.fromisocalendar(*latest, 1) - datetime.timedelta(weeks=2))
    else:
        start = last_complete
    errors = []
    changed = False
    while start <= last_complete:
        y, w, _ = start.isocalendar()
        success, error = fetch_week(y, w)
        changed |= success
        if error and not success:
            errors.append(f"{y}-W{w:02d}")
        start += datetime.timedelta(weeks=1)
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE update_state SET status=? WHERE id=1", ("error:" + ", ".join(errors) if errors else "ok",))
    return changed


def execute_backfill(progress_bar, status_text):
    Path("data").mkdir(exist_ok=True)
    today = datetime.date.today()
    start = datetime.date.fromisocalendar(2023, 19, 1)
    end = today - datetime.timedelta(days=today.weekday())
    weeks = []
    while start <= end:
        iso = start.isocalendar()
        weeks.append((iso.year, iso.week))
        start += datetime.timedelta(weeks=1)
    with sqlite3.connect(DB_NAME) as conn:
        complete = {(y, w) for y, w, n in conn.execute(
            "SELECT year, week, COUNT(*) FROM weekly_records GROUP BY year, week HAVING COUNT(*) = ?", (RECORDS_PER_WEEK,))}
    failures = []
    for idx, (y, w) in enumerate(weeks):
        if (y, w) in complete and idx < len(weeks) - 8:
            progress_bar.progress((idx + 1) / len(weeks))
            continue
        success, _ = fetch_week(y, w)
        if not success:
            failures.append(f"{y}-W{w:02d}")
        status_text.text(f"{y}-W{w:02d} ({idx + 1}/{len(weeks)})")
        progress_bar.progress((idx + 1) / len(weeks))
    return failures

def combined_map_color(flu, covid, flu_max, covid_max):
    """Encode both levels in RGB, keeping every channel at or above 85."""
    if pd.isna(flu) or pd.isna(covid):
        return "#c6b86a"
    flu_fraction = min(1.0, max(0.0, flu / flu_max)) if flu_max > 0 else 0.0
    covid_fraction = min(1.0, max(0.0, covid / covid_max)) if covid_max > 0 else 0.0
    red_blue = round(255 - 170 * flu_fraction)
    green = round(255 - 170 * covid_fraction)
    return f"#{red_blue:02x}{green:02x}{red_blue:02x}"


@st.cache_data(ttl=86400)
def get_japan_geojson():
    url = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
    try:
        r = requests.get(url, timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def extract_selected_index(chart_state):
    if not chart_state:
        return None
    sel = getattr(chart_state, "selection", None) or (chart_state.get("selection") if isinstance(chart_state, dict) else None)
    if not sel:
        return None
    pts = getattr(sel, "points", None) or (sel.get("points") if isinstance(sel, dict) else None)
    if not pts:
        return None
    first_pt = pts[0]
    c_data = getattr(first_pt, "customdata", None) or (first_pt.get("customdata") if isinstance(first_pt, dict) else None)
    if c_data is not None and len(c_data) > 0:
        try:
            return int(c_data[0])
        except (ValueError, TypeError):
            pass
    if isinstance(first_pt, dict) and "point_index" in first_pt:
        return int(first_pt["point_index"])
    return None

def get_chart_signature(chart_state):
    if not chart_state:
        return None
    sel = getattr(chart_state, "selection", None) or (chart_state.get("selection") if isinstance(chart_state, dict) else None)
    if not sel:
        return None
    pts = getattr(sel, "points", None) or (sel.get("points") if isinstance(sel, dict) else None)
    if not pts:
        return None
    p0 = pts[0]
    p_idx = getattr(p0, "point_index", None) or (p0.get("point_index") if isinstance(p0, dict) else None)
    p_x = getattr(p0, "x", None) or (p0.get("x") if isinstance(p0, dict) else None)
    return (p_idx, str(p_x))

# --- 3. APPLICATION INITIALIZATION ---
st.set_page_config(page_title="Japan Sentinel Archive", layout="wide")

init_db()
load_local_csvs()

# Language Setup
st.sidebar.markdown("### Settings / 設定")
lang_select = st.sidebar.radio("Language / 言語:", ["English", "日本語"])
lang = "EN" if lang_select == "English" else "JA"
tx = L[lang]

@st.fragment(run_every="6h")
def check_for_updates():
    if automatic_update():
        st.rerun()
    with sqlite3.connect(DB_NAME) as conn:
        state = conn.execute("SELECT attempted_at, status FROM update_state WHERE id=1").fetchone()
    if state:
        checked = datetime.datetime.fromisoformat(state[0]).astimezone(ZoneInfo("Asia/Tokyo"))
        if state[1].startswith("error:"):
            st.sidebar.warning(("Automatic update failed for: " if lang == "EN" else "自動更新に失敗: ") + state[1][6:])
        st.sidebar.caption(("Last automatic check: " if lang == "EN" else "自動確認: ") + checked.strftime("%Y-%m-%d %H:%M JST"))

check_for_updates()

st.sidebar.markdown(f"### {tx['backfill_header']}")
if st.sidebar.button(tx["backfill_btn"]):
    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()
    failures = execute_backfill(p_bar, p_text)
    st.session_state["sync_result"] = failures
    st.rerun()

conn = sqlite3.connect(DB_NAME)
df_all = pd.read_sql("SELECT * FROM weekly_records ORDER BY year ASC, week ASC", conn)
sources = pd.read_sql("SELECT * FROM weekly_sources", conn)
conn.close()
if "sync_result" in st.session_state:
    failures = st.session_state.pop("sync_result")
    st.sidebar.warning("Unavailable or invalid: " + ", ".join(failures)) if failures else st.sidebar.success("Update complete")

if df_all.empty:
    st.title(tx["title"])
    st.warning(tx["no_data"])
    st.info("Click **'Run Full Backfill'** in the sidebar to download the historical archive, or place `2026-41-teiten.csv` in this folder.")
    st.stop()

# Generate labels & map timeline index
df_all['date'] = df_all.apply(lambda r: datetime.date.fromisocalendar(int(r['year']), int(r['week']), 5), axis=1)
df_all['date'] = pd.to_datetime(df_all['date'])
df_all['week_label'] = df_all.apply(lambda r: f"{r['year']} W{r['week']:02d}", axis=1)

available_weeks = df_all[['year', 'week', 'week_label']].drop_duplicates().sort_values(by=['year', 'week']).reset_index(drop=True)
total_available = len(available_weeks)
week_to_idx = {(int(row['year']), int(row['week'])): idx for idx, row in available_weeks.iterrows()}

if "week_slider_idx" not in st.session_state:
    st.session_state.week_slider_idx = total_available - 1
elif st.session_state.week_slider_idx >= total_available:
    st.session_state.week_slider_idx = total_available - 1

if "last_seen_chart_sig" not in st.session_state:
    st.session_state.last_seen_chart_sig = None
    
if "active_pref_zoom" not in st.session_state:
    st.session_state.active_pref_zoom = None

# Pre-slider event capture
active_chart_state = st.session_state.get("trend_chart")
current_sig = get_chart_signature(active_chart_state)
if current_sig is not None and current_sig != st.session_state.last_seen_chart_sig:
    st.session_state.last_seen_chart_sig = current_sig
    clicked_from_state = extract_selected_index(active_chart_state)
    if clicked_from_state is not None and 0 <= clicked_from_state < total_available:
        st.session_state.week_slider_idx = clicked_from_state

def on_chart_select(*args, **kwargs):
    c_state = st.session_state.get("trend_chart")
    idx = extract_selected_index(c_state)
    if idx is not None and 0 <= idx < total_available:
        st.session_state.week_slider_idx = idx
        st.session_state.last_seen_chart_sig = get_chart_signature(c_state)
        st.session_state.active_pref_zoom = None

# --- 4. SIDEBAR CONTROLS ---
st.sidebar.markdown("---")
selected_diseases = st.sidebar.multiselect(
    "Diseases (choose up to two)" if lang == "EN" else "疾患（2つまで選択）",
    options=list(DISEASES), default=["COVID-19", "Influenza"],
    format_func=lambda disease: DISEASE_TRANSLATIONS[disease][lang],
    max_selections=2, key="selected_diseases",
)
if not selected_diseases:
    st.sidebar.warning("Select at least one disease." if lang == "EN" else "疾患を1つ以上選択してください。")
    st.stop()

metric_type = st.sidebar.radio(
    tx["metric_selector"],
    ["rate", "count"],
    format_func=lambda k: tx["metric_rate"] if k == "rate" else tx["metric_count"]
)
val_col = "cases_per_sentinel" if metric_type == "rate" else "cases_count"

slider_idx = st.sidebar.slider(
    f"{tx['week_slider']} (0 – {total_available - 1})",
    min_value=0, max_value=total_available - 1, key="week_slider_idx"
)

active_year = int(available_weeks.iloc[slider_idx]['year'])
active_week = int(available_weeks.iloc[slider_idx]['week'])

# Source Attribution & Download Link
source_rows = sources[(sources.year == active_year) & (sources.week == active_week)]
current_csv_url = source_rows.iloc[0]['source'] if not source_rows.empty else None
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {tx['source_data_lbl']}")
st.sidebar.caption(tx["source_desc"])
if current_csv_url and current_csv_url.startswith("https://"):
    st.sidebar.link_button(tx["download_csv"].format(year=active_year, week=active_week), current_csv_url, width="stretch")
elif current_csv_url and Path(current_csv_url).is_file():
    st.sidebar.download_button(tx["download_csv"].format(year=active_year, week=active_week), Path(current_csv_url).read_bytes(), file_name=Path(current_csv_url).name, mime="text/csv")
else:
    st.sidebar.warning("Source not recorded. Run update to verify this week." if lang == "EN" else "ソース未記録。更新を実行してください。")
st.sidebar.caption(f"Latest: {available_weeks.iloc[-1]['week_label']}")

# --- 5. TOP SUMMARY CARDS ---
st.title(tx["title"])


df_filtered = df_all[df_all['disease'].isin(selected_diseases)].copy()

# Metric summary cards
card_cols = st.columns(len(selected_diseases) + 1)
metric_display_title = tx["metric_rate"] if metric_type == "rate" else tx["metric_count"]

for i, dis in enumerate(selected_diseases):
    ts = df_all[(df_all['disease'] == dis) & (df_all['jis_id'] == 0)].sort_values('date').reset_index(drop=True)
    selected = ts.index[(ts['year'] == active_year) & (ts['week'] == active_week)].tolist()
    c_val = ts.iloc[selected[0]][val_col] if selected else float('nan')
    p_val = ts.iloc[selected[0] - 1][val_col] if selected and selected[0] > 0 and (ts.iloc[selected[0]]['date'] - ts.iloc[selected[0] - 1]['date']).days == 7 else float('nan')
    diff = c_val - p_val
    val_str = (f"{c_val:.2f}" if metric_type == "rate" else f"{int(c_val):,}") if pd.notna(c_val) else "—"
    dis_name = DISEASE_TRANSLATIONS[dis][lang]
    card_cols[i].metric(f"{dis_name} ({tx['nat_avg_label']})", val_str, tx["vs_last_week"].format(val=diff) if pd.notna(diff) else None, delta_color="inverse")

with card_cols[-1]:
    st.metric("Selected Period", f"{active_year} Week {active_week:02d}", f"{tx['slider_lbl']} {slider_idx} of {total_available - 1}")

# --- 6. MULTI-YEAR TREND LINE CHART ---
st.subheader(tx["hist_trend"].format(metric=metric_display_title))
notes = ("Diseases use different sentinel networks and patient populations; counts and rates are not directly comparable across networks. A dash in the source is treated as missing. " if lang == "EN" else "疾患ごとに定点の種類や対象患者が異なり、報告数や定点当たり報告数を単純に比較できません。原資料の「-」は欠測として扱います。")
if "Influenza" in selected_diseases:
    notes += ("From 2025 week 15, the influenza sentinel network changed; interpret trends across this date with care." if lang == "EN" else "2025年第15週からインフルエンザの定点が変更されたため、前後の推移に注意してください。")
st.caption("Data interpretation" if lang == "EN" else "データの解釈", help=notes)


nat_trend = df_filtered[df_filtered['jis_id'] == 0].copy()
if nat_trend.empty:
    st.warning("National data unavailable. Run the update to retrieve source CSVs." if lang == "EN" else "全国データがありません。更新を実行してください。")

nat_trend['slider_idx'] = nat_trend.apply(lambda r: week_to_idx.get((int(r['year']), int(r['week'])), 0), axis=1)
nat_trend['week_tag'] = nat_trend.apply(lambda r: f"{int(r['year'])}-W{int(r['week']):02d}", axis=1)
nat_trend['disease_display'] = nat_trend['disease'].apply(lambda d: DISEASE_TRANSLATIONS[d][lang])

color_map = {DISEASE_TRANSLATIONS[d][lang]: color for d, color in zip(selected_diseases, [COLOR_COVID, COLOR_FLU])}

fig_curve = px.line(
    nat_trend, x='date', y=val_col, color='disease_display', markers=True,
    color_discrete_map=color_map,
    custom_data=['slider_idx', 'week_tag', 'disease_display'],
    labels={'date': 'Date', val_col: metric_display_title, 'disease_display': 'Disease'},
    template="plotly_white"
)

hover_fmt = ":.2f" if metric_type == "rate" else ":,d"
fig_curve.update_traces(
    mode='lines+markers', marker=dict(size=6, opacity=0.85), line=dict(width=2.5),
    hovertemplate=(
        f"<b>{tx['slider_lbl']}: %{{customdata[0]}}</b>{tx['click_hint']}<br>" +
        f"<b>{tx['week_lbl']}: %{{customdata[1]}}</b><br>" +
        f"{tx['date_lbl']}: %{{x|%Y-%m-%d}}<br>" +
        f"%{{customdata[2]}}: %{{y{hover_fmt}}}<extra></extra>"
    )
)
fig_curve.update_layout(clickmode='event+select', hovermode='closest', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

# Vertical line indicator for current slider week
selected_date_rows = nat_trend[(nat_trend['year'] == active_year) & (nat_trend['week'] == active_week)]
if not selected_date_rows.empty:
    fig_curve.add_vline(
        x=selected_date_rows['date'].iloc[0], line_dash="dash", line_color="#222222",
        annotation_text=f"Selected: {active_year}-W{active_week:02d}", annotation_position="top left"
    )


try:
    st.plotly_chart(fig_curve, key="trend_chart", on_select=on_chart_select, selection_mode="points", width="stretch")
except TypeError:
    st.plotly_chart(fig_curve, use_container_width=True)

# --- 7. REGIONAL HEATMAP (DUAL-COLOR & WHOLE-MAP ZOOM) ---
st.subheader(tx["heatmap"].format(year=active_year, week=active_week))

df_week = df_all[(df_all['year'] == active_year) & (df_all['week'] == active_week) & (df_all['jis_id'] != 0)].copy()
df_week['display_pref'] = df_week['prefecture_en'] if lang == "EN" else df_week['prefecture_jp']

# Keep all 47 prefectures, including weeks with missing values.
df_piv = df_week[df_week['disease'].isin(selected_diseases)].pivot(
    index=['prefecture_jp', 'display_pref', 'jis_id'], columns='disease', values=val_col
).reset_index()
for disease in selected_diseases:
    if disease not in df_piv:
        df_piv[disease] = float('nan')
archive_pref = df_all[df_all['jis_id'] != 0]
maxima = {}
for disease in selected_diseases:
    maximum = archive_pref.loc[archive_pref['disease'] == disease, val_col].max()
    maxima[disease] = float(maximum) if pd.notna(maximum) else 0.0
if len(selected_diseases) == 2:
    first, second = selected_diseases
    df_piv['combined_color'] = df_piv.apply(
        lambda row: combined_map_color(row[second], row[first], maxima[second], maxima[first]), axis=1
    )

geojson_data = get_japan_geojson()
if not geojson_data:
    st.warning("Map geometry could not be loaded." if lang == "EN" else "地図データを読み込めませんでした。")
zoom_pref_jp = st.session_state.active_pref_zoom

if zoom_pref_jp:
    if st.button(tx["clear_sel"], icon="🔄"):
        st.session_state.active_pref_zoom = None
        st.rerun()

def apply_geo_zoom(fig_target):
    """Applies camera zoom to the entire map around a prefecture without isolating its polygon."""
    if zoom_pref_jp and zoom_pref_jp in PREF_COORDS:
        coords = PREF_COORDS[zoom_pref_jp]
        lat, lon = coords["lat"], coords["lon"]
        d_lat = 3.5 if zoom_pref_jp == "北海道" else 1.8
        d_lon = 4.5 if zoom_pref_jp == "北海道" else 2.2
        fig_target.update_geos(
            visible=False,
            lataxis_range=[lat - d_lat, lat + d_lat],
            lonaxis_range=[lon - d_lon, lon + d_lon]
        )
        # Drop a target highlight pin on the selected prefecture
        fig_target.add_trace(go.Scattergeo(
            lat=[lat], lon=[lon], text=[zoom_pref_jp], mode="markers+text",
            textposition="top center",
            marker=dict(size=14, color="#1e3a8a", symbol="circle-open", line=dict(width=3, color="#1e3a8a")),
            showlegend=False, hoverinfo="skip"
        ))
    else:
        fig_target.update_geos(fitbounds="locations", visible=False)
    fig_target.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=550)

# A separate trace for missing values ensures they remain visible in single maps.
def single_map(disease, color):
    valid = df_piv[df_piv[disease].notna()]
    missing = df_piv[df_piv[disease].isna()]
    fig = px.choropleth(
        valid, geojson=geojson_data, locations="prefecture_jp", featureidkey="properties.nam_ja",
        color=disease, range_color=(0, maxima[disease] or 1),
        color_continuous_scale=[[0, "#ffffff"], [1, color]],
        hover_name="display_pref", labels={disease: metric_display_title},
    )
    if not missing.empty:
        fig.add_trace(go.Choropleth(
            geojson=geojson_data, locations=missing['prefecture_jp'], featureidkey="properties.nam_ja",
            z=[0] * len(missing), colorscale=[[0, "#c6b86a"], [1, "#c6b86a"]],
            showscale=False, text=missing['display_pref'],
            hovertemplate="%{text}<br>" + ("No data" if lang == "EN" else "データなし") + "<extra></extra>",
        ))
    fig.update_traces(marker_line_color="black", marker_line_width=0.6)
    apply_geo_zoom(fig)
    return fig

if geojson_data:
    st.caption("Yellow indicates missing data." if lang == "EN" else "黄色は欠測を示します。")
    if len(selected_diseases) == 2:
        first_name, second_name = (DISEASE_TRANSLATIONS[d][lang] for d in selected_diseases)
        if lang == "EN":
            st.caption(f"White: both zero. {first_name} adds magenta; {second_name} adds green. Both high: dark gray. Each reaches full intensity at its archive maximum for the selected metric. Yellow: either value missing.")
            st.caption(f"Archive maxima — {first_name}: {maxima[first]:,.2f}; {second_name}: {maxima[second]:,.2f} ({metric_display_title}).")
        else:
            st.caption(f"白は両疾患がゼロ。{first_name}はマゼンタ、{second_name}は緑で示し、両方が高い場合は濃い灰色になります。各色は選択した指標の保存済み最大値で最も濃くなります。黄色はどちらかの値が欠測です。")
            st.caption(f"保存済み最大値 — {first_name}: {maxima[first]:,.2f}、{second_name}: {maxima[second]:,.2f}（{metric_display_title}）")
        df_piv['color_index'] = range(len(df_piv))
        n_colors = len(df_piv)
        scale = []
        for index, color in enumerate(df_piv['combined_color']):
            scale.extend([[index / n_colors, color], [(index + 1) / n_colors, color]])
        fig = px.choropleth(df_piv, geojson=geojson_data, locations="prefecture_jp",
            featureidkey="properties.nam_ja", color="color_index", color_continuous_scale=scale,
            range_color=(-0.5, n_colors - 0.5), hover_name="display_pref",
            hover_data={"prefecture_jp": False, "color_index": False, first: ":.2f", second: ":.2f"},
            labels={d: DISEASE_TRANSLATIONS[d][lang] for d in selected_diseases})
        fig.update_traces(marker_line_color="black", marker_line_width=0.6)
        fig.update_layout(coloraxis_showscale=False)
        apply_geo_zoom(fig)
        st.plotly_chart(fig, width="stretch", key="map_combined")
    else:
        st.plotly_chart(single_map(selected_diseases[0], COLOR_COVID), width="stretch", key="map_single")

df_table = df_piv.sort_values(by=selected_diseases[0], ascending=False, na_position="last")
table_display = pd.DataFrame(index=df_table['display_pref'])
for disease in selected_diseases:
    table_display[DISEASE_TRANSLATIONS[disease][lang]] = df_table[disease].values

def on_table_select():
    sel_state = st.session_state.get("pref_table")
    rows = getattr(sel_state, "selection", {}).get("rows", []) if sel_state else []
    if rows:
        selected_idx = rows[0]
        selected_pref_jp = df_table.iloc[selected_idx]['prefecture_jp']
        st.session_state.active_pref_zoom = selected_pref_jp
    else:
        st.session_state.active_pref_zoom = None

try:
    st.dataframe(
        table_display, width="stretch", key="pref_table",
        on_select=on_table_select, selection_mode="single-row"
    )
except TypeError:
    st.dataframe(table_display, use_container_width=True)
