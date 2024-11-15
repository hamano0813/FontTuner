import os
import sys

import ttf_metadata
import utils


def list_files(paths: list[str]):
    paths_set = set()

    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    paths_set.add(os.path.join(root, file))
        else:
            paths_set.add(path)
    return list(paths_set)


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print("please drag and drop font files or font directory to this script")
        sys.exit(1)
    paths = list_files(paths)

    ttf_name_df, ttf_os2_df = ttf_metadata.load_metadata(paths)

    utils.save_temp_xlsx({"name": ttf_name_df, "os2": ttf_os2_df})
