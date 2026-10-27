import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
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
        "disease_selector": "Disease:",
        "metric_selector": "Display Metric:",
        "metric_rate": "Cases per Sentinel Clinic (定点当たり)",
        "metric_count": "Total Reported Cases (報告数)",
        "week_slider": "Slider Week Position:",
        "backfill_header": "Data Management",
        "backfill_btn": "Run Full Backfill (2023 W19 → Present)",
        "nat_avg_label": "National Sentinel Average",
        "nat_total_label": "National Total Cases",
        "vs_last_week": "{val:+.2f} vs previous week",
        "legal_status_flu": "Flu Status",
        "trans_level_covid": "COVID-19 Status",
        "hist_trend": "Multi-Year Trend: {disease} ({metric})",
        "heatmap": "Prefectural Distribution ({year} Week {week})",
        "table_pref": "Prefecture",
        "status_warning": "Warning (警報 >=30) 🔴",
        "status_advisory": "Advisory (注意報 >=10) 🟡",
        "status_normal": "Baseline (<10) 🟢",
        "status_high": "Wave Peak (>=15) 🔴",
        "status_low": "Baseline (<15) 🟢",
        "chart_advisory": "Advisory (10.0)",
        "chart_warning": "Warning (30.0)",
        "slider_lbl": "Slider #",
        "week_lbl": "Week",
        "date_lbl": "Date",
        "click_hint": " (Click to jump to this week)",
        "no_data": "Database empty. Run the backfill button in the sidebar or upload a CSV."
    },
    "JA": {
        "title": "🇯🇵 日本感染症サーベイランス・ダッシュボード (2023–2026)",
        "subtitle": "2023年5月（5類移行・定点把握開始）から現在までの全記録アーカイブ",
        "sidebar_header": "設定・操作",
        "lang_selector": "言語 / Language:",
        "disease_selector": "対象疾患:",
        "metric_selector": "表示指標:",
        "metric_rate": "定点当たり報告数（定当）",
        "metric_count": "報告数（患者総数）",
        "week_slider": "スライダー週位置:",
        "backfill_header": "データ管理",
        "backfill_btn": "全履歴バックフィルを実行 (2023年19週〜)",
        "nat_avg_label": "全国定点当たり平均",
        "nat_total_label": "全国合計報告数",
        "vs_last_week": "前週比 {val:+.2f}",
        "legal_status_flu": "流行状況レベル",
        "trans_level_covid": "感染警戒レベル",
        "hist_trend": "全期間推移: {disease}（{metric}）",
        "heatmap": "都道府県別マップ ({year}年 第{week}週)",
        "table_pref": "都道府県",
        "status_warning": "警報レベル (>=30) 🔴",
        "status_advisory": "注意報レベル (>=10) 🟡",
        "status_normal": "平常レベル 🟢",
        "status_high": "警戒水準 (>=15) 🔴",
        "status_low": "平常水準 🟢",
        "chart_advisory": "注意報基準 (10.0)",
        "chart_warning": "警報基準 (30.0)",
        "slider_lbl": "スライダー番号",
        "week_lbl": "週",
        "date_lbl": "日付",
        "click_hint": " (クリックでこの週に移動)",
        "no_data": "データベースが空です。サイドバーのバックフィルを実行するかCSVを読み込んでください。"
    }
}

DISEASE_TRANSLATIONS = {
    "COVID-19": {"EN": "COVID-19", "JA": "新型コロナウイルス (COVID-19)"},
    "Influenza": {"EN": "Influenza", "JA": "インフルエンザ"}
}

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

# --- 2. CSV PARSER ---
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

# --- 3. MULTI-YEAR BACKFILL ENGINE ---
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
                    if recs:
                        break
            except Exception:
                pass

        if recs:
            c.executemany('''
                INSERT OR REPLACE INTO weekly_records 
                (year, week, jis_id, prefecture_jp, prefecture_en, disease, cases_count, cases_per_sentinel)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', recs)
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

def extract_selected_index(event_or_state):
    """Safely extracts the clicked slider index from a Plotly selection event."""
    if not event_or_state:
        return None
    sel = getattr(event_or_state, "selection", None)
    if sel is None and isinstance(event_or_state, dict):
        sel = event_or_state.get("selection", event_or_state)
    if not sel:
        return None
    pts = getattr(sel, "points", None)
    if pts is None and isinstance(sel, dict):
        pts = sel.get("points", [])
    if not pts or len(pts) == 0:
        return None
    first_pt = pts[0]
    c_data = getattr(first_pt, "customdata", None)
    if c_data is None and isinstance(first_pt, dict):
        c_data = first_pt.get("customdata")
    if c_data is not None and len(c_data) > 0:
        try:
            return int(c_data[0])
        except (ValueError, TypeError):
            pass
    if isinstance(first_pt, dict) and "point_index" in first_pt:
        return int(first_pt["point_index"])
    if hasattr(first_pt, "point_index"):
        return int(first_pt.point_index)
    return None

# --- 4. STREAMLIT APPLICATION ---
st.set_page_config(page_title="Japan Sentinel Archive", layout="wide")

init_db()
load_local_csvs()

# Language
st.sidebar.markdown("### Settings / 設定")
lang_select = st.sidebar.radio("Language / 言語:", ["English", "日本語"])
lang = "EN" if lang_select == "English" else "JA"
tx = L[lang]

# Backfill Controls in Sidebar
st.sidebar.markdown(f"### {tx['backfill_header']}")
if st.sidebar.button(tx["backfill_btn"]):
    p_bar = st.sidebar.progress(0)
    p_text = st.sidebar.empty()
    execute_backfill(p_bar, p_text)
    st.rerun()

# Safe Read from DB
conn = sqlite3.connect(DB_NAME)
df_all = pd.read_sql("SELECT * FROM weekly_records ORDER BY year ASC, week ASC", conn)
conn.close()

if df_all.empty:
    st.title(tx["title"])
    st.warning(tx["no_data"])
    st.info("Click **'Run Full Backfill'** in the sidebar to download the historical archive, or place `2026-41-teiten.csv` in this folder.")
    st.stop()

# Generate proper datetime representation
df_all['date'] = df_all.apply(lambda r: datetime.date.fromisocalendar(int(r['year']), int(r['week']), 5), axis=1)
df_all['date'] = pd.to_datetime(df_all['date'])
df_all['week_label'] = df_all.apply(lambda r: f"{r['year']} W{r['week']:02d}", axis=1)

# Sequence of unique available weeks
available_weeks = df_all[['year', 'week', 'week_label']].drop_duplicates().sort_values(by=['year', 'week']).reset_index(drop=True)
total_available = len(available_weeks)

# Fast mapping from (year, week) to slider index
week_to_idx = {
    (int(row['year']), int(row['week'])): idx 
    for idx, row in available_weeks.iterrows()
}

# Check if there is a pending index update from a click event
if "pending_week_slider_idx" in st.session_state:
    st.session_state.week_slider_idx = st.session_state.pop("pending_week_slider_idx")


# Ensure session state slider index is properly initialized
if "week_slider_idx" not in st.session_state:
    st.session_state.week_slider_idx = total_available - 1
elif st.session_state.week_slider_idx >= total_available:
    st.session_state.week_slider_idx = total_available - 1

# Filters
st.sidebar.markdown("---")
selected_disease_key = st.sidebar.radio(
    tx["disease_selector"],
    ["COVID-19", "Influenza"],
    format_func=lambda k: DISEASE_TRANSLATIONS[k][lang]
)

metric_type = st.sidebar.radio(
    tx["metric_selector"],
    ["rate", "count"],
    format_func=lambda k: tx["metric_rate"] if k == "rate" else tx["metric_count"]
)
val_col = "cases_per_sentinel" if metric_type == "rate" else "cases_count"

# Slider bound to session_state
slider_idx = st.sidebar.slider(
    f"{tx['week_slider']} (0 – {total_available - 1})",
    min_value=0,
    max_value=total_available - 1,
    key="week_slider_idx"
)

active_year = int(available_weeks.iloc[slider_idx]['year'])
active_week = int(available_weeks.iloc[slider_idx]['week'])

st.sidebar.caption(f"📍 Active: **Slider #{slider_idx}** → `{active_year}-W{active_week:02d}`")

df_disease = df_all[df_all['disease'] == selected_disease_key].copy()

# Header
st.title(tx["title"])
st.caption(tx["subtitle"])

# National Aggregates
if metric_type == "rate":
    nat_series = df_disease.groupby(['year', 'week', 'date'])[val_col].mean().reset_index()
else:
    nat_series = df_disease.groupby(['year', 'week', 'date'])[val_col].sum().reset_index()
nat_series = nat_series.sort_values(by='date').reset_index(drop=True)

# Attach slider index and week tag
nat_series['slider_idx'] = nat_series.apply(lambda r: week_to_idx.get((int(r['year']), int(r['week'])), 0), axis=1)
nat_series['week_tag'] = nat_series.apply(lambda r: f"{int(r['year'])}-W{int(r['week']):02d}", axis=1)

# Metrics for the selected slider week
curr_row = nat_series[(nat_series['year'] == active_year) & (nat_series['week'] == active_week)]
curr_val = curr_row[val_col].iloc[0] if not curr_row.empty else 0.0

curr_idx = nat_series.index[(nat_series['year'] == active_year) & (nat_series['week'] == active_week)].tolist()
prev_val = nat_series.iloc[curr_idx[0] - 1][val_col] if curr_idx and curr_idx[0] > 0 else curr_val
val_diff = curr_val - prev_val

c1, c2, c3 = st.columns(3)
val_label = tx["nat_avg_label"] if metric_type == "rate" else tx["nat_total_label"]
c1.metric(val_label, f"{curr_val:.2f}" if metric_type == "rate" else f"{int(curr_val):,}", tx["vs_last_week"].format(val=val_diff), delta_color="inverse")

rate_row = df_disease[(df_disease['year'] == active_year) & (df_disease['week'] == active_week)]
curr_rate = rate_row['cases_per_sentinel'].mean() if not rate_row.empty else 0.0

if selected_disease_key == "Influenza":
    status_str = tx["status_warning"] if curr_rate >= 30 else tx["status_advisory"] if curr_rate >= 10 else tx["status_normal"]
    c2.metric(tx["legal_status_flu"], status_str)
else:
    status_str = tx["status_high"] if curr_rate >= 15 else tx["status_low"]
    c2.metric(tx["trans_level_covid"], status_str)

c3.metric("Selected Period", f"{active_year} Week {active_week:02d}", f"Slider #{slider_idx} of {total_available - 1}")

# Multi-Year Trend Chart
metric_name_display = tx["metric_rate"] if metric_type == "rate" else tx["metric_count"]
st.subheader(tx["hist_trend"].format(disease=DISEASE_TRANSLATIONS[selected_disease_key][lang], metric=metric_name_display))

# Build figure with explicit markers and custom data
fig_curve = px.line(
    nat_series, 
    x='date', 
    y=val_col,
    markers=True,
    custom_data=['slider_idx', 'week_tag', 'year', 'week'],
    labels={'date': 'Date', val_col: metric_name_display},
    template="plotly_white"
)

hover_val_fmt = ":.2f" if metric_type == "rate" else ":,d"
fig_curve.update_traces(
    mode='lines+markers',
    marker=dict(size=7, opacity=0.85),
    line=dict(color="#e63946" if selected_disease_key == "COVID-19" else "#457b9d", width=2.5),
    hovertemplate=(
        f"<b>{tx['slider_lbl']}: %{{customdata[0]}}</b>{tx['click_hint']}<br>" +
        f"<b>{tx['week_lbl']}: %{{customdata[1]}}</b><br>" +
        f"{tx['date_lbl']}: %{{x|%Y-%m-%d}}<br>" +
        f"{metric_name_display}: %{{y{hover_val_fmt}}}<extra></extra>"
    )
)

# Enable single-click point selection
fig_curve.update_layout(
    clickmode='event+select',
    hovermode='closest'
)

# Vertical marker for selected slider week
active_date_val = curr_row['date'].iloc[0] if not curr_row.empty else None
if active_date_val is not None:
    fig_curve.add_vline(
        x=active_date_val, 
        line_dash="dash", 
        line_color="#222222", 
        annotation_text=f"Selected: Slider #{slider_idx} ({active_year}-W{active_week:02d})",
        annotation_position="top left"
    )

if metric_type == "rate":
    if selected_disease_key == "Influenza":
        fig_curve.add_hline(y=10.0, line_dash="dash", line_color="orange", annotation_text=tx["chart_advisory"])
        fig_curve.add_hline(y=30.0, line_dash="dash", line_color="red", annotation_text=tx["chart_warning"])
    else:
        fig_curve.add_hline(y=15.0, line_dash="dot", line_color="red", annotation_text="Wave Threshold (15.0)")

# Render Chart and capture click selection
chart_event = st.plotly_chart(
    fig_curve,
    width='stretch',
    key="trend_chart",
    on_select="rerun",
    selection_mode="points"
)

# Trap click event and immediately update state
clicked_idx = extract_selected_index(chart_event)
if clicked_idx is not None and clicked_idx != st.session_state.week_slider_idx:
    if st.session_state.get("week_slider_idx") != clicked_idx:
        st.session_state.pending_week_slider_idx = clicked_idx
        st.rerun()

# Heatmap & Table for Selected Week
st.subheader(tx["heatmap"].format(year=active_year, week=active_week))
df_active = df_disease[(df_disease['year'] == active_year) & (df_disease['week'] == active_week)].copy()
df_active['display_pref'] = df_active['prefecture_en'] if lang == "EN" else df_active['prefecture_jp']

geojson_data = get_japan_geojson()
col_map, col_table = st.columns([3, 2])

with col_map:
    if geojson_data and not df_active.empty:
        fig_map = px.choropleth(
            df_active,
            geojson=geojson_data,
            locations="prefecture_jp",
            featureidkey="properties.nam_ja",
            color=val_col,
            color_continuous_scale="Reds",
            range_color=(0, max(20, float(df_active[val_col].max()))),
            hover_name="display_pref",
            hover_data={"prefecture_jp": False, "cases_per_sentinel": ":.2f", "cases_count": ":,.0f"},
            labels={"cases_per_sentinel": tx["metric_rate"], "cases_count": tx["metric_count"]}
        )
        fig_map.update_geos(fitbounds="locations", visible=False)
        fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig_map, width='stretch')
    else:
        st.bar_chart(df_active.set_index('display_pref')[val_col])

with col_table:
    sorted_df = df_active.sort_values(by=val_col, ascending=False)[['display_pref', 'cases_per_sentinel', 'cases_count']]
    sorted_df.columns = [tx["table_pref"], tx["metric_rate"], tx["metric_count"]]
    st.dataframe(sorted_df.reset_index(drop=True), height=440, width='stretch')
