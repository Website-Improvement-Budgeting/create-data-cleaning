import pandas as pd


REQUIRED_COLUMNS = [
    "biro_code",
    "biro_name",
    "row_detail",
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "current_budget",
    "commitment_actuals",
    "sisa",
    "source_entity",
    "detail_code",
    "detail_name",
    "row_type",
    "current_funds_center",
    "current_funds_center_name"
]


BUDGET_COLUMNS = [
    "consumable_budget",
    "consumed_budget",
    "available_amount",
    "current_budget",
    "commitment_actuals",
    "sisa"
]


VALID_ROW_TYPES = {
    "Parent",
    "Funds_Center",
    "Commitment_Item",
    "Empty"
}


def validate_budget_data(data_sheets):
    """
    Melakukan validasi terhadap hasil transformasi data budget.
    """

    validation_results = []

    for sheet_name, df in data_sheets.items():

        errors = []
        warnings = []

        # =====================================
        # 1. Validasi jumlah baris
        # =====================================

        row_count = len(df)

        if row_count == 0:
            errors.append("Sheet kosong.")

        # =====================================
        # 2. Validasi struktur kolom
        # =====================================

        missing_columns = [
            col for col in REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing_columns:
            errors.append(
                f"Kolom wajib tidak ditemukan: {missing_columns}"
            )

        # Jika struktur kolom belum lengkap,
        # lanjut ke sheet berikutnya
        if missing_columns:
            validation_results.append({
                "sheet_name": sheet_name,
                "status": "ERROR",
                "row_count": row_count,
                "errors": errors,
                "warnings": warnings
            })
            continue

        # =====================================
        # 3. Validasi biro_code
        # =====================================

        empty_biro = df["biro_code"].isna().sum()

        if empty_biro > 0:
            warnings.append(
                f"{empty_biro} baris memiliki biro_code kosong."
            )

        # =====================================
        # 4. Validasi detail_code
        # =====================================

        empty_detail = df["detail_code"].isna().sum()

        if empty_detail > 0:
            warnings.append(
                f"{empty_detail} baris memiliki detail_code kosong."
            )

        # =====================================
        # 5. Validasi kolom angka
        # =====================================

        for col in BUDGET_COLUMNS:

            if not pd.api.types.is_numeric_dtype(df[col]):
                errors.append(
                    f"Kolom {col} belum bertipe numeric."
                )

        # =====================================
        # 6. Validasi row_type
        # =====================================

        invalid_row_types = set(df["row_type"].dropna()) - VALID_ROW_TYPES

        if invalid_row_types:
            errors.append(
                f"Ditemukan row_type tidak dikenal: "
                f"{invalid_row_types}"
            )

        # =====================================
        # 7. Validasi Funds Center
        # =====================================

        fc_rows = df["row_type"] == "Funds_Center"

        invalid_fc_mapping = df[
            fc_rows
            & (
                df["current_funds_center"]
                != df["detail_code"]
            )
        ]

        if len(invalid_fc_mapping) > 0:
            errors.append(
                f"{len(invalid_fc_mapping)} Funds Center "
                f"memiliki mapping yang tidak sesuai."
            )

        # =====================================
        # 8. Validasi Commitment Item
        # =====================================

        ci_with_fc = df[
            (df["row_type"] == "Commitment_Item")
            & df["current_funds_center"].notna()
        ]

        ci_without_fc_name = ci_with_fc[
            ci_with_fc["current_funds_center_name"].isna()
        ]

        if len(ci_without_fc_name) > 0:
            errors.append(
                f"{len(ci_without_fc_name)} Commitment Item "
                f"memiliki Funds Center tetapi nama FC kosong."
            )

        # =====================================
        # 9. Validasi Parent
        # =====================================

        parent_rows = df["row_type"] == "Parent"

        parent_with_fc = df[
            parent_rows
            & df["current_funds_center"].notna()
        ]

        if len(parent_with_fc) > 0:
            errors.append(
                f"{len(parent_with_fc)} Parent memiliki "
                f"Funds Center yang aktif."
            )

        # =====================================
        # 10. Statistik row type
        # =====================================

        row_type_counts = (
            df["row_type"]
            .value_counts()
            .to_dict()
        )

        # =====================================
        # STATUS
        # =====================================

        if errors:
            status = "ERROR"
        elif warnings:
            status = "WARNING"
        else:
            status = "PASS"

        validation_results.append({
            "sheet_name": sheet_name,
            "status": status,
            "row_count": row_count,
            "parent_count": row_type_counts.get(
                "Parent", 0
            ),
            "funds_center_count": row_type_counts.get(
                "Funds_Center", 0
            ),
            "commitment_item_count": row_type_counts.get(
                "Commitment_Item", 0
            ),
            "errors": errors,
            "warnings": warnings
        })

    return validation_results