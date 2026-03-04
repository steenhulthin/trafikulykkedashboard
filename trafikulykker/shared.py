from pathlib import Path

import pandas as pd

app_dir = Path(__file__).parent


def _load_processed_data() -> pd.DataFrame:
    candidates = [
        app_dir / "ligehi10_long.csv",
        app_dir.parent / "data" / "processed" / "ligehi10_long.csv",
        app_dir / "ligehi10_long.parquet",
        app_dir.parent / "data" / "processed" / "ligehi10_long.parquet",
    ]

    for path in candidates:
        if not path.exists():
            continue
        if path.suffix == ".csv":
            return pd.read_csv(path)
        if path.suffix == ".parquet":
            try:
                return pd.read_parquet(path)
            except ImportError as exc:
                raise ImportError(
                    "Found Parquet data but no parquet engine is installed. "
                    "Install 'pyarrow' or generate CSV with "
                    "'python data/prepare_ligehi10.py --structure long --format csv'."
                ) from exc

    expected = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Could not find processed LIGEHI10 data. Looked for: {expected}")


df = _load_processed_data()
df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
df["incidence_per_100k"] = pd.to_numeric(df["incidence_per_100k"], errors="coerce")
df = df.dropna(subset=["year", "incidence_per_100k"]).copy()
df["year"] = df["year"].astype(int)

year_choices = [str(y) for y in sorted(df["year"].unique())]
age_choices = sorted(df["age_group"].dropna().astype(str).unique().tolist())
sex_choices = sorted(df["sex_indicator"].dropna().astype(str).unique().tolist())
injury_choices = sorted(df["injury_severity"].dropna().astype(str).unique().tolist())
transport_choices = sorted(df["transport_mode"].dropna().astype(str).unique().tolist())
