import pandas as pd
import numpy as np
def transform_budget_data(all_sheets):
    """
    Melakukan transformasi awal pada data budget.
    """

    data_sheets = {}

    for sheet_name, df in all_sheets.items():

        # Buang 2 baris awal/header SAP
        df = df.iloc[2:].copy()

        # Reset index
        df.reset_index(drop=True, inplace=True)

        data_sheets[sheet_name] = df

    return data_sheets
def standardize_columns(data_sheets):
    """
    Memberikan nama kolom standar pada setiap sheet.
    """

    column_names = [
        "biro_code",
        "biro_name",
        "row_detail",
        "consumable_budget",
        "consumed_budget",
        "available_amount",
        "current_budget",
        "commitment_actuals",
        "sisa"
    ]

    for sheet_name, df in data_sheets.items():
        df.columns = column_names
        df["source_entity"] = sheet_name.upper()

        data_sheets[sheet_name] = df

    return data_sheets
def clean_code_biro(value):
    """
    Membersihkan dan menstandarkan kode biro.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    # Jika hasil pembacaan berupa 1.0, 10.0, dst.
    if value.endswith(".0"):
        value = value[:-2]

    # Jika berupa angka maksimal 3 digit,
    # tambahkan angka 0 di depan.
    if value.isdigit() and len(value) <= 3:
        value = value.zfill(3)

    return value
def split_detail(value):
    """
    Memisahkan row_detail menjadi detail_code dan detail_name.
    """

    if pd.isna(value):
        return pd.Series([None, None])

    value = str(value).strip()

    # Pisahkan hanya pada spasi pertama
    parts = value.split(maxsplit=1)

    code = parts[0].strip()

    if len(parts) > 1:
        name = parts[1].strip()
    else:
        name = None

    return pd.Series([code, name])
def clean_number(value):
    """
    Membersihkan nilai angka budget
    dan mengubahnya menjadi numeric.
    """

    if pd.isna(value):
        return 0

    # Jika sudah berupa angka
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    value = str(value).strip()

    if value == "":
        return 0

    # Format Indonesia:
    # 22.640.048,00 → 22640048.00
    if "," in value:
        value = value.replace(".", "")
        value = value.replace(",", ".")

    try:
        return float(value)

    except ValueError:
        return 0
def classify_row(row):
    """
    Menentukan jenis setiap baris data SAP.
    """

    detail_code = row["detail_code"]
    parent_code = row["biro_code"]

    # Jika detail code kosong
    if pd.isna(detail_code):
        return "Empty"

    detail_code = str(detail_code).strip()
    parent_code = str(parent_code).strip()

    # Jika detail code sama dengan kode biro
    if detail_code == parent_code:
        return "Parent"

    # Jika detail code diawali S
    if detail_code.upper().startswith("S"):
        return "Funds_Center"

    # Selain itu dianggap Commitment Item
    return "Commitment_Item"
def map_funds_center(data_sheets):
    """
    Menghubungkan setiap Commitment Item
    dengan Funds Center terakhir yang muncul
    dalam kelompok biro yang sama.
    """

    processed_sheets = {}

    for sheet_name, df in data_sheets.items():

        df = df.copy()

        current_parent = None
        current_fc = None
        current_fc_name = None

        mapped_fc = []
        mapped_fc_name = []

        for _, row in df.iterrows():

            parent_code = row["biro_code"]
            row_type = row["row_type"]

            # Jika biro berubah,
            # reset Funds Center
            if parent_code != current_parent:
                current_parent = parent_code
                current_fc = None
                current_fc_name = None

            # Parent
            if row_type == "Parent":
                current_fc = None
                current_fc_name = None

            # Funds Center
            elif row_type == "Funds_Center":
                current_fc = row["detail_code"]
                current_fc_name = row["detail_name"]

            # Simpan konteks Funds Center
            mapped_fc.append(current_fc)
            mapped_fc_name.append(current_fc_name)

        df["current_funds_center"] = mapped_fc
        df["current_funds_center_name"] = mapped_fc_name

        processed_sheets[sheet_name] = df

    return processed_sheets