# restore_snapshot.py
import json
import os
from tests.integration.helpers.chain import restore_snapshot


def restore_saved_snapshot(snapshot_name):
    file_dir = os.path.realpath(__file__)
    file_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, '../../temp/snapshots.json')))
    with open(file_path, "r") as f:
        snapshots = json.load(f)

    if snapshot_name not in snapshots:
        print(f"Snapshot {snapshot_name} not found.")
        return

    restore_snapshot({"result": snapshots[snapshot_name]})
    print(f"Restored to snapshot: {snapshot_name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python snapshots.py <snapshot_name>")
    else:
        restore_saved_snapshot(sys.argv[1])
