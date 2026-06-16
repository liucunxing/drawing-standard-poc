import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router


# ─────────────────────────────────────────────
# 日志配置：同时输出到控制台和文件
# ─────────────────────────────────────────────
def setup_logging() -> None:
    log_dir  = Path(os.environ.get("LOG_DIR", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    # 格式：时间 | 级别 | 模块 | 消息
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件：单文件最大 50 MB，保留最近 10 个历史文件
    file_handler = RotatingFileHandler(
        log_file, maxBytes=50 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    # 控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    # 配置根 logger（所有模块自动继承）
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # 降低第三方库的日志级别，避免刷屏
    for noisy in ("uvicorn.access", "httpx", "httpcore", "aiohttp", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ─────────────────────────────────────────────
# FastAPI 应用
# ─────────────────────────────────────────────
app = FastAPI(
    title="drawing-poc",
    description="工程图纸智能识别 POC",
    version="1.0.0",
)

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    setup_logging()
    logging.getLogger(__name__).info(
        "服务启动完成 | LOG_DIR=%s", os.environ.get("LOG_DIR", "./logs")
    )


@app.get("/")
def root():
    return {"message": "服务运行中"}    