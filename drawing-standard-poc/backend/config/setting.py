import os
DEFAULTS = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "MYSQL_DB": "drawing_poc",
    "MYSQL_USER": "drawing_poc",
    "MYSQL_PASSWORD": "",
}




def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


