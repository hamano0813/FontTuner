import os
import sys

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

    df = metadata.load(path_list)
    if not df.empty:
        utils.write_excel(df)

    dfs = [utils.read_excel(path) for path in path_list if path.lower().endswith(".xlsx")]
    if dfs:
        metadata.save(dfs)
