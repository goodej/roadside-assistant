import json
import os


def _save_json(fp, d: dict):
    make_dir_if_not_existing(fp)
    with open(fp, 'w') as f:
        json.dump(d, f, indent=4)

def make_dir_if_not_existing(fp):
    pdir = os.path.dirname(fp)
    if not os.path.exists(pdir):
        os.mkdir(pdir)