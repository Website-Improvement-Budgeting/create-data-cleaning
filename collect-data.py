"""
collect-data.py
----------------
Menyusun output pipeline menjadi dataset/tabel yang siap dimuat ke Supabase
sesuai schema_silog.sql.

Input utama:
    data/database_ready_budget_master.csv
    data/data_silog.sql

Output:
    data/supabase_import/*.csv

Catatan:
- budget_master menggunakan ID yang SUDAH dibuat oleh pipeline.
- master data (unit_entity, biro, funds_center, commitment_item, fund,
  master_fc, master_ci, master_fund) diambil dari existing master SQL
  agar ID/relasi tetap konsisten.
- Tabel transaksi yang belum memiliki data hanya dibuat sebagai template
  dengan kolom yang sesuai schema.
"""

from __future__ import annotations

from pathlib import Path
import csv
import io
import re
import pandas as pd


# ============================================================
# 1. PATH
# ============================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT
OUTPUT_DIR = ROOT / "supabase_import"

BUDGET_FILE = ROOT / "database_ready_budget_master.csv"
MASTER_SQL_FILE = ROOT / "data_silog.sql"


BUDGET_YEAR = 2026


# ============================================================
# 2. HELPERS
# ============================================================

def clean_code(series: pd.Series) -> pd.Series:
    """Normalisasi kode agar tidak berubah menjadi 001.0 / NaN string."""
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .replace("", pd.NA)
    )


def read_copy_table(sql_path: Path, table_name: str) -> pd.DataFrame:
    """
    Membaca satu blok PostgreSQL COPY ... FROM stdin dari data_silog.sql.
    Dipakai untuk mempertahankan ID master existing.
    """
    text = sql_path.read_text(encoding="utf-8", errors="replace")

    pattern = re.compile(
        rf'COPY "public"\."{re.escape(table_name)}" '
        rf'\((.*?)\) FROM stdin;\n(.*?)\n\\\.',
        re.DOTALL,
    )

    match = pattern.search(text)

    if not match:
        raise ValueError(
            f"Tabel {table_name!r} tidak ditemukan dalam {sql_path.name}"
        )

    columns = [
        c.strip().strip('"')
        for c in match.group(1).split(",")
    ]

    raw = match.group(2)

    if not raw.strip():
        return pd.DataFrame(columns=columns)

    rows = list(csv.reader(
        io.StringIO(raw),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
    ))

    # PostgreSQL COPY menggunakan \N untuk NULL
    rows = [
        [None if value == r"\N" else value for value in row]
        for row in rows
    ]

    return pd.DataFrame(rows, columns=columns)


def write_csv(name: str, df: pd.DataFrame) -> None:
    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(
        path,
        index=False,
        encoding="utf-8",
        na_rep="",
    )
    print(f"{name:<28} {len(df):>6,} rows -> {path}")


def assert_columns(df: pd.DataFrame, expected: list[str], name: str) -> None:
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(
            f"{name}: kolom wajib tidak ada: {missing}"
        )


def assert_fk(
    df: pd.DataFrame,
    fk_col: str,
    ref_df: pd.DataFrame,
    pk_col: str,
    *,
    nullable: bool = False,
) -> None:
    if not nullable and df[fk_col].isna().any():
        raise ValueError(f"{fk_col}: terdapat NULL FK")

    actual = set(df[fk_col].dropna())
    valid = set(ref_df[pk_col].dropna())

    invalid = actual - valid
    if invalid:
        sample = list(sorted(invalid))[:10]
        raise ValueError(
            f"{fk_col}: terdapat FK tidak valid. Contoh: {sample}"
        )


# ============================================================
# 3. LOAD DATABASE-READY BUDGET
# ============================================================

print("=" * 70)
print("COLLECT DATA -> SUPABASE READY TABLES")
print("=" * 70)

if not BUDGET_FILE.exists():
    raise FileNotFoundError(
        f"File tidak ditemukan: {BUDGET_FILE}"
    )

if not MASTER_SQL_FILE.exists():
    raise FileNotFoundError(
        f"File tidak ditemukan: {MASTER_SQL_FILE}"
    )

budget_master = pd.read_csv(
    BUDGET_FILE,
    dtype={
        "budget_id": "Int64",
        "entity_id": "Int64",
        "biro_id": "Int64",
        "funds_center_id": "Int64",
        "commitment_item_id": "Int64",
        "budget_scope": "string",
        "budget_year": "Int64",
    },
)

numeric_budget_cols = [
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
]

for col in numeric_budget_cols:
    budget_master[col] = pd.to_numeric(
        budget_master[col],
        errors="raise",
    )

# Pastikan tahun selalu tersedia.
if budget_master["budget_year"].isna().any():
    budget_master["budget_year"] = (
        budget_master["budget_year"]
        .fillna(BUDGET_YEAR)
        .astype("Int64")
    )


# ============================================================
# 4. LOAD EXISTING MASTER DARI data_silog.sql
# ============================================================

unit_entity = read_copy_table(MASTER_SQL_FILE, "unit_entity")
biro = read_copy_table(MASTER_SQL_FILE, "biro")
funds_center = read_copy_table(MASTER_SQL_FILE, "funds_center")
commitment_item = read_copy_table(MASTER_SQL_FILE, "commitment_item")
fund = read_copy_table(MASTER_SQL_FILE, "fund")
master_fc = read_copy_table(MASTER_SQL_FILE, "master_fc")
master_ci = read_copy_table(MASTER_SQL_FILE, "master_ci")
master_fund = read_copy_table(MASTER_SQL_FILE, "master_fund")


# ============================================================
# 5. CAST MASTER ID
# ============================================================

for df, cols in [
    (unit_entity, ["entity_id"]),
    (biro, ["biro_id", "entity_id"]),
    (funds_center, ["funds_center_id"]),
    (commitment_item, ["commitment_item_id"]),
    (fund, ["fund_id"]),
    (master_fc, ["master_fc_id", "target_funds_center_id"]),
    (master_ci, ["master_ci_id", "target_commitment_item_id"]),
    (master_fund, ["master_fund_id", "target_fund_id"]),
]:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="raise",
            ).astype("Int64")


# ============================================================
# 6. VALIDATE budget_master SESUAI schema
# ============================================================

budget_columns = [
    "budget_id",
    "entity_id",
    "biro_id",
    "funds_center_id",
    "commitment_item_id",
    "budget_scope",
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "budget_year",
]

assert_columns(
    budget_master,
    budget_columns,
    "budget_master",
)

budget_master = budget_master[budget_columns].copy()

# PK
if budget_master["budget_id"].duplicated().any():
    raise ValueError("budget_id duplicate ditemukan.")

# NOT NULL yang diwajibkan schema
required_non_null = [
    "budget_id",
    "entity_id",
    "commitment_item_id",
    "budget_scope",
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
]

for col in required_non_null:
    if budget_master[col].isna().any():
        raise ValueError(
            f"{col} memiliki NULL, padahal wajib menurut schema."
        )

# Scope
if not budget_master["budget_scope"].isin(
    ["FC_CI", "CI_ONLY"]
).all():
    raise ValueError("budget_scope di luar FC_CI / CI_ONLY.")

# Schema: FC_CI wajib punya FC; CI_ONLY wajib NULL FC.
fc_ci = budget_master["budget_scope"].eq("FC_CI")
ci_only = budget_master["budget_scope"].eq("CI_ONLY")

if budget_master.loc[fc_ci, "funds_center_id"].isna().any():
    raise ValueError(
        "Ada FC_CI tanpa funds_center_id."
    )

if budget_master.loc[ci_only, "funds_center_id"].notna().any():
    raise ValueError(
        "Ada CI_ONLY yang memiliki funds_center_id."
    )

# Schema: available = consumable - consumed.
expected_available = (
    budget_master["consumable_budget"]
    - budget_master["consumed_budget"]
)

if not (
    budget_master["available_amount"]
    .sub(expected_available)
    .abs()
    .le(1)
    .all()
):
    raise ValueError(
        "available_amount tidak konsisten dengan consumable - consumed."
    )

# Schema: semua nominal >= 0.
if (
    budget_master[numeric_budget_cols] < 0
).any().any():
    raise ValueError(
        "Ada nominal budget negatif."
    )

# Budget year
if (
    budget_master["budget_year"].notna()
    & ~budget_master["budget_year"].between(2000, 2100)
).any():
    raise ValueError(
        "budget_year di luar rentang schema."
    )


# ============================================================
# 7. FOREIGN KEY VALIDATION
# ============================================================

assert_fk(
    budget_master,
    "entity_id",
    unit_entity,
    "entity_id",
)

assert_fk(
    budget_master,
    "biro_id",
    biro,
    "biro_id",
    nullable=True,
)

assert_fk(
    budget_master,
    "funds_center_id",
    funds_center,
    "funds_center_id",
    nullable=True,
)

assert_fk(
    budget_master,
    "commitment_item_id",
    commitment_item,
    "commitment_item_id",
)

assert_fk(
    biro,
    "entity_id",
    unit_entity,
    "entity_id",
)

assert_fk(
    master_fc,
    "target_funds_center_id",
    funds_center,
    "funds_center_id",
)

assert_fk(
    master_ci,
    "target_commitment_item_id",
    commitment_item,
    "commitment_item_id",
)

assert_fk(
    master_fund,
    "target_fund_id",
    fund,
    "fund_id",
)


# ============================================================
# 8. TRANSACTION TABLE TEMPLATES
# ============================================================
# Belum diisi karena pipeline budget belum menghasilkan transaksi
# request/approval/allocation/history. Kolom dibuat mengikuti schema.

users = pd.DataFrame(columns=[
    "user_id",
    "username",
    "password",
    "role",
    "entity_id",
    "biro_id",
])

budget_request = pd.DataFrame(columns=[
    "request_id",
    "user_id",
    "entity_id",
    "request_date",
    "pic",
    "input_profit_center",
    "input_cost_center",
    "input_gl_account",
    "request_amount",
    "request_description",
    "mapped_fund_id",
    "mapped_funds_center_id",
    "mapped_commitment_item_id",
    "budget_id",
    "budget_scope",
    "available_amount_snapshot",
    "shortage_amount",
    "approval_hold_amount_snapshot",
    "mapping_status",
    "budget_status",
    "request_status",
    "transaction_date",
    "batch_id",
])

approval_decision = pd.DataFrame(columns=[
    "approval_id",
    "request_id",
    "approval_user_id",
    "decision",
    "instruction",
    "approved_amount",
    "decision_date",
])

budget_allocation = pd.DataFrame(columns=[
    "allocation_id",
    "request_id",
    "source_budget_id",
    "target_budget_id",
    "allocation_type",
    "amount",
    "instruction",
    "approved_by",
])

budget_history = pd.DataFrame(columns=[
    "history_id",
    "budget_id",
    "request_id",
    "action",
    "field_name",
    "previous_value",
    "updated_value",
    "amount",
    "created_by",
    "transaction_date",
])


# ============================================================
# 9. EXPORT
# ============================================================

tables = {
    "unit_entity": unit_entity,
    "biro": biro,
    "funds_center": funds_center,
    "commitment_item": commitment_item,
    "fund": fund,
    "master_fc": master_fc,
    "master_ci": master_ci,
    "master_fund": master_fund,
    "budget_master": budget_master,
    "users": users,
    "budget_request": budget_request,
    "approval_decision": approval_decision,
    "budget_allocation": budget_allocation,
    "budget_history": budget_history,
}

print("\n" + "=" * 70)
print("EXPORT SUMMARY")
print("=" * 70)

for name, df in tables.items():
    write_csv(name, df)

print("\n" + "=" * 70)
print("VALIDATION PASSED")
print("=" * 70)
print(f"Budget master : {len(budget_master):,} rows")
print(f"FC_CI         : {(budget_master['budget_scope'] == 'FC_CI').sum():,}")
print(f"CI_ONLY       : {(budget_master['budget_scope'] == 'CI_ONLY').sum():,}")
print(f"Output folder : {OUTPUT_DIR}")
print("=" * 70)
