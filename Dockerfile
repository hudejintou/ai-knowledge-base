# 基础镜像：与本机 Python 版本一致
FROM python:3.13-slim

# PYTHONPATH=/app 让容器内能 import rag 包（rag 位于 /app/rag）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# 先只复制依赖清单并安装。这样只要 requirements.txt 没变，改代码时不会重新安装依赖，构建更快
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制代码：rag 是核心模块，backend 是 Django 工程
COPY rag/ ./rag/
COPY backend/ ./backend/

# 后续命令（manage.py、gunicorn）都在 backend 目录下执行
WORKDIR /app/backend

EXPOSE 8000

# 默认命令：用 gunicorn 启动 Django。compose 文件会覆盖它，先执行 migrate
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]