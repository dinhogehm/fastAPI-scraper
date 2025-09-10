# Análise de Concorrência e Isolamento Multi-Usuário

## Situação Atual

A aplicação atual possui algumas limitações importantes para cenários multi-usuário:

### Problemas Identificados

1. **Instância Única do ScrapingService**: 
   - Todos os usuários compartilham a mesma instância
   - Dicionários globais (`_tasks`, `_processing_queues`, etc.) são compartilhados
   - Não há isolamento entre diferentes contas/usuários

2. **Autenticação Simples**:
   - Uma única API key para todos os usuários
   - Não há identificação de usuário ou conta
   - Impossível rastrear qual usuário iniciou qual tarefa

3. **Armazenamento em Memória**:
   - Dados perdidos se a aplicação reiniciar
   - Não há persistência das tarefas
   - Limitado pela memória RAM disponível

## Riscos de Concorrência

### Cenários Problemáticos

1. **Conflito de Task IDs**: Embora use UUID, não há namespace por usuário
2. **Vazamento de Dados**: Um usuário pode acessar tarefas de outro usuário se souber o ID
3. **Sobrecarga de Recursos**: Muitos scrapes simultâneos podem sobrecarregar o sistema
4. **Race Conditions**: Acesso simultâneo aos dicionários compartilhados

## Soluções Propostas

### 1. Implementar Sistema Multi-Tenant

```python
# Estrutura proposta para isolamento por usuário/conta
class MultiTenantScrapingService:
    def __init__(self):
        self._tenant_services: Dict[str, ScrapingService] = {}
        self._tenant_locks: Dict[str, asyncio.Lock] = {}
    
    def get_service_for_tenant(self, tenant_id: str) -> ScrapingService:
        if tenant_id not in self._tenant_services:
            self._tenant_services[tenant_id] = ScrapingService()
            self._tenant_locks[tenant_id] = asyncio.Lock()
        return self._tenant_services[tenant_id]
```

### 2. Melhorar Autenticação

```python
# Sistema de API keys por usuário/conta
class APIKeyManager:
    def __init__(self):
        self.api_keys = {
            "user_123_key": {"user_id": "123", "account_id": "acc_1"},
            "user_456_key": {"user_id": "456", "account_id": "acc_1"},
            "user_789_key": {"user_id": "789", "account_id": "acc_2"}
        }
    
    def verify_and_get_context(self, api_key: str) -> dict:
        return self.api_keys.get(api_key)
```

### 3. Implementar Rate Limiting

```python
# Controle de taxa por usuário/conta
class RateLimiter:
    def __init__(self):
        self.limits = {
            "requests_per_minute": 10,
            "concurrent_tasks": 5,
            "max_pages_per_task": 1000
        }
```

### 4. Adicionar Persistência

```python
# Usar banco de dados para persistir tarefas
class TaskRepository:
    async def save_task(self, task: ScrapeResult, tenant_id: str):
        # Salvar no banco com tenant_id
        pass
    
    async def get_task(self, task_id: str, tenant_id: str) -> Optional[ScrapeResult]:
        # Buscar apenas tarefas do tenant específico
        pass
```

### 5. Implementar Queue System

```python
# Sistema de filas distribuído (Redis/RabbitMQ)
class DistributedQueue:
    def __init__(self):
        self.redis_client = redis.Redis()
    
    async def enqueue_task(self, task_data: dict, tenant_id: str):
        queue_name = f"scraping_queue_{tenant_id}"
        await self.redis_client.lpush(queue_name, json.dumps(task_data))
```

## Implementação Recomendada

### Fase 1: Isolamento Básico
1. Implementar sistema multi-tenant em memória
2. Adicionar identificação de usuário via API key
3. Implementar rate limiting básico

### Fase 2: Persistência
1. Adicionar banco de dados (PostgreSQL/MySQL)
2. Migrar armazenamento de tarefas para BD
3. Implementar cleanup automático de tarefas antigas

### Fase 3: Escalabilidade
1. Implementar sistema de filas distribuído
2. Adicionar workers separados para processamento
3. Implementar monitoramento e métricas

## Benefícios Esperados

1. **Isolamento Completo**: Cada conta/usuário tem seus próprios dados
2. **Escalabilidade**: Sistema pode crescer horizontalmente
3. **Confiabilidade**: Dados persistidos e recuperáveis
4. **Segurança**: Usuários não podem acessar dados de outros
5. **Monitoramento**: Rastreabilidade por usuário/conta

## Próximos Passos

1. Definir estrutura de usuários/contas
2. Implementar sistema de API keys por usuário
3. Refatorar ScrapingService para suportar multi-tenancy
4. Adicionar testes de concorrência
5. Implementar monitoramento de recursos