# Usar a imagem base oficial do Python
FROM python:3.9-slim

# Instalar dependências do sistema necessárias para o lxml
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Expor a porta (se necessário)
EXPOSE 80

# Definir a variável de ambiente para a chave de API (substitua 'sua-chave-de-api' pela sua chave real ou use variáveis de ambiente no deployment)
# ENV API_KEY=sua-chave-de-api

# Comando para iniciar a aplicação
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
