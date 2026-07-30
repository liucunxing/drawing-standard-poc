# -*- coding:utf-8 -*-
"""
应用配置服务 —— 从数据库 system_config 表加载配置项

使用方式:
    from backend.config.app_config import app_config

    tmp_dir = app_config.tmp_dir
    paddle_models_root = app_config.paddle_models_root

初始化时机:
    应用启动时自动从数据库读取所有配置项并缓存到内存中。
    若数据库不可用则回退到代码内置默认值（开发环境兜底）。
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ============================================
# 内置默认值（仅当数据库不可用时作为兜底）
# ============================================
_BUILTIN_DEFAULTS: Dict[str, str] = {
    "tmp_dir": str(Path(__file__).resolve().parents[1] / "tmp"),
    # [上线待替换] paddle_models_root: 生产环境请通过 system_config 表或环境变量配置
    # 原 Windows 开发路径: D:\work\Develop\conda_envs\.paddlex\official_models
    # Linux 示例: /opt/paddlex/official_models
    "paddle_models_root": "",
}


class AppConfig:
    """
    应用级配置单例。

    启动时从 system_config 表一次性加载全部 key-value 到内存字典，
    后续通过属性访问，无需再次查询数据库。
    """

    def __init__(self) -> None:
        self._config: Dict[str, str] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # 公开属性（带类型提示，方便 IDE 补全）
    # ------------------------------------------------------------------

    @property
    def tmp_dir(self) -> Path:
        """临时目录（存放 page_images / table_blocks / uploads / markdown 等）"""
        return Path(self.get("tmp_dir"))

    @property
    def paddle_models_root(self) -> Path:
        """PaddleOCR 本地模型根目录"""
        return Path(self.get("paddle_models_root"))

    # ------------------------------------------------------------------
    # 通用取值方法
    # ------------------------------------------------------------------

    def get(self, key: str, default: Optional[str] = None) -> str:
        """获取配置值；优先数据库缓存，其次内置默认值，最后返回传入的 default。"""
        self._ensure_loaded()
        if key in self._config:
            return self._config[key]
        builtin = _BUILTIN_DEFAULTS.get(key)
        if builtin is not None:
            return builtin
        return default or ""

    def get_path(self, key: str, default: Optional[str] = None) -> Path:
        """获取配置值并返回 Path 对象。"""
        return Path(self.get(key, default))

    def reload(self) -> None:
        """强制重新从数据库加载配置（用于运行时热更新场景）。"""
        self._loaded = False
        self._ensure_loaded()

    def as_dict(self) -> Dict[str, str]:
        """返回所有配置的副本（调试/日志用）。"""
        self._ensure_loaded()
        return dict(self._config)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_from_database()

    def _load_from_database(self) -> None:
        """从 system_config 表读取全部配置项到内存。"""
        try:
            from backend.config.config import SQLManager

            with SQLManager() as db:
                rows = db.get_list(
                    "SELECT key_name, key_value FROM system_config"
                )
                if rows:
                    for row in rows:
                        self._config[row["key_name"]] = row["key_value"]
                    logger.info(
                        "[AppConfig] 从数据库加载 %d 项配置: %s",
                        len(self._config),
                        list(self._config.keys()),
                    )
                else:
                    logger.warning(
                        "[AppConfig] system_config 表为空或无数据，使用内置默认值"
                    )
        except Exception as exc:
            logger.warning(
                "[AppConfig] 数据库读取失败，使用内置默认值。异常: %s", exc
            )
        finally:
            # 无论成功与否都标记为已加载，避免反复重试
            self._loaded = True


# ============================================
# 全局单例 —— 导入即可使用
# ============================================
app_config = AppConfig()
