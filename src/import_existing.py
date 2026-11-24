"""
Existing Master Data Extraction

Membaca data master dari data_silog.sql
untuk digunakan sebagai reference database mapping.
"""

import re
import pandas as pd
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

SQL_FILE = Path("data_silog.sql")


# ============================================================
# EXTRACT COPY BLOCK
# ============================================================

def extract_copy_block(sql_text, table_name):
    """
    Mengambil blok COPY untuk tabel tertentu
    dari PostgreSQL dump.
    """

    pattern = (
        rf'COPY "public"\."{re.escape(table_name)}" '
        rf'\((.*?)\) FROM stdin;\n'
        rf'(.*?)\n\\\.'
    )

    match = re.search(
        pattern,
        sql_text,
        flags=re.DOTALL
    )

    if not match:
        raise ValueError(
            f"COPY block untuk tabel '{table_name}' tidak ditemukan."
        )

    columns_text = match.group(1)
    data_text = match.group(2)

    columns = [
        col.strip().strip('"')
        for col in columns_text.split(",")
    ]

    rows = []

    for line in data_text.splitlines():

        if not line.strip():
            continue

        values = line.split("\t")

        cleaned_values = []

        for value in values:

            if value == r"\N":
                cleaned_values.append(None)
            else:
                cleaned_values.append(value)

        rows.append(cleaned_values)

    return pd.DataFrame(
        rows,
        columns=columns
    )


# ============================================================
# NORMALIZE MASTER DATA TYPES
# ============================================================

def normalize_master_types(table_name, df):
    """
    Menyesuaikan tipe data master agar konsisten
    ketika digunakan untuk database mapping.
    """

    df = df.copy()

    # --------------------------------------------------------
    # BIRO
    # --------------------------------------------------------

    if table_name == "biro":

        df["biro_id"] = pd.to_numeric(
            df["biro_id"],
            errors="coerce"
        ).astype("Int64")

        df["entity_id"] = pd.to_numeric(
            df["entity_id"],
            errors="coerce"
        ).astype("Int64")

        df["biro_code"] = (
            df["biro_code"]
            .astype("string")
            .str.strip()
        )

        df["biro_name"] = (
            df["biro_name"]
            .astype("string")
            .str.strip()
        )

    # --------------------------------------------------------
    # FUNDS CENTER
    # --------------------------------------------------------

    elif table_name == "funds_center":

        df["funds_center_id"] = pd.to_numeric(
            df["funds_center_id"],
            errors="coerce"
        ).astype("Int64")

        df["funds_center_code"] = (
            df["funds_center_code"]
            .astype("string")
            .str.strip()
        )

    # --------------------------------------------------------
    # COMMITMENT ITEM
    # --------------------------------------------------------

    elif table_name == "commitment_item":

        df["commitment_item_id"] = pd.to_numeric(
            df["commitment_item_id"],
            errors="coerce"
        ).astype("Int64")

        df["commitment_item_code"] = (
            df["commitment_item_code"]
            .astype("string")
            .str.strip()
        )

        df["commitment_item_name"] = (
            df["commitment_item_name"]
            .astype("string")
            .str.strip()
        )

    # --------------------------------------------------------
    # MASTER CI
    # --------------------------------------------------------

    elif table_name == "master_ci":

        df["master_ci_id"] = pd.to_numeric(
            df["master_ci_id"],
            errors="coerce"
        ).astype("Int64")

        df["from_gl_account"] = pd.to_numeric(
            df["from_gl_account"],
            errors="coerce"
        ).astype("Int64")

        df["to_gl_account"] = pd.to_numeric(
            df["to_gl_account"],
            errors="coerce"
        ).astype("Int64")

        df["target_commitment_item_id"] = pd.to_numeric(
            df["target_commitment_item_id"],
            errors="coerce"
        ).astype("Int64")

    return df


# ============================================================
# LOAD EXISTING MASTER
# ============================================================

def load_existing_master(sql_file=SQL_FILE):

    print("\n========================================")
    print(" EXISTING MASTER DATA EXTRACTION")
    print("========================================")

    sql_file = Path(sql_file)

    if not sql_file.exists():
        raise FileNotFoundError(
            f"File tidak ditemukan: {sql_file}"
        )

    print(f"\nSQL file : {sql_file}")

    sql_text = sql_file.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    master_tables = {}

    tables = [
        "biro",
        "funds_center",
        "commitment_item",
        "master_ci"
    ]

    for table_name in tables:

        print(
            f"\nExtracting: {table_name}"
        )

        df = extract_copy_block(
            sql_text,
            table_name
        )

        # Normalisasi tipe data
        df = normalize_master_types(
            table_name,
            df
        )

        master_tables[table_name] = df

        print(
            f"Jumlah data : {len(df)}"
        )

        print(
            f"Kolom       : {df.columns.tolist()}"
        )

    return master_tables


# ============================================================
# INSPECTION
# ============================================================

def inspect_existing_master(master_tables):

    print("\n========================================")
    print(" EXISTING MASTER INSPECTION")
    print("========================================")

    for table_name, df in master_tables.items():

        print(f"\n--- {table_name.upper()} ---")

        print(
            f"Rows    : {len(df)}"
        )

        print(
            f"Columns : {df.columns.tolist()}"
        )

        print(
            f"Duplicate rows : {df.duplicated().sum()}"
        )

        print("\nData types:")

        print(
            df.dtypes
        )

        print("\nSample:")

        print(
            df.head()
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    master_tables = load_existing_master()

    inspect_existing_master(
        master_tables
    )