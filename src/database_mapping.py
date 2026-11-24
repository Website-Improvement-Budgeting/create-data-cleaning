"""
Database Mapping

Mengubah FINAL DATASET hasil pipeline menjadi struktur
yang sesuai dengan database existing.
"""

import pandas as pd

from src.import_existing import load_existing_master


# ============================================================
# ENTITY MAPPING
# ============================================================

ENTITY_MAPPING = {
    "BUBI": 1,
    "IKN": 2,
    "KANTOR PUSAT SILOG": 3,
    "LOGISTIK": 4,
    "VUBA": 5,
    "VUDS": 6,
    "VULS": 7,
}


# ============================================================
# DATABASE MAPPING
# ============================================================

def map_final_dataset_to_database(final_data):
    """
    Mapping FINAL DATASET ke ID master database existing.

    Mapping:
    1. source_entity -> entity_id
    2. entity_id + biro_code -> biro_id
    3. current_funds_center -> funds_center_id
    4. detail_code -> commitment_item_id
       menggunakan direct mapping ke commitment_item
    5. Jika direct mapping tidak ditemukan,
       gunakan master_ci sebagai fallback berdasarkan
       range from_gl_account sampai to_gl_account.
    """

    print("\n========================================")
    print(" DATABASE MAPPING")
    print("========================================")

    df = final_data.copy()

    # ========================================================
    # 1. ENTITY MAPPING
    # ========================================================

    print("\n[1] Mapping ENTITY...")

    df["source_entity"] = (
        df["source_entity"]
        .astype("string")
        .str.strip()
    )

    df["entity_id"] = (
        df["source_entity"]
        .map(ENTITY_MAPPING)
    )

    print(
        "Entity berhasil dimapping:",
        df["entity_id"].notna().sum(),
        "/",
        len(df)
    )

    # ========================================================
    # 2. LOAD MASTER DATABASE
    # ========================================================

    print("\n[2] Loading existing master...")

    masters = load_existing_master()

    biro_master = masters["biro"].copy()
    funds_center_master = masters["funds_center"].copy()
    commitment_item_master = masters["commitment_item"].copy()
    master_ci = masters["master_ci"].copy()

    # ========================================================
    # 3. NORMALISASI DATA MAPPING
    # ========================================================

    print("\n[3] Normalisasi data mapping...")

    # --------------------------------------------------------
    # FINAL DATASET
    # --------------------------------------------------------

    df["biro_code"] = (
        df["biro_code"]
        .astype("string")
        .str.strip()
    )

    df["current_funds_center"] = (
        df["current_funds_center"]
        .astype("string")
        .str.strip()
    )

    df["detail_code"] = (
        df["detail_code"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # BIRO MASTER
    # --------------------------------------------------------

    biro_master["biro_id"] = pd.to_numeric(
        biro_master["biro_id"],
        errors="coerce"
    )

    biro_master["entity_id"] = pd.to_numeric(
        biro_master["entity_id"],
        errors="coerce"
    )

    biro_master["biro_code"] = (
        biro_master["biro_code"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # FUNDS CENTER MASTER
    # --------------------------------------------------------

    funds_center_master["funds_center_id"] = pd.to_numeric(
        funds_center_master["funds_center_id"],
        errors="coerce"
    )

    funds_center_master["funds_center_code"] = (
        funds_center_master["funds_center_code"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # COMMITMENT ITEM MASTER
    # --------------------------------------------------------

    commitment_item_master["commitment_item_id"] = pd.to_numeric(
        commitment_item_master["commitment_item_id"],
        errors="coerce"
    )

    commitment_item_master["commitment_item_code"] = (
        commitment_item_master["commitment_item_code"]
        .astype("string")
        .str.strip()
    )

    # --------------------------------------------------------
    # MASTER CI
    # --------------------------------------------------------

    master_ci["master_ci_id"] = pd.to_numeric(
        master_ci["master_ci_id"],
        errors="coerce"
    )

    master_ci["from_gl_account"] = pd.to_numeric(
        master_ci["from_gl_account"],
        errors="coerce"
    )

    master_ci["to_gl_account"] = pd.to_numeric(
        master_ci["to_gl_account"],
        errors="coerce"
    )

    master_ci["target_commitment_item_id"] = pd.to_numeric(
        master_ci["target_commitment_item_id"],
        errors="coerce"
    )

    # ========================================================
    # 4. MAP BIRO
    # ========================================================

    print("\n[4] Mapping BIRO...")

    df = df.merge(
        biro_master[
            [
                "biro_id",
                "entity_id",
                "biro_code",
            ]
        ].rename(
            columns={
                "entity_id": "master_entity_id"
            }
        ),
        how="left",
        left_on=[
            "entity_id",
            "biro_code"
        ],
        right_on=[
            "master_entity_id",
            "biro_code"
        ],
    )

    df = df.drop(
        columns=["master_entity_id"]
    )

    print(
        "Biro berhasil dimapping:",
        df["biro_id"].notna().sum(),
        "/",
        len(df)
    )

    # ========================================================
    # 5. MAP FUNDS CENTER
    # ========================================================

    print("\n[5] Mapping FUNDS CENTER...")

    df = df.merge(
        funds_center_master[
            [
                "funds_center_id",
                "funds_center_code",
            ]
        ],
        how="left",
        left_on="current_funds_center",
        right_on="funds_center_code",
    )

    df = df.drop(
        columns=["funds_center_code"]
    )

    print(
        "Funds Center berhasil dimapping:",
        df["funds_center_id"].notna().sum(),
        "/",
        len(df)
    )

    # ========================================================
    # 6. MAP COMMITMENT ITEM - DIRECT
    # ========================================================

    print("\n[6] Mapping COMMITMENT ITEM - DIRECT...")

    df = df.merge(
        commitment_item_master[
            [
                "commitment_item_id",
                "commitment_item_code",
            ]
        ],
        how="left",
        left_on="detail_code",
        right_on="commitment_item_code",
    )

    df = df.drop(
        columns=["commitment_item_code"]
    )

    df["commitment_item_id"] = pd.to_numeric(
        df["commitment_item_id"],
        errors="coerce"
    )

    # Hanya Commitment Item yang dihitung
    commitment_mask = (
        df["row_type"] == "Commitment_Item"
    )

    direct_mapped = (
        df.loc[
            commitment_mask,
            "commitment_item_id"
        ]
        .notna()
        .sum()
    )

    total_commitment = commitment_mask.sum()

    print(
        "Direct mapping berhasil:",
        direct_mapped,
        "/",
        total_commitment
    )

    # ========================================================
    # 7. MASTER CI FALLBACK
    # ========================================================

    print("\n[7] Mapping melalui MASTER CI...")

    # Konversi detail_code menjadi angka
    df["_detail_code_num"] = pd.to_numeric(
        df["detail_code"],
        errors="coerce"
    )

    # Hanya baris Commitment Item yang:
    # - belum berhasil direct mapping
    # - detail_code berupa angka
    unmatched_mask = (
        (df["row_type"] == "Commitment_Item")
        &
        (df["commitment_item_id"].isna())
        &
        (df["_detail_code_num"].notna())
    )

    mapped_by_master_ci = 0

    for idx in df.index[unmatched_mask]:

        code = df.at[
            idx,
            "_detail_code_num"
        ]

        matches = master_ci[
            (
                master_ci["from_gl_account"]
                <= code
            )
            &
            (
                master_ci["to_gl_account"]
                >= code
            )
        ]

        if matches.empty:
            continue

        # Ambil mapping pertama
        target_id = matches.iloc[0][
            "target_commitment_item_id"
        ]

        if pd.isna(target_id):
            continue

        df.at[
            idx,
            "commitment_item_id"
        ] = int(target_id)

        mapped_by_master_ci += 1

    print(
        "Berhasil dimapping melalui MASTER CI:",
        mapped_by_master_ci
    )

    # Hapus kolom bantuan
    df = df.drop(
        columns=["_detail_code_num"]
    )

    # ========================================================
    # 8. FINAL COMMITMENT ITEM CHECK
    # ========================================================

    print(
        "\n========== COMMITMENT ITEM FINAL CHECK =========="
    )

    commitment_check = df[
        df["row_type"] == "Commitment_Item"
    ]

    print(
        "Total Commitment Item:",
        len(commitment_check)
    )

    print(
        "Berhasil mapping:",
        commitment_check[
            "commitment_item_id"
        ].notna().sum()
    )

    print(
        "Tidak berhasil mapping:",
        commitment_check[
            "commitment_item_id"
        ].isna().sum()
    )

    # ========================================================
    # 9. MAPPING CHECK
    # ========================================================

    print(
        "\n========================================"
    )
    print(
        " MAPPING CHECK"
    )
    print(
        "========================================"
    )

    # --------------------------------------------------------
    # ENTITY
    # --------------------------------------------------------

    print("\nEntity tidak ter-mapping:")

    entity_unmatched = df.loc[
        df["entity_id"].isna(),
        "source_entity"
    ].drop_duplicates()

    print(
        entity_unmatched.tolist()
    )

    # --------------------------------------------------------
    # BIRO
    # --------------------------------------------------------

    print("\nBiro tidak ter-mapping:")

    biro_unmatched = df.loc[
        df["biro_id"].isna(),
        [
            "source_entity",
            "entity_id",
            "biro_code"
        ]
    ].drop_duplicates()

    print(
        biro_unmatched.head(30)
    )

    # --------------------------------------------------------
    # FUNDS CENTER
    # --------------------------------------------------------

    print("\nFunds Center tidak ter-mapping:")

    funds_unmatched = df.loc[
        df["funds_center_id"].isna(),
        [
            "source_entity",
            "current_funds_center"
        ]
    ].drop_duplicates()

    print(
        funds_unmatched.head(30)
    )

    # --------------------------------------------------------
    # COMMITMENT ITEM
    # --------------------------------------------------------

    print("\nCommitment Item tidak ter-mapping:")

    commitment_unmatched = df.loc[
        (
            (df["row_type"] == "Commitment_Item")
            &
            (df["commitment_item_id"].isna())
        ),
        [
            "source_entity",
            "biro_code",
            "detail_code",
            "detail_name"
        ]
    ].drop_duplicates()

    print(
        commitment_unmatched.head(50)
    )

    # ========================================================
    # 10. RETURN
    # ========================================================

    return df