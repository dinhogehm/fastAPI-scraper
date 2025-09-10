#!/bin/bash

# Script de inicialização da API Multi-Tenant

echo "🚀 Iniciando API Multi-Tenant Scraper..."
echo "======================================="

# Verifica se o Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Instale o Python 3 primeiro."
    exit 1
fi

# Verifica se as dependências estão instaladas
echo "📦 Verificando dependências..."
python3 -c "import fastapi, uvicorn, aiohttp, asyncio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependências não encontradas. Instalando..."
    pip3 install fastapi uvicorn aiohttp asyncio
fi

# Verifica se o arquivo de configuração existe
if [ ! -f "config/api_keys.json" ]; then
    echo "⚙️  Configurando API keys..."
    python3 setup_multitenant.py
fi

# Inicia a API
echo "🌐 Iniciando servidor na porta 8080..."
echo "📖 Documentação disponível em: http://localhost:8080/docs"
echo "🔍 Health check em: http://localhost:8080/health"
echo ""
echo "Para testar o sistema multi-tenant, execute:"
echo "python3 test_multitenant.py"
echo ""
echo "Pressione Ctrl+C para parar o servidor"
echo ""

python3 -m uvicorn api_multitenant:app --host 0.0.0.0 --port 8080 --reload