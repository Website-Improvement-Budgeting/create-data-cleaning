import re
import glob
import os
import pandas as pd

SCHEMA_FILE = "schema_silog.sql"
CSV_FOLDER = "supabase_import"

# ============================================================
# 1. BACA SCHEMA SQL
# ============================================================

with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
    schema = f.read()

# Ambil semua CREATE TABLE
pattern = re.compile(
    r'CREATE TABLE IF NOT EXISTS "public"\."([^"]+)"\s*\((.*?)\n\);',
    re.DOTALL
)

schema_tables = {}

for table_name, body in pattern.findall(schema):
    columns = []

    for line in body.splitlines():
        line = line.strip()

        # hanya ambil baris definisi kolom
        if not line.startswith('"'):
            continue

        match = re.match(r'"([^"]+)"\s+(.+?)(?:,)?$', line)

        if match:
            column_name = match.group(1)
            column_definition = match.group(2)

            # Skip constraint jika somehow terbaca
            if column_name.lower() not in ["constraint"]:
                columns.append(column_name)

    schema_tables[table_name] = columns


# ============================================================
# 2. BACA CSV OUTPUT
# ============================================================

csv_files = glob.glob(os.path.join(CSV_FOLDER, "*.csv"))

csv_tables = {}

for file in csv_files:
    table_name = os.path.splitext(os.path.basename(file))[0]

    df = pd.read_csv(file)

    csv_tables[table_name] = {
        "columns": df.columns.tolist(),
        "rows": len(df)
    }


# ============================================================
# 3. AUDIT
# ============================================================

print("=" * 70)
print("SCHEMA vs SUPABASE CSV AUDIT")
print("=" * 70)

print("\n[1] CSV TABLE YANG DIBUAT")
print("-" * 70)

for table_name, info in csv_tables.items():

    if table_name not in schema_tables:
        print(f"🔴 {table_name}: TIDAK ADA DI SCHEMA")
        continue

    schema_cols = schema_tables[table_name]
    csv_cols = info["columns"]

    missing = [c for c in schema_cols if c not in csv_cols]
    extra = [c for c in csv_cols if c not in schema_cols]

    if not missing and not extra:
        print(
            f"🟢 {table_name}: PASS "
            f"({info['rows']} rows, {len(csv_cols)} columns)"
        )
    else:
        print(f"🔴 {table_name}: PERBEDAAN")

        if missing:
            print(f"   Missing columns: {missing}")

        if extra:
            print(f"   Extra columns: {extra}")


# ============================================================
# 4. TABEL SCHEMA YANG BELUM ADA CSV
# ============================================================

print("\n[2] TABEL SCHEMA YANG BELUM DIBUAT CSV")
print("-" * 70)

missing_tables = sorted(set(schema_tables) - set(csv_tables))

for table in missing_tables:
    print(f"🟡 {table}")


# ============================================================
# 5. SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

passed = 0
failed = 0

for table_name, info in csv_tables.items():

    if table_name not in schema_tables:
        failed += 1
        continue

    schema_cols = set(schema_tables[table_name])
    csv_cols = set(info["columns"])

    if schema_cols == csv_cols:
        passed += 1
    else:
        failed += 1

print(f"CSV tables checked : {len(csv_tables)}")
print(f"Structure PASS     : {passed}")
print(f"Structure ISSUE    : {failed}")
print(f"Schema-only tables : {len(missing_tables)}")

print("=" * 70)