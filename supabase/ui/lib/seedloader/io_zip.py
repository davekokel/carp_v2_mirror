import io
import zipfile

import pandas as pd

from .utils import clean_df


def open_zip(file) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(file.read()))


def read_csv_like(z: zipfile.ZipFile, patterns):
    names = [n for n in z.namelist() if not n.endswith("/")]
    for n in names:
        nl = n.lower()
        if any(p in nl for p in patterns):
            with z.open(n) as f:
                return pd.read_csv(f)
    return None


def load_kit_data(z: zipfile.ZipFile):
    # raw dataframes
    df_02 = read_csv_like(z, ["02_transgenes.csv"])
    df_03 = read_csv_like(z, ["03_transgene_alleles.csv"])
    df_01 = read_csv_like(z, ["01_fish.csv"])
    df_10 = read_csv_like(z, ["10_fish_transgene_alleles.csv"])

    # cleaned
    if df_02 is not None:
        df_02 = clean_df(df_02)
    if df_03 is not None:
        df_03 = clean_df(df_03)
    if df_01 is not None:
        df_01 = clean_df(df_01)
    if df_10 is not None:
        df_10 = clean_df(df_10)

    return df_01, df_02, df_03, df_10
