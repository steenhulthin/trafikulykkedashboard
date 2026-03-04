#from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


DIMENSION_COLUMNS = [
    "age_code",
    "age_group",
    "sex_code",
    "sex_indicator",
    "injury_code",
    "injury_severity",
    "transport_code",
    "transport_mode",
]


def normalize_code(series: pd.Series, width: int | None = None) -> pd.Series:
    out = series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    if width is not None:
        out = out.str.zfill(width)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare LIGEHI10 traffic accident incidence data for Shiny for Python "
            "dashboards."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/202634153829606224870LIGEHI10.xlsx"),
        help="Path to the source Excel file.",
    )
    parser.add_argument(
        "--sheet",
        default="LIGEHI10",
        help="Sheet name to read from the Excel file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where prepared outputs are written.",
    )
    parser.add_argument(
        "--base-name",
        default="ligehi10",
        help="Base filename used for output files.",
    )
    parser.add_argument(
        "--structure",
        choices=["long", "wide_sex", "star"],
        default="long",
        help="Target output data structure.",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default="parquet",
        help="Output file format.",
    )
    return parser.parse_args()


def load_ligehi10_frame(path: Path, sheet: str) -> pd.DataFrame:
    # Row 3 contains year headers and rows 4..184 contain data.
    raw = pd.read_excel(path, sheet_name=sheet, header=None)

    year_headers = raw.iloc[2, 8:].dropna().tolist()
    year_headers = [str(int(y)) for y in year_headers]

    df = raw.iloc[3:, : 8 + len(year_headers)].copy()
    df.columns = DIMENSION_COLUMNS + year_headers

    # The source is a denormalized table with merged-like headers.
    df[DIMENSION_COLUMNS] = df[DIMENSION_COLUMNS].ffill()

    # Drop non-data rows, e.g. trailing notes.
    df = df.dropna(subset=year_headers, how="all").reset_index(drop=True)
    return df


def build_long_table(df: pd.DataFrame) -> pd.DataFrame:
    year_columns = [c for c in df.columns if c not in DIMENSION_COLUMNS]

    long_df = df.melt(
        id_vars=DIMENSION_COLUMNS,
        value_vars=year_columns,
        var_name="year",
        value_name="incidence_per_100k",
    )

    long_df["year"] = pd.to_numeric(long_df["year"], errors="coerce").astype("Int64")
    long_df["incidence_per_100k"] = pd.to_numeric(
        long_df["incidence_per_100k"], errors="coerce"
    )

    long_df = long_df.dropna(subset=["year", "incidence_per_100k"]).copy()
    long_df["year"] = long_df["year"].astype(int)

    long_df["age_code"] = normalize_code(long_df["age_code"], width=4)
    long_df["sex_code"] = normalize_code(long_df["sex_code"])
    long_df["injury_code"] = normalize_code(long_df["injury_code"])
    long_df["transport_code"] = normalize_code(long_df["transport_code"], width=2)

    long_df["sex"] = long_df["sex_code"].map({"M1": "men", "K1": "women"}).fillna(
        "unknown"
    )

    age_order_by_code = {
        "9917": 1,
        "1824": 2,
        "2544": 3,
        "4564": 4,
        "6599": 5,
    }
    long_df["age_order"] = long_df["age_code"].map(age_order_by_code).astype("Int64")

    return long_df.sort_values(
        ["year", "age_order", "sex_code", "injury_code", "transport_code"]
    ).reset_index(drop=True)


def build_wide_sex_table(long_df: pd.DataFrame) -> pd.DataFrame:
    idx = [
        "year",
        "age_code",
        "age_group",
        "age_order",
        "injury_code",
        "injury_severity",
        "transport_code",
        "transport_mode",
    ]
    wide = (
        long_df.pivot_table(
            index=idx, columns="sex_code", values="incidence_per_100k", aggfunc="first"
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    wide = wide.rename(columns={"M1": "men_per_100k", "K1": "women_per_100k"})
    if "men_per_100k" not in wide.columns:
        wide["men_per_100k"] = pd.NA
    if "women_per_100k" not in wide.columns:
        wide["women_per_100k"] = pd.NA
    wide["gender_gap_per_100k"] = wide["men_per_100k"] - wide["women_per_100k"]

    return wide.sort_values(
        ["year", "age_order", "injury_code", "transport_code"]
    ).reset_index(drop=True)


def build_star_schema(long_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    dim_age = (
        long_df[["age_code", "age_group", "age_order"]]
        .drop_duplicates()
        .sort_values("age_order")
        .reset_index(drop=True)
    )
    dim_sex = (
        long_df[["sex_code", "sex_indicator", "sex"]]
        .drop_duplicates()
        .sort_values("sex_code")
        .reset_index(drop=True)
    )
    dim_injury = (
        long_df[["injury_code", "injury_severity"]]
        .drop_duplicates()
        .sort_values("injury_code")
        .reset_index(drop=True)
    )
    dim_transport = (
        long_df[["transport_code", "transport_mode"]]
        .drop_duplicates()
        .sort_values("transport_code")
        .reset_index(drop=True)
    )

    fact = long_df[
        [
            "year",
            "age_code",
            "sex_code",
            "injury_code",
            "transport_code",
            "incidence_per_100k",
        ]
    ].copy()

    return {
        "fact_incidence": fact,
        "dim_age": dim_age,
        "dim_sex": dim_sex,
        "dim_injury": dim_injury,
        "dim_transport": dim_transport,
    }


def write_frame(df: pd.DataFrame, out_path: Path, fmt: str) -> None:
    if fmt == "csv":
        df.to_csv(out_path, index=False, encoding="utf-8")
        return
    if fmt == "json":
        df.to_json(out_path, orient="records", lines=True, force_ascii=False)
        return
    if fmt == "parquet":
        try:
            df.to_parquet(out_path, index=False)
        except ImportError as exc:
            raise ImportError(
                "Parquet output requires an engine such as 'pyarrow' or 'fastparquet'."
            ) from exc
        return
    raise ValueError(f"Unsupported format: {fmt}")


def write_outputs(
    *,
    long_df: pd.DataFrame,
    structure: str,
    fmt: str,
    output_dir: Path,
    base_name: str,
) -> Iterable[Path]:
    ext = {"csv": "csv", "json": "json", "parquet": "parquet"}[fmt]
    output_dir.mkdir(parents=True, exist_ok=True)

    if structure == "long":
        target = output_dir / f"{base_name}_long.{ext}"
        write_frame(long_df, target, fmt)
        return [target]

    if structure == "wide_sex":
        wide = build_wide_sex_table(long_df)
        target = output_dir / f"{base_name}_wide_sex.{ext}"
        write_frame(wide, target, fmt)
        return [target]

    if structure == "star":
        tables = build_star_schema(long_df)
        written_paths: list[Path] = []
        for suffix, table in tables.items():
            target = output_dir / f"{base_name}_{suffix}.{ext}"
            write_frame(table, target, fmt)
            written_paths.append(target)
        return written_paths

    raise ValueError(f"Unsupported structure: {structure}")


def main() -> None:
    args = parse_args()
    base_df = load_ligehi10_frame(args.input, args.sheet)
    long_df = build_long_table(base_df)

    written = write_outputs(
        long_df=long_df,
        structure=args.structure,
        fmt=args.format,
        output_dir=args.output_dir,
        base_name=args.base_name,
    )

    print("Wrote files:")
    for path in written:
        print(f"- {path}")
    print(f"Rows in long table: {len(long_df):,}")


if __name__ == "__main__":
    main()
