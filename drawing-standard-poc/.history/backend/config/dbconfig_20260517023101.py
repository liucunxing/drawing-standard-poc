import os

env = os.environ.get('ONEPAGE_ENV', 'default')
DATABASES_CONFIG = {
    'default': {
        'NAME': 'localMysql',
        'USER': 'root',
        'PASSWORD': 'root',
        'HOST': 'localhost',
        'PORT': '3306',
        'DRIVER': 'ODBC Driver 17 for SQL Server'
    }
}

DATABASES = DATABASES_CONFIG.get(env, None)
if not DATABASES:
    DATABASES = DATABASES_CONFIG.get('default')

warehouse_database_name = DATABASES.get('NAME')
sqlalchemy_connect_string = "mssql+pyodbc://{}:{}@{}:{}/{}?driver={}&autocommit=true".format(DATABASES.get('USER'),
                                                                                             parse.quote_plus(DATABASES.get('PASSWORD')),
                                                                                             DATABASES.get('HOST',
                                                                                                           '127.0.0.1'),
                                                                                             DATABASES.get('PORT'),
                                                                                             DATABASES.get('NAME'),
                                                                                             DATABASES.get('DRIVER'))
connect_string = "Driver={};Server={},{};Database={};Uid={};Pwd={};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;ConnectRetryCount=3;ConnectRetryInterval=10;".format(
    DATABASES.get('DRIVER'),
    DATABASES.get('HOST', '127.0.0.1'),
    DATABASES.get('PORT'),
    DATABASES.get('NAME'),
    DATABASES.get('USER'),
    DATABASES.get('PASSWORD'))

DATA_PLATFORM_URI = connect_string
SQLALCHEMY_DATA_PLATFORM_URI = sqlalchemy_connect_string