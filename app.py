# app.py
# Run:
#   cd "C:\Users\nandi\OneDrive\Desktop\Sushil\wellness_app"
#   streamlit run app.py
#
# Fixes:
# - DB migration included (avoids missing "person" column)
# - Fixes StreamlitDuplicateElementKey by adding a unique `context_key`
#   so the same logger can be used in multiple tabs safely.

import os
import sqlite3
from datetime import datetime, date, timedelta

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st



# =========================
# 0) APP CONFIG + THEME
# =========================
st.set_page_config(page_title="Wellness Lab", layout="wide", page_icon="🧠")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "wellness.db")
os.makedirs(DATA_DIR, exist_ok=True)

CUSTOM_CSS = """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1300px;}
h1, h2, h3 {letter-spacing: -0.02em;}
.card {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  border-radius: 18px;
  padding: 16px 16px;
  box-shadow: 0 12px 30px rgba(0,0,0,0.18);
}
.small {opacity: 0.85; font-size: 0.92rem;}
.badge {
  display:inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.18);
  border: 1px solid rgba(99, 102, 241, 0.35);
  font-size: 0.85rem;
}
hr {opacity: 0.25;}
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
.js-plotly-plot, .plotly, .plot-container {border-radius: 18px;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================
# 1) DATABASE (single-file)
# =========================
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """
    Creates the latest schema AND migrates older schemas in place.
    Avoids: 'no such column: person'
    """
    conn = db()

    # Create latest schema
    conn.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person TEXT NOT NULL DEFAULT 'Sushil',
        log_date TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        meal_time TEXT NOT NULL,
        dish TEXT NOT NULL,
        grams REAL NOT NULL,
        carbs_g REAL,
        protein_g REAL,
        fat_g REAL,
        kcal REAL,
        gerd REAL,
        notes TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person TEXT NOT NULL DEFAULT 'Sushil',
        log_date TEXT NOT NULL,
        weight_kg REAL,
        sleep_hours REAL,
        exercise_min REAL,
        mood INTEGER,
        stress INTEGER,
        gerd_symptom INTEGER,
        glucose_mgdl REAL,
        period_day INTEGER,
        period_flow TEXT,
        period_symptoms TEXT,
        insulin_units REAL,
        extra_notes TEXT,
        UNIQUE(person, log_date)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        person TEXT NOT NULL,
        goal_type TEXT NOT NULL,
        start_date TEXT NOT NULL,
        start_weight REAL,
        target_weight REAL,
        target_date TEXT NOT NULL,
        kcal_adjust REAL,
        protein_target REAL,
        PRIMARY KEY(person, goal_type)
    )
    """)

    # ----- MIGRATIONS -----
    def ensure_column(table, col, coldef_sql):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef_sql}")

    # logs: older DB might miss person/notes/etc
    ensure_column("logs", "person", "TEXT NOT NULL DEFAULT 'Sushil'")
    ensure_column("logs", "log_date", "TEXT")
    ensure_column("logs", "meal_type", "TEXT")
    ensure_column("logs", "meal_time", "TEXT")
    ensure_column("logs", "dish", "TEXT")
    ensure_column("logs", "grams", "REAL")
    ensure_column("logs", "carbs_g", "REAL")
    ensure_column("logs", "protein_g", "REAL")
    ensure_column("logs", "fat_g", "REAL")
    ensure_column("logs", "kcal", "REAL")
    ensure_column("logs", "gerd", "REAL")
    ensure_column("logs", "notes", "TEXT")

    # daily: older DB might miss person and newer fields
    ensure_column("daily", "person", "TEXT NOT NULL DEFAULT 'Sushil'")
    ensure_column("daily", "log_date", "TEXT")
    ensure_column("daily", "weight_kg", "REAL")
    ensure_column("daily", "sleep_hours", "REAL")
    ensure_column("daily", "exercise_min", "REAL")
    ensure_column("daily", "mood", "INTEGER")
    ensure_column("daily", "stress", "INTEGER")
    ensure_column("daily", "gerd_symptom", "INTEGER")
    ensure_column("daily", "glucose_mgdl", "REAL")
    ensure_column("daily", "period_day", "INTEGER")
    ensure_column("daily", "period_flow", "TEXT")
    ensure_column("daily", "period_symptoms", "TEXT")
    ensure_column("daily", "insulin_units", "REAL")
    ensure_column("daily", "extra_notes", "TEXT")

    conn.commit()
    conn.close()

init_db()

def upsert_daily(person, log_date, **kwargs):
    conn = db()
    cols = [
        "weight_kg","sleep_hours","exercise_min","mood","stress","gerd_symptom","glucose_mgdl",
        "period_day","period_flow","period_symptoms","insulin_units","extra_notes"
    ]
    data = {c: kwargs.get(c, None) for c in cols}

    row = conn.execute("SELECT id FROM daily WHERE person=? AND log_date=?", (person, log_date)).fetchone()
    if row:
        sets = ", ".join([f"{c}=?" for c in cols])
        conn.execute(
            f"UPDATE daily SET {sets} WHERE person=? AND log_date=?",
            (*[data[c] for c in cols], person, log_date)
        )
    else:
        conn.execute("""
            INSERT INTO daily(
                person, log_date, weight_kg, sleep_hours, exercise_min, mood, stress, gerd_symptom,
                glucose_mgdl, period_day, period_flow, period_symptoms, insulin_units, extra_notes
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            person, log_date, data["weight_kg"], data["sleep_hours"], data["exercise_min"], data["mood"], data["stress"],
            data["gerd_symptom"], data["glucose_mgdl"], data["period_day"], data["period_flow"], data["period_symptoms"],
            data["insulin_units"], data["extra_notes"]
        ))
    conn.commit()
    conn.close()

def add_meal_log(person, log_date, meal_type, meal_time, dish, grams, macros, notes=""):
    conn = db()
    conn.execute("""
        INSERT INTO logs(
            person, log_date, meal_type, meal_time, dish, grams,
            carbs_g, protein_g, fat_g, kcal, gerd, notes
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        person, log_date, meal_type, meal_time, dish, float(grams),
        float(macros["carbs_g"]), float(macros["protein_g"]), float(macros["fat_g"]),
        float(macros["kcal"]), float(macros["gerd"]), notes
    ))
    conn.commit()
    conn.close()

def load_logs(person, days=60):
    conn = db()
    since = (date.today() - timedelta(days=days)).isoformat()
    df = pd.read_sql_query("""
        SELECT * FROM logs
        WHERE person=? AND log_date>=?
        ORDER BY log_date DESC, meal_time DESC
    """, conn, params=(person, since))
    conn.close()
    return df

def load_daily(person, days=90):
    conn = db()
    since = (date.today() - timedelta(days=days)).isoformat()
    df = pd.read_sql_query("""
        SELECT * FROM daily
        WHERE person=? AND log_date>=?
        ORDER BY log_date ASC
    """, conn, params=(person, since))
    conn.close()
    return df

def set_goal(person, goal_type, start_weight, target_weight, target_date, kcal_adjust, protein_target):
    conn = db()
    conn.execute("""
        INSERT INTO goals(person, goal_type, start_date, start_weight, target_weight, target_date, kcal_adjust, protein_target)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(person, goal_type)
        DO UPDATE SET start_date=excluded.start_date, start_weight=excluded.start_weight,
                      target_weight=excluded.target_weight, target_date=excluded.target_date,
                      kcal_adjust=excluded.kcal_adjust, protein_target=excluded.protein_target
    """, (
        person, goal_type, date.today().isoformat(), float(start_weight), float(target_weight),
        target_date, float(kcal_adjust), float(protein_target)
    ))
    conn.commit()
    conn.close()

def get_goal(person, goal_type):
    conn = db()
    row = conn.execute("""
        SELECT start_date, start_weight, target_weight, target_date, kcal_adjust, protein_target
        FROM goals WHERE person=? AND goal_type=?
    """, (person, goal_type)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "start_date": row[0],
        "start_weight": row[1],
        "target_weight": row[2],
        "target_date": row[3],
        "kcal_adjust": row[4],
        "protein_target": row[5],
    }

# =========================
# 2) FOOD + DISH DATABASE
# =========================
ING_DB = {
    "egg_whole":         {"protein": 12.6, "carbs": 1.1,  "fat": 10.0, "kcal": 143, "gerd": 0.05},
    "egg_white":         {"protein": 11.0, "carbs": 0.7,  "fat": 0.2,  "kcal": 52,  "gerd": 0.02},
    "milk_2pct":         {"protein": 3.4,  "carbs": 4.8,  "fat": 2.0,  "kcal": 50,  "gerd": 0.05},
    "curd_plain":        {"protein": 4.0,  "carbs": 4.0,  "fat": 3.0,  "kcal": 60,  "gerd": -0.03},
    "yogurt_plain":      {"protein": 10.0, "carbs": 6.0,  "fat": 3.0,  "kcal": 100, "gerd": -0.05},
    "buttermilk":        {"protein": 3.0,  "carbs": 5.0,  "fat": 1.0,  "kcal": 35,  "gerd": -0.02},
    "whey_powder":       {"protein": 80.0, "carbs": 8.0,  "fat": 6.0,  "kcal": 400, "gerd": 0.05},

    "rice_cooked":       {"protein": 2.7,  "carbs": 28.0, "fat": 0.3,  "kcal": 130, "gerd": 0.00},
    "brown_rice_cooked": {"protein": 2.6,  "carbs": 23.0, "fat": 1.0,  "kcal": 110, "gerd": 0.00},
    "poha_cooked":       {"protein": 2.0,  "carbs": 20.0, "fat": 3.0,  "kcal": 115, "gerd": 0.05},
    "upma_cooked":       {"protein": 3.0,  "carbs": 18.0, "fat": 4.0,  "kcal": 120, "gerd": 0.05},
    "oats_cooked":       {"protein": 2.4,  "carbs": 12.0, "fat": 1.4,  "kcal": 71,  "gerd": -0.05},

    "roti":              {"protein": 8.0,  "carbs": 45.0, "fat": 3.0,  "kcal": 250, "gerd": 0.05},
    "phulka":            {"protein": 8.0,  "carbs": 47.0, "fat": 2.5,  "kcal": 240, "gerd": 0.05},
    "paratha":           {"protein": 7.0,  "carbs": 40.0, "fat": 12.0, "kcal": 300, "gerd": 0.15},
    "thepla":            {"protein": 8.0,  "carbs": 40.0, "fat": 8.0,  "kcal": 260, "gerd": 0.12},
    "bread":             {"protein": 9.0,  "carbs": 49.0, "fat": 3.2,  "kcal": 265, "gerd": 0.10},

    "dal_cooked":        {"protein": 9.0,  "carbs": 20.0, "fat": 0.5,  "kcal": 120, "gerd": 0.05},
    "rajma_cooked":      {"protein": 8.5,  "carbs": 22.0, "fat": 0.7,  "kcal": 127, "gerd": 0.08},
    "chole_cooked":      {"protein": 9.0,  "carbs": 27.0, "fat": 2.5,  "kcal": 164, "gerd": 0.12},
    "moong_sprouts":     {"protein": 3.0,  "carbs": 6.0,  "fat": 0.2,  "kcal": 35,  "gerd": 0.02},

    "chicken_cooked":    {"protein": 27.0, "carbs": 0.0,  "fat": 4.0,  "kcal": 165, "gerd": 0.05},
    "fish_cooked":       {"protein": 22.0, "carbs": 0.0,  "fat": 5.0,  "kcal": 130, "gerd": 0.05},
    "paneer":            {"protein": 18.0, "carbs": 2.0,  "fat": 20.0, "kcal": 265, "gerd": 0.10},
    "tofu":              {"protein": 8.0,  "carbs": 2.0,  "fat": 5.0,  "kcal": 80,  "gerd": 0.03},

    "oil":               {"protein": 0.0,  "carbs": 0.0,  "fat": 100.0,"kcal": 900, "gerd": 0.20},
    "ghee":              {"protein": 0.0,  "carbs": 0.0,  "fat": 100.0,"kcal": 900, "gerd": 0.22},

    "veg_curry":         {"protein": 2.0,  "carbs": 8.0,  "fat": 4.0,  "kcal": 80,  "gerd": 0.10},
    "bhaji":             {"protein": 2.5,  "carbs": 10.0, "fat": 6.0,  "kcal": 105, "gerd": 0.12},
    "sambar":            {"protein": 4.0,  "carbs": 10.0, "fat": 2.0,  "kcal": 70,  "gerd": 0.08},

    "banana":            {"protein": 1.1,  "carbs": 23.0, "fat": 0.3,  "kcal": 89,  "gerd": -0.03},
    "fruit_mixed":       {"protein": 0.8,  "carbs": 14.0, "fat": 0.2,  "kcal": 60,  "gerd": -0.04},
    "nuts_mixed":        {"protein": 18.0, "carbs": 16.0, "fat": 50.0, "kcal": 600, "gerd": 0.10},

    "dhokla":            {"protein": 7.0,  "carbs": 25.0, "fat": 4.0,  "kcal": 160, "gerd": 0.10},
    "khandvi":           {"protein": 8.0,  "carbs": 18.0, "fat": 6.0,  "kcal": 160, "gerd": 0.10},
    "fafda":             {"protein": 7.0,  "carbs": 40.0, "fat": 18.0, "kcal": 340, "gerd": 0.25},
    "handvo":            {"protein": 8.0,  "carbs": 22.0, "fat": 9.0,  "kcal": 210, "gerd": 0.18},
    "khakhra":           {"protein": 10.0, "carbs": 65.0, "fat": 8.0,  "kcal": 360, "gerd": 0.10},
    "undhiyu":           {"protein": 3.0,  "carbs": 12.0, "fat": 7.0,  "kcal": 120, "gerd": 0.12},
    "sev":               {"protein": 12.0, "carbs": 50.0, "fat": 25.0, "kcal": 470, "gerd": 0.25},

    "idli":              {"protein": 4.0,  "carbs": 20.0, "fat": 1.0,  "kcal": 100, "gerd": 0.05},
    "dosa":              {"protein": 5.0,  "carbs": 25.0, "fat": 6.0,  "kcal": 170, "gerd": 0.10},

    "pav_bhaji":         {"protein": 6.0,  "carbs": 25.0, "fat": 8.0,  "kcal": 190, "gerd": 0.25},
    "vada_pav":          {"protein": 6.0,  "carbs": 30.0, "fat": 12.0, "kcal": 250, "gerd": 0.30},
    "samosa":            {"protein": 5.0,  "carbs": 30.0, "fat": 12.0, "kcal": 260, "gerd": 0.30},

    "pizza":             {"protein": 11.0, "carbs": 33.0, "fat": 10.0, "kcal": 285, "gerd": 0.30},
    "burger":            {"protein": 13.0, "carbs": 24.0, "fat": 13.0, "kcal": 250, "gerd": 0.30},
    "fries":             {"protein": 3.4,  "carbs": 41.0, "fat": 15.0, "kcal": 312, "gerd": 0.35},

    "black_coffee":      {"protein": 0.1,  "carbs": 0.0,  "fat": 0.0,  "kcal": 2,   "gerd": 0.20},
    "tea":               {"protein": 0.5,  "carbs": 2.0,  "fat": 0.5,  "kcal": 15,  "gerd": 0.10},
}

DISH_RECIPES = {
    "omelette":           [("egg_whole", 120), ("oil", 5)],
    "boiled_eggs_2":      [("egg_whole", 100)],
    "oats_bowl":          [("oats_cooked", 300), ("milk_2pct", 200), ("banana", 120)],
    "poha":               [("poha_cooked", 300), ("oil", 5)],
    "upma":               [("upma_cooked", 300), ("oil", 5)],
    "idli_sambar":        [("idli", 200), ("sambar", 250)],
    "dosa_sambar":        [("dosa", 180), ("sambar", 250)],

    "dal_rice":           [("dal_cooked", 250), ("rice_cooked", 250), ("oil", 5)],
    "rajma_rice":         [("rajma_cooked", 250), ("rice_cooked", 250), ("oil", 5)],
    "chole_rice":         [("chole_cooked", 250), ("rice_cooked", 250), ("oil", 5)],
    "roti_veg_curry":     [("roti", 160), ("veg_curry", 250)],
    "roti_dal":           [("roti", 160), ("dal_cooked", 250)],
    "paratha_curd":       [("paratha", 180), ("curd_plain", 200)],
    "thepla_curd":        [("thepla", 160), ("curd_plain", 200)],

    "egg_curry":          [("egg_whole", 120), ("veg_curry", 200), ("oil", 10)],
    "chicken_curry_rice": [("chicken_cooked", 150), ("veg_curry", 200), ("rice_cooked", 250), ("oil", 10)],
    "biryani_chicken":    [("rice_cooked", 300), ("chicken_cooked", 150), ("oil", 12)],
    "paneer_curry_roti":  [("paneer", 150), ("veg_curry", 200), ("roti", 160)],
    "tofu_curry_roti":    [("tofu", 180), ("veg_curry", 200), ("roti", 160)],

    "dhokla_plate":       [("dhokla", 200)],
    "khandvi_plate":      [("khandvi", 200)],
    "handvo_slice":       [("handvo", 180)],
    "fafda":              [("fafda", 120)],
    "khakhra_snack":      [("khakhra", 60)],
    "undhiyu_roti":       [("undhiyu", 300), ("roti", 160)],
    "sev_snack":          [("sev", 40)],

    "pav_bhaji":          [("pav_bhaji", 350)],
    "vada_pav":           [("vada_pav", 200)],
    "samosa":             [("samosa", 150)],

    "protein_shake":      [("whey_powder", 30), ("milk_2pct", 250)],
    "banana_milk_shake":  [("milk_2pct", 350), ("banana", 180)],
    "curd_bowl":          [("curd_plain", 300), ("banana", 120), ("nuts_mixed", 25)],

    "pizza":              [("pizza", 250)],
    "burger":             [("burger", 220)],
    "fries":              [("fries", 180)],
}

DISH_CATEGORIES = {
    "Breakfast": [
        "omelette","boiled_eggs_2","oats_bowl","poha","upma","idli_sambar","dosa_sambar","protein_shake","banana_milk_shake"
    ],
    "Lunch": [
        "dal_rice","rajma_rice","chole_rice","roti_veg_curry","roti_dal","egg_curry",
        "chicken_curry_rice","biryani_chicken","paneer_curry_roti","tofu_curry_roti"
    ],
    "Dinner": [
        "dal_rice","roti_veg_curry","roti_dal","egg_curry","chicken_curry_rice",
        "paneer_curry_roti","tofu_curry_roti","paratha_curd","thepla_curd"
    ],
    "Snacks": [
        "dhokla_plate","khandvi_plate","handvo_slice","khakhra_snack","sev_snack","fafda",
        "pav_bhaji","vada_pav","samosa","pizza","burger","fries","curd_bowl"
    ],
}

def macros_for_dish(dish_name, grams):
    recipe = DISH_RECIPES.get(dish_name, [])
    if not recipe:
        return {"carbs_g": 0.0, "protein_g": 0.0, "fat_g": 0.0, "kcal": 0.0, "gerd": 0.0}

    ref_total = sum(g for _, g in recipe)
    if ref_total <= 0:
        ref_total = 1.0
    scale = float(grams) / float(ref_total)

    carbs = protein = fat = kcal = gerd = 0.0
    for ing, g in recipe:
        base = ING_DB.get(ing, None)
        if not base:
            continue
        used_g = g * scale
        factor = used_g / 100.0
        carbs += base["carbs"] * factor
        protein += base["protein"] * factor
        fat += base["fat"] * factor
        kcal += base["kcal"] * factor
        gerd += base["gerd"] * (used_g / ref_total)

    return {
        "carbs_g": round(carbs, 1),
        "protein_g": round(protein, 1),
        "fat_g": round(fat, 1),
        "kcal": round(kcal, 0),
        "gerd": float(np.clip(gerd, -0.3, 1.0)),
    }

# =========================
# 3) WELLNESS / PERFORMANCE MODELS
# =========================
def clamp01(x): return float(np.clip(x, 0.0, 1.0))

def wellness_index_generic(kcal, protein_g, sleep_h, exercise_min, stress_0_10):
    sleep_score = clamp01(1 - abs(sleep_h - 7.5)/4.0)
    exercise_score = clamp01(min(exercise_min, 60)/60.0)
    stress_score = clamp01(1 - (stress_0_10/10.0))
    protein_score = clamp01(min(protein_g, 120)/120.0)
    kcal_score = clamp01(min(kcal, 3200)/3200.0)

    score = (
        0.30*sleep_score +
        0.20*exercise_score +
        0.25*stress_score +
        0.15*protein_score +
        0.10*kcal_score
    )
    return round(100*score, 1)

# =========================
# 4) PLOTS
# =========================
def nice_line(df, x, y, title, ytitle=None):
    if df.empty:
        return None
    fig = px.line(df, x=x, y=y, markers=True, title=title)
    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=16, r=16, t=52, b=16),
        title=dict(x=0.02),
        font=dict(size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_traces(line=dict(width=3))
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title=ytitle or y)
    return fig

def nice_area_macros(df, title="Macros per day (g)"):
    if df.empty:
        return None
    use = df.copy()
    use["log_date"] = pd.to_datetime(use["log_date"])
    daily = use.groupby("log_date")[["carbs_g","protein_g","fat_g"]].sum().reset_index()
    daily = daily.sort_values("log_date")

    fig = go.Figure()
    for col in ["protein_g","carbs_g","fat_g"]:
        fig.add_trace(go.Scatter(
            x=daily["log_date"], y=daily[col], mode="lines", stackgroup="one",
            name=col.replace("_g","").title(), line=dict(width=2)
        ))
    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=16, r=16, t=52, b=16),
        title=dict(text=title, x=0.02),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="grams"),
    )
    return fig

# =========================
# 5) UI BLOCKS
# =========================
def header_block(name, subtitle, tag):
    st.markdown(f"""
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
        <div>
          <h2 style="margin:0;">{name}</h2>
          <div class="small">{subtitle}</div>
        </div>
        <div class="badge">{tag}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def meal_logger(person, enable_gerd=True, enable_t1d=False, context_key="main"):
    st.subheader("Log a meal")

    cols = st.columns([1.1, 1.0, 1.0, 1.2, 1.0])
    with cols[0]:
        log_date = st.date_input("Date", value=date.today(), key=f"{person}_{context_key}_meal_date")
    with cols[1]:
        meal_type = st.selectbox("Meal", ["Breakfast","Lunch","Dinner","Snacks"], key=f"{person}_{context_key}_meal_type")
    with cols[2]:
        meal_time = st.time_input("Time", value=datetime.now().time().replace(second=0, microsecond=0), key=f"{person}_{context_key}_meal_time")
    with cols[3]:
        dish = st.selectbox("Dish", DISH_CATEGORIES.get(meal_type, list(DISH_RECIPES.keys())), key=f"{person}_{context_key}_dish")
    with cols[4]:
        grams = st.number_input("Weight (g)", min_value=10, max_value=2500, value=300, step=10, key=f"{person}_{context_key}_grams")

    st.caption("Tip: weigh the plate/bowl using a kitchen scale. If you don't know, estimate (300g bowl, 180g sandwich).")

    override = False
    carbs_override = protein_override = fat_override = kcal_override = 0.0
    if enable_t1d:
        with st.expander("Type 1: Use nutrients from photo app (optional)"):
            override = st.checkbox("Override dish macros with my app values", key=f"{person}_{context_key}_override")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                carbs_override = st.number_input("Carbs (g)", min_value=0.0, max_value=600.0, value=0.0, step=1.0, key=f"{person}_{context_key}_carb_ov")
            with c2:
                protein_override = st.number_input("Protein (g)", min_value=0.0, max_value=300.0, value=0.0, step=1.0, key=f"{person}_{context_key}_prot_ov")
            with c3:
                fat_override = st.number_input("Fat (g)", min_value=0.0, max_value=300.0, value=0.0, step=1.0, key=f"{person}_{context_key}_fat_ov")
            with c4:
                kcal_override = st.number_input("Calories (kcal)", min_value=0.0, max_value=4000.0, value=0.0, step=10.0, key=f"{person}_{context_key}_kcal_ov")

    notes = st.text_input("Notes (optional)", value="", key=f"{person}_{context_key}_meal_notes")

    if override:
        macros = {"carbs_g": float(carbs_override), "protein_g": float(protein_override),
                  "fat_g": float(fat_override), "kcal": float(kcal_override), "gerd": 0.0}
    else:
        macros = macros_for_dish(dish, grams)

    if not enable_gerd:
        macros["gerd"] = 0.0

    st.markdown(
        f"""
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><b>{dish}</b> · {meal_type} · {meal_time.strftime("%H:%M")} · {grams:.0f} g</div>
            <div class="badge">{person}</div>
          </div>
          <hr/>
          <div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:10px;">
            <div><div class="small">Carbs</div><div style="font-size:1.2rem;"><b>{macros['carbs_g']}</b> g</div></div>
            <div><div class="small">Protein</div><div style="font-size:1.2rem;"><b>{macros['protein_g']}</b> g</div></div>
            <div><div class="small">Fat</div><div style="font-size:1.2rem;"><b>{macros['fat_g']}</b> g</div></div>
            <div><div class="small">Calories</div><div style="font-size:1.2rem;"><b>{int(macros['kcal'])}</b></div></div>
            <div><div class="small">GERD</div><div style="font-size:1.2rem;"><b>{macros['gerd']:.2f}</b></div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("Save meal", key=f"{person}_{context_key}_save_meal"):
        add_meal_log(
            person=person,
            log_date=log_date.isoformat(),
            meal_type=meal_type,
            meal_time=meal_time.strftime("%H:%M"),
            dish=dish,
            grams=grams,
            macros=macros,
            notes=notes or ""
        )
        st.success("Meal saved.")

def daily_logger(person, enable_gerd=True, enable_t1d=False, enable_period=False, context_key="main"):
    st.subheader("Daily check-in")

    c = st.columns([1.1, 1, 1, 1, 1, 1])
    with c[0]:
        log_date = st.date_input("Date", value=date.today(), key=f"{person}_{context_key}_daily_date")
    with c[1]:
        weight_kg = st.number_input("Weight (kg)", min_value=25.0, max_value=200.0,
                                    value=48.0 if person=="Sushil" else 55.0, step=0.1, key=f"{person}_{context_key}_w")
    with c[2]:
        sleep_h = st.number_input("Sleep (hours)", min_value=0.0, max_value=14.0, value=7.0, step=0.5, key=f"{person}_{context_key}_sleep")
    with c[3]:
        exercise_min = st.number_input("Exercise (minutes)", min_value=0.0, max_value=600.0, value=30.0, step=5.0, key=f"{person}_{context_key}_exmin")
    with c[4]:
        mood = st.slider("Mood", 0, 10, 6, key=f"{person}_{context_key}_mood")
    with c[5]:
        stress = st.slider("Stress", 0, 10, 4, key=f"{person}_{context_key}_stress")

    gerd_symptom = None
    glucose = None
    insulin_units = None
    period_day = None
    period_flow = None
    period_symptoms = None

    extras = st.columns([1,1,1,1])
    i = 0
    if enable_gerd:
        with extras[i]:
            gerd_symptom = st.slider("GERD symptoms", 0, 10, 3, key=f"{person}_{context_key}_gerd")
        i += 1

    if enable_t1d:
        with extras[i]:
            glucose = st.number_input("Glucose (mg/dL)", min_value=20.0, max_value=600.0, value=120.0, step=1.0, key=f"{person}_{context_key}_glu")
        i += 1
        with extras[i]:
            insulin_units = st.number_input("Total insulin today (units)", min_value=0.0, max_value=200.0, value=0.0, step=0.5, key=f"{person}_{context_key}_ins")
        i += 1

    if enable_period:
        with st.expander("Period tracker"):
            p1, p2 = st.columns([1,1])
            with p1:
                period_day = st.number_input("Cycle day (1..)", min_value=0, max_value=60, value=0, step=1, key=f"{person}_{context_key}_pday")
                period_flow = st.selectbox("Flow", ["", "Spotting", "Light", "Medium", "Heavy"], index=0, key=f"{person}_{context_key}_pflow")
            with p2:
                period_symptoms = st.text_area("Symptoms", value="", height=80, key=f"{person}_{context_key}_psym")

    extra_notes = st.text_area("Notes", value="", height=90, key=f"{person}_{context_key}_notes")

    if st.button("Save daily check-in", key=f"{person}_{context_key}_save_daily"):
        upsert_daily(
            person=person,
            log_date=log_date.isoformat(),
            weight_kg=weight_kg,
            sleep_hours=sleep_h,
            exercise_min=exercise_min,
            mood=mood,
            stress=stress,
            gerd_symptom=gerd_symptom if enable_gerd else None,
            glucose_mgdl=glucose if enable_t1d else None,
            insulin_units=insulin_units if enable_t1d else None,
            period_day=period_day if enable_period else None,
            period_flow=period_flow if enable_period else None,
            period_symptoms=period_symptoms if enable_period else None,
            extra_notes=extra_notes
        )
        st.success("Daily check-in saved.")

def goal_panel(person, goal_type, default_start, default_target, days_default, label, context_key="main"):
    st.subheader(label)
    g = get_goal(person, goal_type)

    c1, c2, c3, c4 = st.columns([1,1,1,1])
    with c1:
        start_w = st.number_input("Start weight (kg)", min_value=25.0, max_value=200.0,
                                  value=float(g["start_weight"]) if g else float(default_start), step=0.1, key=f"{person}_{context_key}_{goal_type}_sw")
    with c2:
        target_w = st.number_input("Target weight (kg)", min_value=25.0, max_value=200.0,
                                   value=float(g["target_weight"]) if g else float(default_target), step=0.1, key=f"{person}_{context_key}_{goal_type}_tw")
    with c3:
        target_d = st.date_input("Target date", value=(date.today()+timedelta(days=days_default)) if not g else date.fromisoformat(g["target_date"]),
                                 key=f"{person}_{context_key}_{goal_type}_td")
    with c4:
        protein_target = st.number_input("Protein target (g/day)", min_value=20.0, max_value=250.0,
                                         value=float(g["protein_target"]) if g else 110.0, step=5.0, key=f"{person}_{context_key}_{goal_type}_pt")

    kcal_adjust = st.slider("Daily calorie adjustment", -800, 1200, 300 if goal_type=="gain" else -300,
                            step=50, key=f"{person}_{context_key}_{goal_type}_kc")

    if st.button("Save goal", key=f"{person}_{context_key}_{goal_type}_save"):
        set_goal(person, goal_type, start_w, target_w, target_d.isoformat(), kcal_adjust, protein_target)
        st.success("Goal saved.")

    days_left = max(1, (target_d - date.today()).days)
    kg_change = target_w - start_w
    per_day = kg_change / days_left

    st.markdown(f"""
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div><b>Plan summary</b></div>
        <div class="badge">{goal_type.upper()}</div>
      </div>
      <hr/>
      <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:10px;">
        <div><div class="small">Days left</div><div style="font-size:1.2rem;"><b>{days_left}</b></div></div>
        <div><div class="small">Target change</div><div style="font-size:1.2rem;"><b>{kg_change:+.1f}</b> kg</div></div>
        <div><div class="small">Per-day change</div><div style="font-size:1.2rem;"><b>{per_day:+.3f}</b></div></div>
        <div><div class="small">Protein target</div><div style="font-size:1.2rem;"><b>{protein_target:.0f}</b></div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
def render_graphs(df, person, enable_gerd=False, enable_t1d=False, enable_period=False):
    if df is None or len(df) == 0:
        st.info("No history yet. Save a few days to see graphs.")
        return

    dfx = df.copy()

    if "log_date" not in dfx.columns:
        st.warning("No 'log_date' column found, cannot draw graphs.")
        return

    dfx["log_date"] = pd.to_datetime(dfx["log_date"], errors="coerce")
    dfx = dfx.dropna(subset=["log_date"]).sort_values("log_date")

    st.subheader("Trends & Graphs")

    # Row 1: Wellness + Weight
    c1, c2 = st.columns(2)

    if "WellnessIndex" in dfx.columns:
        fig = px.line(dfx, x="log_date", y="WellnessIndex", markers=True,
                      title=f"{person}: Wellness Index over time")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_traces(line=dict(width=3))
        c1.plotly_chart(fig, use_container_width=True)

    if "weight_kg" in dfx.columns and dfx["weight_kg"].notna().any():
        fig = px.line(dfx[dfx["weight_kg"].notna()], x="log_date", y="weight_kg", markers=True,
                      title=f"{person}: Weight trend (kg)")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_traces(line=dict(width=3))
        c2.plotly_chart(fig, use_container_width=True)

    # Row 2: Nutrition totals
    macro_cols = [c for c in ["kcal", "protein_g", "carbs_g", "fat_g"] if c in dfx.columns]
    if macro_cols:
        st.markdown("#### Nutrition totals (per day)")
        melt = dfx[["log_date"] + macro_cols].melt(id_vars=["log_date"], var_name="metric", value_name="value")
        fig = px.bar(melt, x="log_date", y="value", color="metric", barmode="group", title="Daily totals")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Row 3: Sleep / Exercise / GERD
    cols = st.columns(3)

    if "sleep_hours" in dfx.columns and dfx["sleep_hours"].notna().any():
        fig = px.line(dfx[dfx["sleep_hours"].notna()], x="log_date", y="sleep_hours", markers=True, title="Sleep (hours)")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_traces(line=dict(width=3))
        cols[0].plotly_chart(fig, use_container_width=True)

    if "exercise_min" in dfx.columns and dfx["exercise_min"].notna().any():
        fig = px.bar(dfx[dfx["exercise_min"].notna()], x="log_date", y="exercise_min", title="Exercise (minutes/day)")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        cols[1].plotly_chart(fig, use_container_width=True)

    if enable_gerd and "gerd_symptom" in dfx.columns and dfx["gerd_symptom"].notna().any():
        fig = px.line(dfx[dfx["gerd_symptom"].notna()], x="log_date", y="gerd_symptom", markers=True, title="GERD symptoms (0–10)")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_traces(line=dict(width=3))
        cols[2].plotly_chart(fig, use_container_width=True)

    # T1D
    if enable_t1d:
        st.markdown("#### Type 1 Diabetes trends")
        tcols = st.columns(2)

        if "glucose_mgdl" in dfx.columns and dfx["glucose_mgdl"].notna().any():
            fig = px.line(dfx[dfx["glucose_mgdl"].notna()], x="log_date", y="glucose_mgdl", markers=True, title="Avg glucose (mg/dL)")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
            fig.update_traces(line=dict(width=3))
            tcols[0].plotly_chart(fig, use_container_width=True)

        if "insulin_units" in dfx.columns and dfx["insulin_units"].notna().any():
            fig = px.bar(dfx[dfx["insulin_units"].notna()], x="log_date", y="insulin_units", title="Total insulin (units/day)")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10))
            tcols[1].plotly_chart(fig, use_container_width=True)

    # Period
    if enable_period and "period_day" in dfx.columns and dfx["period_day"].notna().any():
        st.markdown("#### Period tracker")
        fig = px.scatter(dfx[dfx["period_day"].notna()], x="log_date", y="period_day", title="Cycle day")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # ---- Trend charts ----
    gcols = st.columns([1.2, 1.0])

    with gcols[0]:
        if not merged.empty and "WellnessIndex" in merged.columns:
            fig = nice_line(
                merged,
                "log_date",
                "WellnessIndex",
                "Wellness trend",
                ytitle="Wellness (0–100)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data yet. Add meals + daily check-ins to see trends.")

    with gcols[1]:
        if not logs.empty:
            fig2 = nice_area_macros(logs, title="Macros per day (g)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Log meals to see macro trends.")

    pcols = st.columns([1, 1])

    with pcols[0]:
        if not merged.empty and "weight_kg" in merged.columns and merged["weight_kg"].notna().any():
            figw = nice_line(
                merged[merged["weight_kg"].notna()],
                "log_date",
                "weight_kg",
                "Weight trend",
                ytitle="kg"
            )
            st.plotly_chart(figw, use_container_width=True)
        else:
            st.caption("Weight plot appears after you log weight in Daily check-in.")

    with pcols[1]:
        if enable_gerd and "gerd_symptom" in merged.columns and merged["gerd_symptom"].notna().any():
            figg = nice_line(
                merged[merged["gerd_symptom"].notna()],
                "log_date",
                "gerd_symptom",
                "GERD symptoms trend",
                ytitle="0–10"
            )
            st.plotly_chart(figg, use_container_width=True)
        elif enable_t1d and "glucose_mgdl" in merged.columns and merged["glucose_mgdl"].notna().any():
            figglu = nice_line(
                merged[merged["glucose_mgdl"].notna()],
                "log_date",
                "glucose_mgdl",
                "Glucose trend",
                ytitle="mg/dL"
            )
            st.plotly_chart(figglu, use_container_width=True)
        else:
            st.caption("This panel becomes GERD or Glucose once logged.")


    with gcols[0]:
        if not merged.empty and "WellnessIndex" in merged.columns:
            fig = nice_line(
                merged,
                "log_date",
                "WellnessIndex",
                "Wellness trend",
                ytitle="Wellness (0–100)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data yet. Add meals + daily check-ins to see trends.")

    with gcols[1]:
        if not logs.empty:
            fig2 = nice_area_macros(logs, title="Macros per day (g)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Log meals to see macro trends.")

    pcols = st.columns([1, 1])

    with pcols[0]:
        if not merged.empty and "weight_kg" in merged.columns and merged["weight_kg"].notna().any():
            figw = nice_line(
                merged[merged["weight_kg"].notna()],
                "log_date",
                "weight_kg",
                "Weight trend",
                ytitle="kg"
            )
            st.plotly_chart(figw, use_container_width=True)
        else:
            st.caption("Weight plot appears after you log weight in Daily check-in.")

    with pcols[1]:
        if enable_gerd and "gerd_symptom" in merged.columns and merged["gerd_symptom"].notna().any():
            figg = nice_line(
                merged[merged["gerd_symptom"].notna()],
                "log_date",
                "gerd_symptom",
                "GERD symptoms trend",
                ytitle="0–10"
            )
            st.plotly_chart(figg, use_container_width=True)
        elif enable_t1d and "glucose_mgdl" in merged.columns and merged["glucose_mgdl"].notna().any():
            figglu = nice_line(
                merged[merged["glucose_mgdl"].notna()],
                "log_date",
                "glucose_mgdl",
                "Glucose trend",
                ytitle="mg/dL"
            )
            st.plotly_chart(figglu, use_container_width=True)
        else:
            st.caption("This panel becomes GERD or Glucose once logged.")


    st.subheader("Recent meals")
    if logs.empty:
        st.caption("No meals logged yet.")
    else:
        show = logs.copy()
        show = show.sort_values(["log_date", "meal_time"], ascending=[False, False]).head(20)
        st.dataframe(
            show[["log_date","meal_type","meal_time","dish","grams","kcal","protein_g","carbs_g","fat_g","notes"]],
            use_container_width=True,
            hide_index=True
        )

# =========================
# 6) APP UI
# =========================
st.title("Wellness Lab")
st.caption("3 profiles · meal-by-meal logging · trend graphs · goals · DB migration included")

st.sidebar.markdown("### Profile")
profile = st.sidebar.radio("Choose person", ["Sushil", "Chido", "Stupid"], index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick help")
st.sidebar.write("• Stop Streamlit: **Ctrl+C** in PowerShell, then run again.")
st.sidebar.write("• History stored in **data/wellness.db**")

if profile == "Sushil":
    header_block("Sushil", "Weight gain + GERD-aware tracking + protein planning", "GAIN + GERD")
    tabs = st.tabs(["Dashboard", "Log Meals", "Daily Check-in", "Goals"])
    with tabs[0]:
        dashboard("Sushil", enable_gerd=True, enable_t1d=False, enable_period=False)
    with tabs[1]:
        meal_logger("Sushil", enable_gerd=True, enable_t1d=False, context_key="meals")
    with tabs[2]:
        daily_logger("Sushil", enable_gerd=True, enable_t1d=False, enable_period=False, context_key="daily")
    with tabs[3]:
        goal_panel("Sushil", "gain", default_start=48.0, default_target=54.0, days_default=30, label="Weight gain goal", context_key="goal")

elif profile == "Chido":
    header_block("Chido", "Weight loss + wellness tracking (no GERD) + period tracking", "LOSS")
    tabs = st.tabs(["Dashboard", "Log Meals", "Daily Check-in", "Goals"])
    with tabs[0]:
        dashboard("Chido", enable_gerd=False, enable_t1d=False, enable_period=True)
    with tabs[1]:
        meal_logger("Chido", enable_gerd=False, enable_t1d=False, context_key="meals")
    with tabs[2]:
        daily_logger("Chido", enable_gerd=False, enable_t1d=False, enable_period=True, context_key="daily")
    with tabs[3]:
        goal_panel("Chido", "loss", default_start=70.0, default_target=65.0, days_default=45, label="Weight loss goal", context_key="goal")

else:
    header_block("Stupid", "Type 1 diabetes tracker: meals, glucose, insulin logging + weight gain goal", "T1D + GAIN")
    st.warning(
        "Type 1 diabetes safety: this app records data only. It does NOT calculate insulin doses. "
        "Do not use it to change insulin without clinician guidance."
    )
    tabs = st.tabs(["Dashboard", "Log Meals", "Daily Check-in", "Goals", "Period tracker"])
    with tabs[0]:
        dashboard("Stupid", enable_gerd=False, enable_t1d=True, enable_period=False)
    with tabs[1]:
        meal_logger("Stupid", enable_gerd=False, enable_t1d=True, context_key="meals")
    with tabs[2]:
        daily_logger("Stupid", enable_gerd=False, enable_t1d=True, enable_period=False, context_key="daily")
    with tabs[3]:
        goal_panel("Stupid", "gain", default_start=48.0, default_target=54.0, days_default=30, label="Weight gain goal", context_key="goal")
    with tabs[4]:
        # separate tab gets its own unique keys via context_key="period"
        daily_logger("Stupid", enable_gerd=False, enable_t1d=True, enable_period=True, context_key="period")

st.markdown("---")
st.caption("Local DB: data/wellness.db · Personal tracking tool · Not a medical device")
