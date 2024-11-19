import os
import sys

import pandas as pd

import metadata
import utils

if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print("please drag and drop font files or font directory to this script")
        sys.exit(1)

    if paths[0].endswith(".xlsx"):
        df = pd.read_excel(paths[0], engine="openpyxl", dtype=str, na_values=None, keep_default_na=False)

        metadata.save(df)
    else:
        font_paths = []
        for path in paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        font_paths.append(os.path.join(root, file))
            else:
                font_paths.append(path)
        df = metadata.load([path for path in font_paths if path.lower().endswith((".ttf", ".otf"))])
        utils.save_meta(df)
