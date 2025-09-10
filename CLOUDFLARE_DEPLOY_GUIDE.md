# Guia de Deploy no Cloudflare Workers

## Resumo da Viabilidade

**✅ SIM, é possível fazer deploy do serviço FastAPI no Cloudflare Workers!**

O Cloudflare Workers oferece suporte nativo ao Python e FastAPI desde 2024, utilizando Pyodide (uma implementação do CPython compilada para WebAssembly) integrada diretamente no runtime do Workers.

## Características do Cloudflare Workers para Python

### ✅ Suporte Completo
- **FastAPI nativo**: Suporte direto ao FastAPI sem modificações
- **ASGI Server integrado**: O Workers runtime fornece um servidor ASGI automaticamente
- **Bindings**: Acesso a todos os serviços Cloudflare (R2, KV, D1, Durable Objects, etc.)
- **Bibliotecas Python**: Suporte à maioria da Standard Library e pacotes populares
- **Ambiente Variables**: Suporte completo a variáveis de ambiente e secrets

### 🔄 Adaptações Necessárias

#### 1. Estrutura do Worker
O FastAPI precisa ser encapsulado em uma classe `WorkerEntrypoint`:

```python
from workers import WorkerEntrypoint
from fastapi import FastAPI

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        import asgi
        return await asgi.fetch(app, request, self.env)

app = FastAPI()

# Seus endpoints FastAPI aqui
@app.get("/")
async def root():
    return {"message": "Hello, World!"}
```

#### 2. Configuração do Projeto
Arquivo `wrangler.toml`:

```toml
name = "fastapi-scraper-multitenant"
main = "src/main.py"
compatibility_date = "2024-03-18"
compatibility_flags = ["python_workers"]

[vars]
ENVIRONMENT = "production"

# Secrets (configurar via wrangler secret put)
# API_KEYS_CONFIG
# DATABASE_URL (se usar D1 ou external DB)
```

#### 3. Gerenciamento de Dependências
Arquivo `pyproject.toml`:

```toml
[project]
name = "fastapi-scraper-multitenant"
version = "0.1.0"
description = "Multi-tenant FastAPI scraper service"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "httpx",  # Para requisições HTTP
    "pydantic"
]

[dependency-groups]
dev = ["workers-py"]
```

## Limitações e Considerações

### ⚠️ Limitações Importantes

1. **Tempo de Execução**: Workers têm limite de 30 segundos por requisição (pode ser estendido com Durable Objects)
2. **Memória**: Limite de 128MB por Worker
3. **Armazenamento**: Não há filesystem persistente (usar KV, R2 ou D1)
4. **Bibliotecas**: Nem todas as bibliotecas Python são suportadas (especialmente as que dependem de C extensions não portadas)
5. **Concorrência**: Modelo de isolates (não threads tradicionais)

### 🔧 Adaptações Necessárias no Código Atual

#### 1. Substituir Armazenamento em Memória
**Problema**: O serviço atual usa dicionários em memória para armazenar tarefas.
**Solução**: Migrar para Cloudflare KV ou Durable Objects.

```python
# Antes (em memória)
self._tasks = {}

# Depois (Cloudflare KV)
async def store_task(self, task_id: str, task_data: dict):
    await self.env.TASKS_KV.put(f"task:{task_id}", json.dumps(task_data))

async def get_task(self, task_id: str):
    data = await self.env.TASKS_KV.get(f"task:{task_id}")
    return json.loads(data) if data else None
```

#### 2. Substituir Bibliotecas de Scraping
**Problema**: Bibliotecas como `requests`, `selenium` não são suportadas.
**Solução**: Usar `httpx` (suportado) ou a API `fetch` do JavaScript.

```python
# Usar httpx em vez de requests
import httpx

async def scrape_url(self, url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

#### 3. Configuração Multi-tenant com KV
```python
class CloudflareMultiTenantService:
    def __init__(self, env):
        self.env = env
        self.kv = env.TASKS_KV
        self.api_keys_kv = env.API_KEYS_KV
    
    async def get_tenant_from_api_key(self, api_key: str):
        tenant_data = await self.api_keys_kv.get(f"key:{api_key}")
        return json.loads(tenant_data) if tenant_data else None
    
    async def store_task(self, tenant_id: str, task_id: str, task_data: dict):
        key = f"tenant:{tenant_id}:task:{task_id}"
        await self.kv.put(key, json.dumps(task_data))
    
    async def get_task(self, tenant_id: str, task_id: str):
        key = f"tenant:{tenant_id}:task:{task_id}"
        data = await self.kv.get(key)
        return json.loads(data) if data else None
```

## 🚀 Processo de Deploy

### 1. Preparação

```bash
# Instalar Wrangler CLI
npm install -g wrangler

# Fazer login no Cloudflare
wrangler login

# Verificar se está logado
wrangler whoami

# Instalar pywrangler para Python Workers (se necessário)
npm install -g pywrangler
```

### 2. Configuração dos KV Stores

```bash
# Usar o script automatizado para criar namespaces e configurar chaves
python3 setup_cloudflare_kv.py

# OU fazer manualmente:
# Criar namespaces KV
wrangler kv:namespace create "TASKS_KV" --name fastapi-multitenant-scraper
wrangler kv:namespace create "API_KEYS_KV" --name fastapi-multitenant-scraper

# Atualizar wrangler.toml com os IDs retornados
# Exemplo:
# [[kv_namespaces]]
# binding = "TASKS_KV"
# id = "seu-tasks-kv-id-aqui"
```

### 3. Deploy

```bash
# Verificar configuração antes do deploy
wrangler deploy --dry-run

# Deploy para produção
wrangler deploy

# OU usando pywrangler (se disponível)
pywrangler deploy

# Deploy para staging
wrangler deploy --env staging

# Verificar se o deploy foi bem-sucedido
wrangler tail --format pretty
```

## Vantagens do Cloudflare Workers

### 🚀 Performance
- **Edge Computing**: Deploy global automático em 300+ localizações
- **Cold Start**: ~1ms (muito mais rápido que containers)
- **Escalabilidade**: Automática e ilimitada

### 💰 Custo
- **Free Tier**: 100.000 requisições/dia gratuitas
- **Paid**: $5/mês para 10 milhões de requisições
- **Sem custos de infraestrutura**: Não precisa gerenciar servidores

### 🔒 Segurança
- **Isolamento**: Cada requisição roda em um isolate separado
- **DDoS Protection**: Proteção automática
- **SSL/TLS**: Certificados automáticos

## 📁 Estrutura de Arquivos para Cloudflare Workers

```
fastAPI-scraper/
├── cloudflare_worker_main.py    # Entry point adaptado para Workers
├── wrangler.toml                # Configuração do Cloudflare Workers
├── requirements-cloudflare.txt  # Dependências compatíveis com Pyodide
├── setup_cloudflare_kv.py      # Script para configurar KV stores
├── CLOUDFLARE_DEPLOY_GUIDE.md  # Este guia de deploy
├── test_comprehensive_isolation.py # Testes de isolamento
└── debug_isolation.py          # Script de debug (para referência)
```

### 4. Configuração das API Keys

```bash
# Executar script de configuração (recomendado)
python3 setup_cloudflare_kv.py

# O script oferece as seguintes opções:
# 1. Criar namespaces KV
# 2. Configurar API keys
# 3. Verificar configuração
# 4. Fazer tudo (setup completo)

# OU configurar manualmente via wrangler
wrangler kv:key put "key:test_key_123" '{"tenant_id":"tenant_1","user_id":"user1","knowledge_bases":["kb_user1_001"],"active":true}' --binding API_KEYS_KV --name fastapi-multitenant-scraper
```

### 5. Teste e Verificação

```bash
# Testar o endpoint de health check
curl https://seu-worker.seu-subdominio.workers.dev/health

# Testar com uma API key válida
curl -X POST "https://seu-worker.seu-subdominio.workers.dev/scrape" \
  -H "Authorization: Bearer test_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "knowledge_base_id": "kb_user1_001",
    "limit": 5
  }'

# Verificar logs em tempo real
wrangler tail --format pretty

# Executar testes de isolamento (localmente)
python3 test_comprehensive_isolation.py
```

## 🔧 Comandos Úteis

### Desenvolvimento
```bash
# Desenvolvimento local
wrangler dev

# Desenvolvimento com logs detalhados
wrangler dev --local --log-level debug

# Testar localmente antes do deploy
wrangler dev --compatibility-date 2024-01-15
```

### Monitoramento
```bash
# Ver logs em tempo real
wrangler tail

# Ver logs com filtro
wrangler tail --format json | jq '.message'

# Ver métricas
wrangler analytics
```

### Gerenciamento KV
```bash
# Listar todas as chaves
wrangler kv:key list --binding API_KEYS_KV

# Ver valor de uma chave específica
wrangler kv:key get "key:test_key_123" --binding API_KEYS_KV

# Deletar uma chave
wrangler kv:key delete "key:old_key" --binding API_KEYS_KV

# Backup das chaves (exportar)
wrangler kv:bulk download --binding API_KEYS_KV backup.json
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **Erro de autenticação**
   ```bash
   # Verificar se está logado
   wrangler whoami
   
   # Re-fazer login se necessário
   wrangler logout
   wrangler login
   ```

2. **KV namespace não encontrado**
   - Verificar se os IDs no `wrangler.toml` estão corretos
   - Executar `wrangler kv:namespace list` para ver namespaces disponíveis

3. **Dependências não compatíveis**
   - Usar apenas as dependências listadas em `requirements-cloudflare.txt`
   - Verificar compatibilidade com Pyodide

4. **Timeout ou erro 500**
   - Verificar logs com `wrangler tail`
   - Reduzir timeout de requests HTTP
   - Verificar se as variáveis de ambiente estão configuradas

### Logs de Debug
```bash
# Ativar logs detalhados no Worker
wrangler deploy --compatibility-flags python_workers --log-level debug

# Ver logs específicos de erro
wrangler tail --format json | grep -i error
```

## 🎯 Próximos Passos

### Melhorias Recomendadas

1. **Otimização de Performance**
   - Implementar cache inteligente com TTL
   - Otimizar queries KV com batching
   - Usar Durable Objects para estado compartilhado
   - Implementar compressão de dados

2. **Monitoramento e Observabilidade**
   - Configurar alertas no Cloudflare Dashboard
   - Implementar métricas customizadas
   - Dashboard de performance em tempo real
   - Logs estruturados com correlação de requests

3. **Segurança Aprimorada**
   - Rate limiting por tenant e IP
   - Validação de domínios permitidos
   - Audit logs para compliance
   - Rotação automática de API keys

4. **Funcionalidades Avançadas**
   - Webhooks para notificações
   - Processamento em background com Queues
   - Suporte a múltiplos formatos de saída
   - API de analytics para tenants

### Considerações de Produção

- **Backup**: Implementar backup automático dos KV stores
- **Disaster Recovery**: Plano de recuperação de desastres
- **Compliance**: Adequação a LGPD/GDPR se necessário
- **Documentação**: API docs automática com OpenAPI

## 📞 Suporte

Para dúvidas sobre o deploy no Cloudflare Workers:
- [Documentação oficial do Cloudflare Workers](https://developers.cloudflare.com/workers/)
- [Comunidade Discord do Cloudflare](https://discord.gg/cloudflaredev)
- [GitHub Issues do projeto](https://github.com/seu-usuario/fastapi-scraper)

---

**✅ Deploy concluído com sucesso!** 

Seu serviço FastAPI multi-tenant agora está rodando no Cloudflare Workers com:
- ✅ Isolamento completo entre tenants
- ✅ Armazenamento distribuído via KV
- ✅ Autenticação por API key
- ✅ Monitoramento e logs
- ✅ Escalabilidade automática
- ✅ SSL/TLS automático
- ✅ CDN global integrado

## Conclusão

**O deploy no Cloudflare Workers é altamente viável e recomendado** para este tipo de serviço, oferecendo:

- ✅ Suporte nativo ao FastAPI
- ✅ Escalabilidade automática global
- ✅ Custos muito baixos
- ✅ Performance superior
- ✅ Manutenção mínima

As principais adaptações necessárias são:
1. Migrar armazenamento em memória para KV
2. Usar bibliotecas compatíveis (httpx em vez de requests)
3. Adaptar estrutura para WorkerEntrypoint

O investimento na migração será compensado pelos benefícios de performance, escalabilidade e custo do Cloudflare Workers.