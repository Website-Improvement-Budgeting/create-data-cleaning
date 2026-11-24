import pandas as pd


def extract_budget_data(file_path):
    """
    Membaca data budget dari file Excel.
    """

    sheet_budget = [
        "Kantor Pusat Silog",
        "LOGISTIK",
        "BUBI",
        "IKN",
        "VUBA",
        "VUDS",
        "VULS"
    ]

    all_sheets = pd.read_excel(
        file_path,
        sheet_name=sheet_budget,
        header=None
    )

    return all_sheets