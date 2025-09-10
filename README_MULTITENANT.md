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
curl -X POST "http://localhost:8080/scrape"   -H "Authorization: Bearer test_key_123"   -H "Content-Type: application/json"   -d '{
    "url": "https://example.com",
    "limit": 5
  }'
```

### Verificar Status
```bash
curl -X GET "http://localhost:8080/status/task_123"   -H "Authorization: Bearer test_key_123"
```

### Obter Estatísticas
```bash
curl -X GET "http://localhost:8080/stats"   -H "Authorization: Bearer test_key_123"
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