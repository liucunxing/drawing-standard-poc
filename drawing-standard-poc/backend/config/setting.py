import os
import sys
import traceback

import dotenv



DEFAULTS = {
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_DB": "drawing-poc",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "root",
}




def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


