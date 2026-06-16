#!/bin/bash
# ============================================================
# drawing-poc 一键部署脚本
# 在服务器上执行：bash deploy.sh
# ============================================================

set -e

PROJECT_DIR="/home/application/image/sinopec"
echo "========================================"
echo " drawing-poc 部署脚本"
echo " 项目目录: $PROJECT_DIR"
echo "========================================"

# ── 1. 检查前置条件 ─────────────────────────────
echo "[1/7] 检查前置条件..."
command -v docker    >/dev/null 2>&1 || { echo "❌ docker 未安装"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ docker-compose 未安装"; exit 1; }
nvidia-smi           >/dev/null 2>&1 || { echo "⚠️  nvidia-smi 不可用，GPU 可能无法使用"; }
echo "  ✅ docker $(docker --version | awk '{print $3}')"
echo "  ✅ docker-compose $(docker-compose --version 2>/dev/null | awk '{print $4}')"

# ── 2. 创建目录结构 ─────────────────────────────
echo "[2/7] 创建目录结构..."
mkdir -p "$PROJECT_DIR/logs/backend"
mkdir -p "$PROJECT_DIR/logs/frontend"
mkdir -p "$PROJECT_DIR/data/tmp"
mkdir -p "$PROJECT_DIR/models/paddle"
mkdir -p "$PROJECT_DIR/models/mineru"
mkdir -p "$PROJECT_DIR/models/huggingface"
echo "  ✅ 目录创建完成"

# ── 3. 配置 .env ────────────────────────────────
echo "[3/7] 检查 .env 文件..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  ⚠️  已从 .env.example 复制，请编辑 $PROJECT_DIR/.env 后重新运行"
    exit 0
else
    echo "  ✅ .env 已存在"
fi

# ── 4. 设置权限 ─────────────────────────────────
echo "[4/7] 设置目录权限..."
chmod -R 755 "$PROJECT_DIR/data"
chmod -R 755 "$PROJECT_DIR/logs"
chmod -R 755 "$PROJECT_DIR/models"
echo "  ✅ 权限设置完成"

# ── 5. 构建镜像 ─────────────────────────────────
echo "[5/7] 构建 Docker 镜像（首次构建约 10-30 分钟）..."
cd "$PROJECT_DIR"
docker-compose build --no-cache 2>&1 | tee "$PROJECT_DIR/logs/build.log"
echo "  ✅ 镜像构建完成（日志: logs/build.log）"

# ── 6. 启动服务 ─────────────────────────────────
echo "[6/7] 启动服务..."
docker-compose up -d
echo "  ✅ 服务已启动"

# ── 7. 健康检查 ─────────────────────────────────
echo "[7/7] 等待服务就绪（最多 2 分钟）..."
sleep 10
for i in $(seq 1 12); do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        echo "  ✅ 后端已就绪 (http://localhost:8000)"
        break
    fi
    echo "  ⏳ 等待后端就绪... ($((i*10))s)"
    sleep 10
done

for i in $(seq 1 6); do
    if curl -sf http://localhost:8501/ > /dev/null 2>&1; then
        echo "  ✅ 前端已就绪 (http://localhost:8501)"
        break
    fi
    echo "  ⏳ 等待前端就绪... ($((i*10))s)"
    sleep 10
done

# ── 完成 ────────────────────────────────────────
echo ""
echo "========================================"
echo " 部署完成！"
echo ""
echo " 📋 访问地址："
echo "    前端（Streamlit）:  http://$(grep SERVER_IP .env | cut -d= -f2):$(grep FRONTEND_PORT .env | cut -d= -f2)"
echo "    后端（API Docs）:   http://$(grep SERVER_IP .env | cut -d= -f2):$(grep BACKEND_PORT .env | cut -d= -f2)/docs"
echo ""
echo " 📂 重要目录："
echo "    项目代码:  $PROJECT_DIR"
echo "    后端日志:  $PROJECT_DIR/logs/backend"
echo "    前端日志:  $PROJECT_DIR/logs/frontend"
echo "    临时文件:  $PROJECT_DIR/data/tmp"
echo "    模型缓存:  $PROJECT_DIR/models"
echo ""
echo " 🔧 常用命令："
echo "    查看日志:    docker-compose logs -f backend"
echo "    重启服务:    docker-compose restart"
echo "    停止服务:    docker-compose down"
echo "    重新构建:    docker-compose up -d --build"
echo "========================================"
