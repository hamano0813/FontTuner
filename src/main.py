import os
import sys

import pandas as pd

import metadata
import utils


if __name__ == "__main__":
    paths = sys.argv[1:]

    path_list = []
    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    path_list.append(os.path.join(root, file))
        else:
            path_list.append(path)

    if not path_list and os.path.exists("metadata.xlsx"):
        path_list.append("metadata.xlsx")

    metadata_df = metadata.load([path for path in path_list if path.lower().endswith((".ttf", ".otf"))])
    if not metadata_df.empty:
        utils.write_excel(metadata_df)

    dfs = [
        pd.read_excel(path, sheet_name="metadata", engine="openpyxl", dtype=str, na_values="", keep_default_na=False)
        for path in path_list
        if path.lower().endswith(".xlsx")
    ]
    if dfs:
        metadata.save(dfs)
