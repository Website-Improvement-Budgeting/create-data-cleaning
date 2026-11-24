import pandas as pd
from src.extract import extract_budget_data

from src.transform import (
    transform_budget_data,
    standardize_columns,
    clean_code_biro,
    split_detail,
    clean_number,
    classify_row,
    map_funds_center
)

from src.validate import validate_budget_data
from src.finalize import create_final_dataset
from src.database_mapping import map_final_dataset_to_database


# ============================================================
# 1. LOKASI FILE INPUT
# ============================================================

FILE_PATH = "dataset/data-mentah-budgeting.xlsx"


# ============================================================
# 2. EXTRACT
# ============================================================

raw_data = extract_budget_data(FILE_PATH)


# ============================================================
# 3. TRANSFORM AWAL
# ============================================================

transformed_data = transform_budget_data(raw_data)


# ============================================================
# 4. STANDARDISASI KOLOM
# ============================================================

standardized_data = standardize_columns(transformed_data)


# ============================================================
# 5. CLEAN BIRO CODE
# ============================================================

for sheet_name, df in standardized_data.items():

    df["biro_code"] = (
        df["biro_code"]
        .apply(clean_code_biro)
    )

    standardized_data[sheet_name] = df


# ============================================================
# 6. SPLIT DETAIL
# ============================================================

for sheet_name, df in standardized_data.items():

    df[["detail_code", "detail_name"]] = (
        df["row_detail"]
        .apply(split_detail)
    )

    standardized_data[sheet_name] = df


# ============================================================
# 7. CLEAN ANGKA BUDGET
# ============================================================

budget_columns = [
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "current_budget",
    "commitment_actuals",
    "sisa"
]


for sheet_name, df in standardized_data.items():

    for col in budget_columns:

        df[col] = (
            df[col]
            .apply(clean_number)
        )

    standardized_data[sheet_name] = df


# ============================================================
# 8. KLASIFIKASI ROW
# ============================================================

for sheet_name, df in standardized_data.items():

    df["row_type"] = (
        df.apply(classify_row, axis=1)
    )

    standardized_data[sheet_name] = df


print("\n========== EXTRACT & TRANSFORM ==========")

print("\nSheet yang berhasil dibaca:")

print(
    list(raw_data.keys())
)


print("\nData setelah klasifikasi:")

print(
    standardized_data["Kantor Pusat Silog"][
        [
            "biro_code",
            "detail_code",
            "detail_name",
            "row_type"
        ]
    ].head(20)
)


print("\nJumlah setiap row_type:")

print(
    standardized_data["Kantor Pusat Silog"]["row_type"]
    .value_counts(dropna=False)
)


# ============================================================
# 9. MAP FUNDS CENTER
# ============================================================

standardized_data = map_funds_center(
    standardized_data
)


print("\n========== FUNDS CENTER MAPPING ==========")

print(
    standardized_data["Kantor Pusat Silog"].loc[
        534:560,
        [
            "biro_code",
            "detail_code",
            "detail_name",
            "row_type",
            "current_funds_center",
            "current_funds_center_name"
        ]
    ]
)


# ============================================================
# 10. DATA VALIDATION
# ============================================================

validation_results = validate_budget_data(
    standardized_data
)


print("\n========== VALIDATION REPORT ==========")


for result in validation_results:

    print(
        f"\nSheet: {result['sheet_name']}"
    )

    print(
        f"Status: {result['status']}"
    )

    print(
        f"Jumlah baris: {result['row_count']}"
    )

    print(
        f"Parent: {result['parent_count']}"
    )

    print(
        f"Funds Center: {result['funds_center_count']}"
    )

    print(
        f"Commitment Item: {result['commitment_item_count']}"
    )

    if result["errors"]:

        print("Errors:")

        for error in result["errors"]:

            print(
                f"  - {error}"
            )

    if result["warnings"]:

        print("Warnings:")

        for warning in result["warnings"]:

            print(
                f"  - {warning}"
            )


print("\n========================================")


# ============================================================
# 11. CREATE FINAL DATASET
# ============================================================

final_data = create_final_dataset(
    standardized_data
)


print("\n========== FINAL DATASET ==========")

print(
    "Jumlah baris:",
    len(final_data)
)

print(
    "Jumlah kolom:",
    len(final_data.columns)
)


print("\nKolom:")

print(
    final_data.columns.tolist()
)


print("\nContoh data:")

print(
    final_data.head()
)


# ============================================================
# 12. DATABASE MAPPING
# ============================================================

mapped_data = map_final_dataset_to_database(
    final_data
)
# ============================================================
# 12A. DATABASE-READY PAYLOAD
# ============================================================

print("\n========== DATABASE-READY PAYLOAD ==========")

# ------------------------------------------------------------
# Pisahkan data yang sudah memiliki Commitment Item ID
# dan data yang belum berhasil dimapping.
# ------------------------------------------------------------

# ------------------------------------------------------------
# DATABASE READY
# ------------------------------------------------------------

database_ready = mapped_data[
    mapped_data["commitment_item_id"].notna()
].copy()

# ------------------------------------------------------------
# EXCEPTION
# ------------------------------------------------------------

unmapped_exception = mapped_data[
    mapped_data["commitment_item_id"].isna()
].copy()

# ------------------------------------------------------------
# EXCLUDE NEGATIVE AVAILABLE AMOUNT
# ------------------------------------------------------------

negative_available = database_ready[
    (
        database_ready["consumable_budget"]
        - database_ready["consumed_budget"]
    ) < 0
].copy()

# Pindahkan row negatif ke exception
unmapped_exception = pd.concat(
    [
        unmapped_exception,
        negative_available
    ],
    ignore_index=True
)

# Hapus row negatif dari database-ready
database_ready = database_ready[
    ~(
        (
            database_ready["consumable_budget"]
            - database_ready["consumed_budget"]
        ) < 0
    )
].copy()


# ------------------------------------------------------------
# Normalisasi budget amount
# ------------------------------------------------------------

amount_columns = [
    "current_budget",
    "consumable_budget",
    "consumed_budget"
]

for col in amount_columns:

    database_ready[col] = (
        pd.to_numeric(
            database_ready[col],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )


# ------------------------------------------------------------
# Hitung ulang available_amount
# ------------------------------------------------------------
# available_amount harus selalu memenuhi:
#
# available_amount =
# consumable_budget - consumed_budget
#
# Perhitungan dilakukan SETELAH normalisasi
# agar konsisten dengan constraint database.
# ------------------------------------------------------------

database_ready["available_amount"] = (
    database_ready["consumable_budget"]
    - database_ready["consumed_budget"]
)


# ------------------------------------------------------------
# Validasi hasil perhitungan
# ------------------------------------------------------------

if (
    database_ready["available_amount"] < 0
).any():

    print(
        "\nWARNING:"
        " terdapat available_amount negatif."
    )

    print(
        database_ready.loc[
            database_ready["available_amount"] < 0,
            [
                "entity_id",
                "biro_id",
                "funds_center_id",
                "commitment_item_id",
                "consumable_budget",
                "consumed_budget",
                "available_amount"
            ]
        ].head(20)
    )
# ------------------------------------------------------------
# Tentukan kolom yang akan menjadi payload budget_master
# ------------------------------------------------------------

budget_columns = [
    "entity_id",
    "biro_id",
    "funds_center_id",
    "commitment_item_id",
    "budget_scope",
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "budget_year"
]


# ------------------------------------------------------------
# Cek kolom yang tersedia sebelum membuat payload
# ------------------------------------------------------------

print("\n========== KOLOM UNTUK PENENTUAN BUDGET SCOPE ==========")

print(
    mapped_data[
        [
            col
            for col in [
                "source_entity",
                "row_type",
                "current_funds_center",
                "current_funds_center_name",
                "detail_code",
                "detail_name",
                "current_budget",
                "consumable_budget",
                "consumed_budget",
                "available_amount"
            ]
            if col in mapped_data.columns
        ]
    ].head(30)
)

print("\nKolom yang tersedia di mapped_data:")
print(mapped_data.columns.tolist())
# ------------------------------------------------------------
# Tentukan BUDGET SCOPE
# ------------------------------------------------------------
# Jika terdapat Funds Center dan Commitment Item,
# maka budget_scope = FC_CI.
#
# Jika hanya terdapat Commitment Item,
# maka budget_scope = CI_ONLY.
# ------------------------------------------------------------

database_ready["budget_scope"] = (
    database_ready["funds_center_id"]
    .notna()
    .map({
        True: "FC_CI",
        False: "CI_ONLY"
    })
)


# ------------------------------------------------------------
# Tentukan BUDGET YEAR
# ------------------------------------------------------------
# Data budgeting yang sedang diproses adalah tahun 2026.
# ------------------------------------------------------------

database_ready["budget_year"] = 2026


# ------------------------------------------------------------
# Pastikan ID foreign key bertipe integer nullable
# ------------------------------------------------------------

for col in [
    "entity_id",
    "biro_id",
    "funds_center_id",
    "commitment_item_id"
]:
    database_ready[col] = pd.to_numeric(
        database_ready[col],
        errors="coerce"
    ).astype("Int64")


# ------------------------------------------------------------
# Buat BUDGET ID
# ------------------------------------------------------------
# budget_master kosong saat ini, sehingga ID dimulai dari 1.

# DETAIL ROW DENGAN AVAILABLE AMOUNT NEGATIF


# ------------------------------------------------------------
# DETAIL SUMBER UNTUK ROW NEGATIF
# ------------------------------------------------------------

print("\n========== SOURCE DATA ROW NEGATIF ==========")

negative_source = mapped_data[
    (mapped_data["entity_id"] == 5) &
    (mapped_data["biro_id"] == 47) &
    (mapped_data["commitment_item_id"] == 1375)
].copy()

print(
    negative_source[
        [
            "source_entity",
            "biro_code",
            "biro_name",
            "row_detail",
            "detail_code",
            "detail_name",
            "row_type",
            "consumable_budget",
            "consumed_budget",
            "available_amount",
            "current_budget",
            "commitment_actuals",
            "sisa",
            "current_funds_center",
            "current_funds_center_name",
            "entity_id",
            "biro_id",
            "funds_center_id",
            "commitment_item_id"
        ]
    ].to_string(index=False)
)

# ------------------------------------------------------------
# Susun payload sesuai struktur budget_master
# ------------------------------------------------------------

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
    "budget_year"
]

# ------------------------------------------------------------
# Buat BUDGET ID
# ------------------------------------------------------------

database_ready.insert(
    0,
    "budget_id",
    range(1, len(database_ready) + 1)
)


# ============================================================
# VALIDASI DATABASE-READY PAYLOAD
# ============================================================

print("\n========== DATABASE-READY VALIDATION ==========")

print(
    "Jumlah row database-ready:",
    len(database_ready)
)

print(
    "Jumlah row exception:",
    len(unmapped_exception)
)


# ------------------------------------------------------------
# Cek NULL pada kolom wajib
# ------------------------------------------------------------

required_columns = [
    "budget_id",
    "entity_id",
    "commitment_item_id",
    "budget_scope",
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "budget_year"
]

print("\nNULL pada kolom wajib:")

for col in required_columns:

    print(
        f"{col}:",
        database_ready[col].isna().sum()
    )


# ------------------------------------------------------------
# Cek budget scope
# ------------------------------------------------------------

print("\nDistribusi budget_scope:")

print(
    database_ready["budget_scope"]
    .value_counts(dropna=False)
)


# ------------------------------------------------------------
# Cek konsistensi available amount
# ------------------------------------------------------------

available_check = (
    database_ready["available_amount"]
    ==
    (
        database_ready["consumable_budget"]
        -
        database_ready["consumed_budget"]
    )
)

print(
    "\nAvailable amount konsisten:",
    available_check.all()
)

print(
    "Jumlah tidak konsisten:",
    (~available_check).sum()
)


# ------------------------------------------------------------
# Cek nilai negatif
# ------------------------------------------------------------

print("\nNilai negatif:")

for col in [
    "current_budget",
    "consumable_budget",
    "consumed_budget",
    "available_amount"
]:

    print(
        f"{col}:",
        (
            database_ready[col] < 0
        ).sum()
    )


# ------------------------------------------------------------
# Cek duplicate budget_id
# ------------------------------------------------------------

print(
    "\nDuplicate budget_id:",
    database_ready["budget_id"].duplicated().sum()
)


# ------------------------------------------------------------
# Tampilkan payload
# ------------------------------------------------------------

print("\n========== DATABASE-READY PAYLOAD ==========")

print(
    database_ready.head(20).to_string(index=False)
)

print("\nStruktur payload:")

print(
    database_ready.dtypes
)


# ============================================================
# SUMMARY
# ============================================================

print("\n========================================")
print(" DATABASE-READY SUMMARY")
print("========================================")

print(
    "Total payload:",
    len(database_ready)
)

print(
    "Total exception:",
    len(unmapped_exception)
)

print(
    "FC_CI:",
    (
        database_ready["budget_scope"] == "FC_CI"
    ).sum()
)

print(
    "CI:",
    (
        database_ready["budget_scope"] == "CI"
    ).sum()
)

print(
    "Commitment Item NULL:",
    database_ready["commitment_item_id"].isna().sum()
)

print(
    "Entity NULL:",
    database_ready["entity_id"].isna().sum()
)

print(
    "Budget ID duplicate:",
    database_ready["budget_id"].duplicated().sum()
)

print(
    "Available amount konsisten:",
    available_check.all()
)

# ============================================================
# 13. MAPPED DATASET SUMMARY
# ============================================================

print("\n========== MAPPED DATASET ==========")

print(
    "Jumlah baris:",
    len(mapped_data)
)

print(
    "Jumlah kolom:",
    len(mapped_data.columns)
)


print("\nKolom:")

print(
    mapped_data.columns.tolist()
)


print("\nContoh mapped data:")

print(
    mapped_data.head()
)


# ============================================================
# 14. FINAL COMMITMENT ITEM MAPPING CHECK
# ============================================================

print(
    "\n========== FINAL COMMITMENT ITEM MAPPING CHECK =========="
)


commitment_check = mapped_data[
    mapped_data["row_type"] == "Commitment_Item"
].copy()


total_commitment = len(
    commitment_check
)


mapped_commitment = (
    commitment_check["commitment_item_id"]
    .notna()
    .sum()
)


unmapped_commitment = (
    commitment_check["commitment_item_id"]
    .isna()
    .sum()
)


print(
    "Total Commitment Item:",
    total_commitment
)

print(
    "Berhasil mapping:",
    mapped_commitment
)

print(
    "Tidak berhasil mapping:",
    unmapped_commitment
)


# ============================================================
# 15. UNMATCHED COMMITMENT ITEM
# ============================================================

if unmapped_commitment > 0:

    unmatched_commitment = commitment_check[
        commitment_check["commitment_item_id"].isna()
    ].copy()


    print(
        "\n========== UNMATCHED COMMITMENT ITEM =========="
    )


    print(
        "Jumlah unmatched:",
        len(unmatched_commitment)
    )


    unique_unmatched = (
        unmatched_commitment[
            [
                "source_entity",
                "detail_code",
                "detail_name"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "source_entity",
                "detail_code"
            ]
        )
    )


    print(
        "\nDaftar unmatched:"
    )


    print(
        unique_unmatched.to_string(
            index=False
        )
    )


    print(
        "\nJumlah kombinasi unik:",
        len(unique_unmatched)
    )


else:

    print(
        "\nSemua Commitment Item berhasil dimapping."
    )


# ============================================================
# 15A. EXPORT DATABASE-READY PAYLOAD
# ============================================================

print("\n========== EXPORT DATABASE-READY PAYLOAD ==========")

budget_master_columns = [
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
    "budget_year"
]

database_ready_export = database_ready[
    budget_master_columns
].copy()

database_ready_export.to_csv(
    "database_ready_budget_master.csv",
    index=False
)

exception_export = unmapped_exception.copy()

exception_export.to_csv(
    "exception_budget_mapping.csv",
    index=False
)

print(
    "Database-ready berhasil diexport:",
    "database_ready_budget_master.csv"
)

print(
    "Jumlah row database-ready:",
    len(database_ready_export)
)

print(
    "Exception berhasil diexport:",
    "exception_budget_mapping.csv"
)

print(
    "Jumlah row exception:",
    len(exception_export)
)

print("\nKolom database-ready:")
print(database_ready_export.columns.tolist())

# ============================================================
# 16. FINAL SUMMARY
# ============================================================

print("\n========================================")
print(" PIPELINE SUMMARY")
print("========================================")


print(
    "Raw sheets:",
    len(raw_data)
)


print(
    "Final rows:",
    len(final_data)
)


print(
    "Mapped rows:",
    len(mapped_data)
)


print(
    "Commitment Item mapped:",
    mapped_commitment,
    "/",
    total_commitment
)


print(
    "Commitment Item unmatched:",
    unmapped_commitment
)


print("\nPipeline selesai.")

print("========================================")