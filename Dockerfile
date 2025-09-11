FROM python:3.9-slim

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libx11-xcb1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxtst6 \
    fonts-liberation \
    fonts-unifont \
    fonts-ubuntu \
    libxml2-dev \
    libxslt-dev \
    libssl-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores do Playwright (sem --with-deps, já instalamos deps via apt)
RUN python -m playwright install chromium

# Copiar o código da aplicação
COPY . .

# Expor a porta (opcional)
EXPOSE 80

# Comando para iniciar a aplicação usando a variável PORT
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-80}"]
