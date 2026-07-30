# -*- coding:utf-8 -*-
import logging
import os
import dotenv
import pymysql
import threading
from pymysql import cursors
from backend.config.setting import DEFAULTS

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


def get_env(key):
    return os.environ.get(key, DEFAULTS.get(key))


def get_bool_env(key):
    return get_env(key).lower() == 'true'


class Config:
    """Application configuration class."""

    def __init__(self):

        self.SECRET_KEY = get_env('SECRET_KEY')

        self.EXECUTOR_TYPE = 'thread'
        self.EXECUTOR_MAX_WORKERS = os.cpu_count() * 2


class SQLManager(object):
    # 初始化实例方法
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.lock = threading.Lock()  # 创建一个锁
        self.connect()

    # 连接数据库
    def connect(self):
        self.conn = pymysql.connect(
            host=DEFAULTS["MYSQL_HOST"],
            port=int(DEFAULTS["MYSQL_PORT"]),
            user=DEFAULTS["MYSQL_USER"],
            passwd=DEFAULTS["MYSQL_PASSWORD"],
            db=DEFAULTS["MYSQL_DB"],
            charset="utf8mb4"
        )
        self.cursor = self.conn.cursor(cursor=cursors.DictCursor)

    # 查询多条数据
    def get_list(self, sql, args=None):
        try:
            self.cursor.execute(sql, args)
            result = self.cursor.fetchall()
            return result
        except pymysql.MySQLError as e:
            logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
            return None

    # 查询单条数据
    def get_one(self, sql, args=None):
        try:
            self.cursor.execute(sql, args)
            result = self.cursor.fetchone()
            return result
        except pymysql.MySQLError as e:
            logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
            return None

    def query_one(self, sql, args=None):
        try:
            self.cursor.execute(sql, args)
            result = self.cursor.fetchone()
            return result
        except pymysql.MySQLError as e:
            logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
            return None

    # 执行单条SQL语句
    def modify(self, sql, args=None):
        with self.lock:  # 获取锁
            try:
                self.cursor.execute(sql, args)
                affected_rows = self.cursor.rowcount
                self.conn.commit()
                return affected_rows
            except pymysql.MySQLError as e:
                logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
                self.conn.rollback()  # 如果发生错误，回滚事务
                return 0  # 发生异常时返回 0 表示没有成功

    # 执行多条SQL语句
    def multi_modify(self, sql, args=None):
        with self.lock:  # 获取锁
            try:
                self.cursor.executemany(sql, args)
                self.conn.commit()
            except pymysql.MySQLError as e:
                logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
                self.conn.rollback()  # 如果发生错误，回滚事务

    # 创建单条记录的语句
    def create(self, sql, args=None):
        with self.lock:  # 获取锁
            last_id = None
            try:
                self.cursor.execute(sql, args)
                self.conn.commit()
                last_id = self.cursor.lastrowid
            except pymysql.MySQLError as e:
                logger.error(f"【ERROR】[SQL执行异常]:: {e} sql:: {sql} args:: {args}")
                self.conn.rollback()  # 如果发生错误，回滚事务
            return last_id

    # 关闭数据库cursor和连接
    def close(self):
        self.cursor.close()
        self.conn.close()

    # 进入with语句自动执行
    def __enter__(self):
        return self

    # 退出with语句块自动执行
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"【ERROR】::{exc_type}: {exc_val}")
        self.close()

    def query(self, sql, params=None):
        """ 执行查询操作 """
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchall()
