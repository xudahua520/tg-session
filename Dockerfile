FROM python:3.9-slim

WORKDIR /app

# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p sessions

# 修改端口为 8899
EXPOSE 8899

# 修改启动命令端口为 8899
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8899"]