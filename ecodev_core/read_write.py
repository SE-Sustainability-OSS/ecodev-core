"""
Module regrouping low level reading and writing helper methods
"""
import json
import os
from pathlib import Path
from typing import Dict
from typing import List
from typing import Union


def write_json_file(json_data: Union[Dict, List], file_path: Path):
    """
    Write json_data at file_path location
    """
    os.umask(0)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(json_data, indent=4))


def load_json_file(file_path: Path):
    """
    Load a json file at file_path location
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        loaded_json = json.load(f)

    return loaded_json


def make_dir(directory: Path):
    """
    Helper that create the directory "directory" if it doesn't exist yet
    """
    try:
        os.umask(0)
        os.makedirs(directory)
    except OSError as error:
        if not directory.is_dir():
            raise OSError(f'directory={directory!r} should exist but does not.: {error}') from error
