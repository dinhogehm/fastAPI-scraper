#!/usr/bin/env python3
"""
Script de configuração para inicializar o sistema multi-tenant.
Configura API keys, tenants e inicializa o serviço.
"""

import json
import os
from datetime import datetime

def setup_api_keys():
    """Configura as API keys de exemplo para teste."""
    api_keys_config = {
        "api_keys": {
            "test_key_123": {
                "tenant_id": "tenant_1",
                "user_id": "user_1",
                "name": "Usuário de Teste 1",
                "created_at": datetime.now().isoformat(),
                "active": True,
                "permissions": ["scrape", "status", "stats"]
            },
            "demo_key_456": {
                "tenant_id": "tenant_1", 
                "user_id": "user_2",
                "name": "Usuário de Teste 2",
                "created_at": datetime.now().isoformat(),
                "active": True,
                "permissions": ["scrape", "status"]
            },
            "prod_key_789": {
                "tenant_id": "tenant_2",
                "user_id": "user_3", 
                "name": "Usuário de Produção",
                "created_at": datetime.now().isoformat(),
                "active": True,
                "permissions": ["scrape", "status", "stats"]
            },
            "admin_key_000": {
                "tenant_id": "admin",
                "user_id": "admin_1",
                "name": "Administrador",
                "created_at": datetime.now().isoformat(),
                "active": True,
                "permissions": ["scrape", "status", "stats", "admin"]
            }
        },
        "tenants": {
            "tenant_1": {
                "name": "Empresa A",
                "plan": "premium",
                "rate_limits": {
                    "requests_per_minute": 30,
                    "max_concurrent_tasks": 8
                },
                "created_at": datetime.now().isoformat(),
                "active": True
            },
            "tenant_2": {
                "name": "Empresa B", 
                "plan": "basic",
                "rate_limits": {
                    "requests_per_minute": 15,
                    "max_concurrent_tasks": 3
                },
                "created_at": datetime.now().isoformat(),
                "active": True
            },
            "admin": {
                "name": "Administração",
                "plan": "unlimited",
                "rate_limits": {
                    "requests_per_minute": 1000,
                    "max_concurrent_tasks": 50
                },
                "created_at": datetime.now().isoformat(),
                "active": True
            }
        }
    }
    
    # Salva configuração em arquivo
    config_file = "config/api_keys.json"
    os.makedirs("config", exist_ok=True)
    
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(api_keys_config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Configuração salva em: {config_file}")
    return api_keys_config

def create_env_file():
    """Cria arquivo .env com configurações padrão."""
    env_content = """
# Configurações da API Multi-Tenant
API_HOST=0.0.0.0
API_PORT=8080
API_RELOAD=true

# Rate Limiting
DEFAULT_RATE_LIMIT_PER_MINUTE=20
DEFAULT_MAX_CONCURRENT_TASKS=5

# Configurações de Scraping
DEFAULT_REQUEST_TIMEOUT=30
MAX_SCRAPE_LIMIT=100
DEFAULT_SCRAPE_LIMIT=10

# Configurações de Segurança
API_KEY_HEADER=Authorization
API_KEY_PREFIX=Bearer

# Configurações de Log
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# Configurações de Webhook
WEBHOOK_TIMEOUT=10
WEBHOOK_RETRY_ATTEMPTS=3

# Configurações de Cache
CACHE_TTL=300
CACHE_MAX_SIZE=1000
""".strip()
    
    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print("✅ Arquivo .env criado com configurações padrão")

def create_startup_script():
    """Cria script de inicialização."""
    startup_content = """
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
""".strip()
    
    with open("start_multitenant.sh", "w", encoding="utf-8") as f:
        f.write(startup_content)
    
    # Torna o script executável
    os.chmod("start_multitenant.sh", 0o755)
    
    print("✅ Script de inicialização criado: start_multitenant.sh")

def create_readme():
    """Cria documentação README para o sistema multi-tenant."""
    readme_content = """
# Sistema Multi-Tenant de Scraping

## Visão Geral

Este sistema implementa uma API de scraping com suporte completo a multi-tenancy, garantindo isolamento seguro entre diferentes organizações e usuários.

## Características Principais

### 🏢 Multi-Tenancy
- **Isolamento completo** entre tenants (organizações)
- **Controle de acesso** baseado em API keys
- **Configurações personalizadas** por tenant
- **Estatísticas separadas** por organização

### 🚦 Rate Limiting
- **Limite por minuto** configurável por tenant
- **Controle de concorrência** (tarefas simultâneas)
- **Diferentes planos** (basic, premium, unlimited)
- **Bloqueio automático** quando limites são excedidos

### 🔒 Segurança
- **Autenticação via API Key** (Bearer token)
- **Validação de permissões** por endpoint
- **Isolamento de dados** entre tenants
- **Logs de auditoria** por usuário

### 📊 Monitoramento
- **Estatísticas em tempo real** por tenant
- **Health check** do sistema
- **Métricas de performance** por usuário
- **Histórico de requisições**

## Configuração Rápida

### 1. Configurar o Sistema
```bash
# Executar configuração inicial
python3 setup_multitenant.py
```

### 2. Iniciar a API
```bash
# Usar script de inicialização
./start_multitenant.sh

# OU iniciar manualmente
python3 -m uvicorn api_multitenant:app --host 0.0.0.0 --port 8080 --reload
```

### 3. Testar o Sistema
```bash
# Executar testes completos
python3 test_multitenant.py
```

## API Keys de Teste

O sistema vem pré-configurado com as seguintes API keys para teste:

| API Key | Tenant | Usuário | Plano | Limite/min | Concorrência |
|---------|--------|---------|-------|------------|-------------|
| `test_key_123` | tenant_1 | user_1 | premium | 30 | 8 |
| `demo_key_456` | tenant_1 | user_2 | premium | 30 | 8 |
| `prod_key_789` | tenant_2 | user_3 | basic | 15 | 3 |
| `admin_key_000` | admin | admin_1 | unlimited | 1000 | 50 |

## Endpoints Disponíveis

### 🔍 Scraping
```http
POST /scrape
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "url": "https://example.com",
  "limit": 10,
  "callback_url": "https://webhook.site/..."
}
```

### 📋 Status da Tarefa
```http
GET /status/{task_id}
Authorization: Bearer {api_key}
```

### 📊 Estatísticas
```http
GET /stats
Authorization: Bearer {api_key}
```

### 🏥 Health Check
```http
GET /health
```

## Exemplos de Uso

### Iniciar um Scraping
```bash
curl -X POST "http://localhost:8080/scrape" \
  -H "Authorization: Bearer test_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "limit": 5
  }'
```

### Verificar Status
```bash
curl -X GET "http://localhost:8080/status/task_123" \
  -H "Authorization: Bearer test_key_123"
```

### Obter Estatísticas
```bash
curl -X GET "http://localhost:8080/stats" \
  -H "Authorization: Bearer test_key_123"
```

## Estrutura do Projeto

```
├── api_multitenant.py          # API principal multi-tenant
├── app/
│   ├── multi_tenant_service.py # Serviços multi-tenant
│   ├── services.py            # Serviços de scraping
│   └── models.py              # Modelos de dados
├── config/
│   └── api_keys.json          # Configuração de API keys
├── test_multitenant.py        # Testes do sistema
├── setup_multitenant.py       # Configuração inicial
├── start_multitenant.sh       # Script de inicialização
└── CONCURRENCY_ANALYSIS.md    # Análise de concorrência
```

## Resolução de Problemas

### Erro 401 - Unauthorized
- Verifique se a API key está correta
- Confirme o formato: `Authorization: Bearer {api_key}`
- Verifique se a API key está ativa

### Erro 429 - Rate Limited
- Aguarde o reset do limite (1 minuto)
- Verifique o plano do tenant
- Considere upgrade para plano premium

### Erro 404 - Task Not Found
- Verifique se o task_id está correto
- Confirme se você tem acesso ao tenant da tarefa
- Tarefas são isoladas por tenant

## Monitoramento

O sistema fornece métricas detalhadas:

- **Total de requisições** por tenant
- **Tarefas ativas/concluídas/falhadas**
- **Rate limiting atual**
- **Uso de concorrência**
- **Tempo de resposta médio**

## Segurança

- ✅ Isolamento completo entre tenants
- ✅ Validação de API keys
- ✅ Rate limiting por tenant
- ✅ Logs de auditoria
- ✅ Controle de permissões
- ✅ Validação de entrada

## Próximos Passos

1. **Persistência**: Implementar banco de dados
2. **Cache**: Redis para performance
3. **Filas**: Celery para processamento
4. **Logs**: Sistema de logging avançado
5. **Métricas**: Prometheus/Grafana
6. **Alertas**: Notificações automáticas
""".strip()
    
    with open("README_MULTITENANT.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("✅ Documentação criada: README_MULTITENANT.md")

def main():
    """Função principal de configuração."""
    print("🔧 Configurando Sistema Multi-Tenant")
    print("====================================")
    print()
    
    try:
        # Configura API keys
        config = setup_api_keys()
        
        # Cria arquivo .env
        create_env_file()
        
        # Cria script de inicialização
        create_startup_script()
        
        # Cria documentação
        create_readme()
        
        print()
        print("✅ Configuração concluída com sucesso!")
        print()
        print("📋 Próximos passos:")
        print("1. Iniciar a API: ./start_multitenant.sh")
        print("2. Testar o sistema: python3 test_multitenant.py")
        print("3. Acessar docs: http://localhost:8080/docs")
        print()
        print("🔑 API Keys configuradas:")
        for key, info in config["api_keys"].items():
            print(f"  {key} -> {info['name']} (Tenant: {info['tenant_id']})")
        
    except Exception as e:
        print(f"❌ Erro durante a configuração: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())