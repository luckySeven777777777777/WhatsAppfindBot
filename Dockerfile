# 使用 Playwright 官方提供的 Python 镜像（自带所有浏览器依赖）
FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 关键一步：在 Docker 内部安装 Chromium
RUN playwright install chromium

# 启动命令
CMD ["python", "whatsapp_check.py"]