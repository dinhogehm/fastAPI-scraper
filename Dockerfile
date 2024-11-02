FROM python:3.9-slim

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    libz-dev \
    libffi-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Comando para iniciar a aplicação usando a variável PORT
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-80}"]
