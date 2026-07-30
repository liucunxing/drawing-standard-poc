import os
import uvicorn

if __name__ == "__main__":
    # 生产环境通过环境变量控制是否热重载，默认关闭
    reload = os.environ.get("UVICORN_RELOAD", "false").lower() == "true"
    port = int(os.environ.get("UVICORN_PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)