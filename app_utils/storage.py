from sqlalchemy import create_engine, text
import pandas as pd
import os

DB_PATH = "data/wellness.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db():
    os.makedirs("data", exist_ok=True)
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT,
            date TEXT,
            weight REAL,
            protein REAL,
            carbs REAL,
            wellness REAL,
            notes TEXT,
            extra TEXT
        )
        """))

def save_log(profile, date, weight, protein, carbs, wellness, notes="", extra=None):
    extra = extra or {}
    df = pd.DataFrame([{
        "profile": profile,
        "date": date,
        "weight": weight,
        "protein": protein,
        "carbs": carbs,
        "wellness": wellness,
        "notes": notes,
        "extra": str(extra)
    }])
    df.to_sql("logs", engine, if_exists="append", index=False)

def load_logs(profile=None):
    if profile:
        q = f"SELECT * FROM logs WHERE profile='{profile}' ORDER BY date"
    else:
        q = "SELECT * FROM logs ORDER BY date"
    return pd.read_sql(q, engine)

