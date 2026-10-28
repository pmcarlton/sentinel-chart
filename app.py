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

# --- 0. BILINGUAL LOCALIZATION (i18n) ---
L = {
    "EN": {
        "title": "🇯🇵 Japan Category 5 Surveillance Dashboard (2023–2026)",
        "subtitle": "Complete Sentinel Surveillance Archive from May 2023 (Class 5 Inception) to Present",
        "sidebar_header": "Dashboard Settings",
        "lang_selector": "Language / 言語:",
        "disease_selector": "Select Diseases (Checkboxes):",
        "metric_selector": "Display Metric:",
        "metric_rate": "Cases per Sentinel Clinic (定点当たり)",
        "metric_count": "Total Reported Cases (報告数)",
        "week_slider": "Timeline Position:",
        "backfill_header": "Data Management",
        "backfill_btn": "Run Full Backfill (2023 W19 → Present)",
        "nat_avg_label": "National Average",
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
        "subtitle": "2023年5月（5類移行・定点把握開始）から現在までの全記録アーカイブ",
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

DISEASE_TRANSLATIONS = {
    "COVID-19": {"EN": "COVID-19", "JA": "新型コロナ (COVID-19)"},
    "Influenza": {"EN": "Influenza", "JA": "インフルエンザ"}
}

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
    flu_col, covid_col = None, None
    for j, cell in enumerate(disease_row):
        c_clean = cell.strip()
        if 'インフルエンザ' in c_clean and '鳥' not in c_clean:
            flu_col = j
        elif 'COVID' in c_clean.upper() or '新型コロナ' in c_clean:
            covid_col = j

    if flu_col is None or covid_col is None:
        return None, None, []

    pref_start_idx = None
    for idx, r in enumerate(rows):
        if len(r) > 0 and '北海道' in r[0]:
            pref_start_idx = idx
            break
    if pref_start_idx is None:
        return None, None, []

    def safe_val(val_str):
        clean = str(val_str).strip().replace(',', '')
        if clean in ['-', '', '***']:
            return 0.0
        try:
            return float(clean)
        except ValueError:
            return 0.0

    parsed_records = []
    for offset in range(47):
        r_idx = pref_start_idx + offset
        if r_idx >= len(rows):
            break
        row = rows[r_idx]
        pref_jp = row[0].strip()
        pref_en = PREF_JP_TO_EN.get(pref_jp, pref_jp)
        jis_id = offset + 1

        parsed_records.append((
            year, week, jis_id, pref_jp, pref_en, "Influenza",
            safe_val(row[flu_col]), safe_val(row[flu_col + 1])
        ))
        parsed_records.append((
            year, week, jis_id, pref_jp, pref_en, "COVID-19",
            safe_val(row[covid_col]), safe_val(row[covid_col + 1])
        ))

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
    csv_files = glob.glob("*teiten*.csv")
    for filepath in csv_files:
        try:
            m = re.search(r'(\d{4})[-_](\d+)', filepath)
            fy, fw = (int(m.group(1)), int(m.group(2))) if m else (None, None)
            with open(filepath, "rb") as f:
                _, _, recs = parse_teiten_csv(f.read(), fallback_year=fy, fallback_week=fw)
                if recs:
                    ingest_records(recs)
        except Exception:
            pass

def execute_backfill(progress_bar, status_text):
    init_db()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    weeks_list = []
    for w in range(19, 53): weeks_list.append((2023, w))
    for w in range(1, 53): weeks_list.append((2024, w))
    for w in range(1, 53): weeks_list.append((2025, w))
    for w in range(1, 42): weeks_list.append((2026, w))

    total = len(weeks_list)
    headers = {"User-Agent": "Mozilla/5.0"}
    success = 0

    for idx, (y, w) in enumerate(weeks_list):
        c.execute("SELECT COUNT(*) FROM weekly_records WHERE year=? AND week=?", (y, w))
        if c.fetchone()[0] >= 94:
            success += 1
            progress_bar.progress((idx + 1) / total)
            continue

        urls = [
            f"https://id-info.jihs.go.jp/surveillance/idwr/provisional/{y}/{w:02d}/{y}-{w:02d}-teiten.csv",
            f"https://www.niid.go.jp/niid/images/idwr/sokuho/idwr-{y}/{y}{w:02d}/{y}-{w:02d}-teiten.csv",
            f"https://www.niid.go.jp/niid/images/idwr/sokuho/idwr-{y}/{str(y)[2:]}{w:02d}/{str(y)[2:]}-{w:02d}-teiten.csv"
        ]
        recs = None
        for u in urls:
            try:
                resp = requests.get(u, headers=headers, timeout=4)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    _, _, recs = parse_teiten_csv(resp.content, fallback_year=y, fallback_week=w)
                    if recs: break
            except Exception:
                pass
        if recs:
            c.executemany('''INSERT OR REPLACE INTO weekly_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', recs)
            conn.commit()
            success += 1

        status_text.text(f"Syncing: Year {y} Week {w:02d} ({idx + 1}/{total})")
        progress_bar.progress((idx + 1) / total)
        time.sleep(0.08)

    conn.close()
    status_text.text(f"Done! {success} / {total} weeks active in database.")

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

st.sidebar.markdown(f"### {tx['backfill_header']}")
if st.sidebar.button(tx["backfill_btn"]):
    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()
    execute_backfill(p_bar, p_text)
    st.rerun()

conn = sqlite3.connect(DB_NAME)
df_all = pd.read_sql("SELECT * FROM weekly_records ORDER BY year ASC, week ASC", conn)
conn.close()

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
st.sidebar.markdown(f"### {tx['disease_selector']}")
col_cb1, col_cb2 = st.sidebar.columns(2)
with col_cb1:
    show_covid = st.checkbox(DISEASE_TRANSLATIONS["COVID-19"][lang], value=True)
with col_cb2:
    show_flu = st.checkbox(DISEASE_TRANSLATIONS["Influenza"][lang], value=True)

if not show_covid and not show_flu:
    st.sidebar.warning(tx["select_at_least_one"])
    show_covid = True

selected_diseases = []
if show_covid: selected_diseases.append("COVID-19")
if show_flu: selected_diseases.append("Influenza")

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
current_csv_url = f"https://id-info.jihs.go.jp/surveillance/idwr/provisional/{active_year}/{active_week:02d}/{active_year}-{active_week:02d}-teiten.csv"
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {tx['source_data_lbl']}")
st.sidebar.caption(tx["source_desc"])
st.sidebar.link_button(tx["download_csv"].format(year=active_year, week=active_week), current_csv_url, use_container_width=True)

# --- 5. TOP SUMMARY CARDS ---
st.title(tx["title"])
st.caption(tx["subtitle"])

df_filtered = df_all[df_all['disease'].isin(selected_diseases)].copy()

# Metric summary cards
card_cols = st.columns(len(selected_diseases) + 1)
metric_display_title = tx["metric_rate"] if metric_type == "rate" else tx["metric_count"]

for i, dis in enumerate(selected_diseases):
    df_d = df_all[df_all['disease'] == dis]
    
    if metric_type == "rate":
        ts = df_d.groupby(['year', 'week', 'date'])[val_col].mean().reset_index().sort_values(by='date')
    else:
        ts = df_d.groupby(['year', 'week', 'date'])[val_col].sum().reset_index().sort_values(by='date')
        
    c_val = ts[(ts['year'] == active_year) & (ts['week'] == active_week)][val_col].iloc[0]
    idx_list = ts.index[(ts['year'] == active_year) & (ts['week'] == active_week)].tolist()
    p_val = ts.iloc[idx_list[0] - 1][val_col] if idx_list and idx_list[0] > 0 else c_val
    diff = c_val - p_val
    
    val_str = f"{c_val:.2f}" if metric_type == "rate" else f"{int(c_val):,}"
    dis_name = DISEASE_TRANSLATIONS[dis][lang]
    card_cols[i].metric(f"{dis_name} ({tx['nat_avg_label']})", val_str, tx["vs_last_week"].format(val=diff), delta_color="inverse")

with card_cols[-1]:
    st.metric("Selected Period", f"{active_year} Week {active_week:02d}", f"{tx['slider_lbl']} {slider_idx} of {total_available - 1}")

# --- 6. MULTI-YEAR TREND LINE CHART ---
st.subheader(tx["hist_trend"].format(metric=metric_display_title))

if metric_type == "rate":
    nat_trend = df_filtered.groupby(['year', 'week', 'date', 'disease'])[val_col].mean().reset_index()
else:
    nat_trend = df_filtered.groupby(['year', 'week', 'date', 'disease'])[val_col].sum().reset_index()

nat_trend['slider_idx'] = nat_trend.apply(lambda r: week_to_idx.get((int(r['year']), int(r['week'])), 0), axis=1)
nat_trend['week_tag'] = nat_trend.apply(lambda r: f"{int(r['year'])}-W{int(r['week']):02d}", axis=1)
nat_trend['disease_display'] = nat_trend['disease'].apply(lambda d: DISEASE_TRANSLATIONS[d][lang])

color_map = {
    DISEASE_TRANSLATIONS["COVID-19"][lang]: COLOR_COVID,
    DISEASE_TRANSLATIONS["Influenza"][lang]: COLOR_FLU
}

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

if metric_type == "rate":
    if "Influenza" in selected_diseases:
        fig_curve.add_hline(y=10.0, line_dash="dash", line_color="orange", annotation_text=tx["chart_advisory"])
        fig_curve.add_hline(y=30.0, line_dash="dash", line_color="red", annotation_text=tx["chart_warning"])
    if "COVID-19" in selected_diseases:
        fig_curve.add_hline(y=15.0, line_dash="dot", line_color=COLOR_COVID, annotation_text=tx["covid_wave"])

try:
    st.plotly_chart(fig_curve, key="trend_chart", on_select=on_chart_select, selection_mode="points", width="stretch")
except TypeError:
    st.plotly_chart(fig_curve, use_container_width=True)

# --- 7. REGIONAL HEATMAP (DUAL-COLOR & WHOLE-MAP ZOOM) ---
st.subheader(tx["heatmap"].format(year=active_year, week=active_week))

df_week = df_all[(df_all['year'] == active_year) & (df_all['week'] == active_week)].copy()
df_week['display_pref'] = df_week['prefecture_en'] if lang == "EN" else df_week['prefecture_jp']

# Pivot week records for dual-disease comparison
df_piv = df_week.pivot(index=['prefecture_jp', 'display_pref', 'jis_id'], columns='disease', values=['cases_per_sentinel', 'cases_count']).reset_index()
df_piv.columns = ['_'.join(c).strip('_') for c in df_piv.columns]

covid_col = f"cases_per_sentinel_COVID-19" if metric_type == "rate" else "cases_count_COVID-19"
flu_col = f"cases_per_sentinel_Influenza" if metric_type == "rate" else "cases_count_Influenza"

# Dual-Color Difference Index: -1 (100% Flu / Green) to +1 (100% COVID / Magenta)
df_piv['covid_val'] = df_piv[covid_col].fillna(0.0)
df_piv['flu_val'] = df_piv[flu_col].fillna(0.0)
df_piv['diff_ratio'] = df_piv.apply(
    lambda r: (r['covid_val'] - r['flu_val']) / max(r['covid_val'] + r['flu_val'], 0.1), axis=1
)
df_piv['dominant'] = df_piv.apply(
    lambda r: "COVID-19" if r['covid_val'] > r['flu_val'] else ("Influenza" if r['flu_val'] > r['covid_val'] else "Balanced"), axis=1
)

geojson_data = get_japan_geojson()
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

# Build Map depending on selected checkboxes
if len(selected_diseases) == 2 and geojson_data:
    tab_combined, tab_split = st.tabs([tx["map_mode_combined"], tx["map_mode_split"]])
    
    with tab_combined:
        # Bivariate / Dual-Color Scale (Green -> Neutral Gray -> Magenta)
        bivariate_colorscale = [
            [0.0, COLOR_FLU],       # -1.0: Pure Influenza (Green)
            [0.35, "#86efac"],      # -0.3: Moderate Influenza
            [0.5, "#e2e8f0"],       #  0.0: Neutral / Balanced Baseline
            [0.65, "#f472b6"],      # +0.3: Moderate COVID
            [1.0, COLOR_COVID]      # +1.0: Pure COVID (Magenta)
        ]
        
        fig_map_dual = px.choropleth(
            df_piv, geojson=geojson_data, locations="prefecture_jp", featureidkey="properties.nam_ja",
            color="diff_ratio", color_continuous_scale=bivariate_colorscale, range_color=(-1.0, 1.0),
            hover_name="display_pref",
            hover_data={
                "prefecture_jp": False, "diff_ratio": False,
                "covid_val": ":.2f" if metric_type == "rate" else ":,d",
                "flu_val": ":.2f" if metric_type == "rate" else ":,d",
                "dominant": True
            },
            labels={
                "covid_val": f"COVID-19 ({metric_display_title})",
                "flu_val": f"Influenza ({metric_display_title})",
                "dominant": tx["dominant_lbl"],
                "diff_ratio": "Burden Balance"
            }
        )
        fig_map_dual.update_coloraxes(
            colorbar_title="Influenza 🟢 | 🟣 COVID-19",
            colorbar_tickvals=[-1, 0, 1],
            colorbar_ticktext=["Flu Dominant", "Equal / Baseline", "COVID Dominant"]
        )
        apply_geo_zoom(fig_map_dual)
        try: st.plotly_chart(fig_map_dual, width="stretch")
        except TypeError: st.plotly_chart(fig_map_dual, use_container_width=True)

    with tab_split:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f"**COVID-19 ({metric_display_title})**")
            fig_covid = px.choropleth(
                df_piv, geojson=geojson_data, locations="prefecture_jp", featureidkey="properties.nam_ja",
                color="covid_val", color_continuous_scale=[[0, "#fdf4ff"], [1, COLOR_COVID]],
                hover_name="display_pref", labels={"covid_val": metric_display_title}
            )
            apply_geo_zoom(fig_covid)
            try: st.plotly_chart(fig_covid, width="stretch")
            except TypeError: st.plotly_chart(fig_covid, use_container_width=True)
            
        with col_m2:
            st.markdown(f"**Influenza ({metric_display_title})**")
            fig_flu = px.choropleth(
                df_piv, geojson=geojson_data, locations="prefecture_jp", featureidkey="properties.nam_ja",
                color="flu_val", color_continuous_scale=[[0, "#f0fdf4"], [1, COLOR_FLU]],
                hover_name="display_pref", labels={"flu_val": metric_display_title}
            )
            apply_geo_zoom(fig_flu)
            try: st.plotly_chart(fig_flu, width="stretch")
            except TypeError: st.plotly_chart(fig_flu, use_container_width=True)

elif len(selected_diseases) == 1 and geojson_data:
    single_dis = selected_diseases[0]
    val_active = "covid_val" if single_dis == "COVID-19" else "flu_val"
    c_scale = [[0, "#fdf4ff"], [1, COLOR_COVID]] if single_dis == "COVID-19" else [[0, "#f0fdf4"], [1, COLOR_FLU]]
    
    fig_single = px.choropleth(
        df_piv, geojson=geojson_data, locations="prefecture_jp", featureidkey="properties.nam_ja",
        color=val_active, color_continuous_scale=c_scale,
        hover_name="display_pref", labels={val_active: metric_display_title}
    )
    apply_geo_zoom(fig_single)
    try: st.plotly_chart(fig_single, width="stretch")
    except TypeError: st.plotly_chart(fig_single, use_container_width=True)

# --- 8. PREFECTURAL DATA TABLE WITH CLICK-TO-ZOOM ---
df_table = df_piv.copy()
sort_col = "covid_val" if ("COVID-19" in selected_diseases and "Influenza" not in selected_diseases) else (
    "flu_val" if ("Influenza" in selected_diseases and "COVID-19" not in selected_diseases) else "covid_val"
)
df_table = df_table.sort_values(by=sort_col, ascending=False)

table_display = pd.DataFrame(index=df_table['display_pref'])
if "COVID-19" in selected_diseases:
    table_display[f"COVID-19 ({tx['table_pref'] if metric_type == 'rate' else 'Cases'})"] = df_table['covid_val'].values
if "Influenza" in selected_diseases:
    table_display[f"Influenza ({tx['table_pref'] if metric_type == 'rate' else 'Cases'})"] = df_table['flu_val'].values
if len(selected_diseases) == 2:
    table_display[tx["dominant_lbl"]] = df_table['dominant'].values

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
