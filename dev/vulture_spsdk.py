# -----------------------------------------------------------------------------------------------------
# Copyright (C) Refeyn Ltd - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# URL: https://www.refeyn.com
# -----------------------------------------------------------------------------------------------------
from pathlib import Path

import vulture
import vulture.core


def run_vulture() -> None:
    v = vulture.Vulture()
    v.scavenge(
        [
            "./dev/firmware_flashing.py",
            "./spsdk_refeyn/",
        ],
        ["spsdk_refeyn/versioning.py"],
    )
    unused_code: list[vulture.core.Item] = v.get_unused_code()
    fileChanges: dict[Path, list[vulture.core.Item]] = {}

    typeFilter = ["class", "method", "function"]

    allTypes = []
    for unused in unused_code:
        allTypes.append(unused.typ)
        if unused.typ not in typeFilter:
            continue

        if unused.filename in fileChanges:
            fileChanges[unused.filename].append(unused)
        else:
            fileChanges[unused.filename] = [unused]

    for srcFile, linesToRemove in fileChanges.items():
        with srcFile.open("r") as f:
            originalFile = f.readlines()

        for line in reversed(linesToRemove):
            originalFile = originalFile[: line.first_lineno - 1] + originalFile[line.last_lineno :]

        with srcFile.open("w") as f:
            f.writelines(originalFile)


if __name__ == "__main__":
    run_vulture()
