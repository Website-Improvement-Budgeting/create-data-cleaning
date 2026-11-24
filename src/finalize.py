import pandas as pd


def create_final_dataset(data_sheets):
    """
    Menggabungkan seluruh sheet hasil transformasi
    menjadi satu dataset final.
    """

    frames = []

    for sheet_name, df in data_sheets.items():

        df = df.copy()

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    final_data = pd.concat(
        frames,
        ignore_index=True
    )

    return final_data