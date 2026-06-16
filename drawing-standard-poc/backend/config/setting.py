import os
import sys
import traceback

import dotenv



DEFAULTS = {
    "MYSQL_HOST": "10.150.18.21",
    "MYSQL_PORT": "31002",
    "MYSQL_DB": "drawing-poc",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "smartvision",
}




def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


