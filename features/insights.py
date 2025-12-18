import pandas as pd

def week_summary(df: pd.DataFrame):
    # df from DB logs; expects columns: date, wellness, protein, weight
    if df is None or df.empty:
        return None

    d = df.copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"]).sort_values("date")

    last7 = d.tail(7)
    if last7.empty:
        return None

    out = {
        "avg_wellness": float(last7["wellness"].mean()) if "wellness" in last7 else None,
        "avg_protein": float(last7["protein"].mean()) if "protein" in last7 else None,
        "weight_change": None
    }

    if "weight" in last7 and last7["weight"].notna().sum() >= 2:
        out["weight_change"] = float(last7["weight"].iloc[-1] - last7["weight"].iloc[0])

    return out
