from typing import Optional, Dict, Any
import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from app.services import ScrapingService
from app.models import ScrapeResponse

logger = logging.getLogger(__name__)

class RateLimiter:
    """Controla a taxa de requisições por tenant."""
    
    def __init__(self):
        self.request_counts: Dict[str, list] = defaultdict(list)
        self.concurrent_tasks: Dict[str, int] = defaultdict(int)
        
        # Limites configuráveis
        self.max_requests_per_minute = 20
        self.max_concurrent_tasks = 5
        self.max_pages_per_task = 500
    
    async def check_rate_limit(self, tenant_id: str) -> bool:
        """Verifica se o tenant pode fazer uma nova requisição."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Remove requisições antigas
        self.request_counts[tenant_id] = [
            req_time for req_time in self.request_counts[tenant_id]
            if req_time > minute_ago
        ]
        
        # Verifica limite de requisições por minuto
        if len(self.request_counts[tenant_id]) >= self.max_requests_per_minute:
            return False
        
        # Verifica limite de tarefas concorrentes
        if self.concurrent_tasks[tenant_id] >= self.max_concurrent_tasks:
            return False
        
        return True
    
    async def record_request(self, tenant_id: str):
        """Registra uma nova requisição."""
        self.request_counts[tenant_id].append(datetime.now())
        self.concurrent_tasks[tenant_id] += 1
    
    async def release_task(self, tenant_id: str):
        """Libera uma tarefa concorrente."""
        if self.concurrent_tasks[tenant_id] > 0:
            self.concurrent_tasks[tenant_id] -= 1
    
    def validate_limit(self, limit: int) -> int:
        """Valida e ajusta o limite de páginas por tarefa."""
        return min(limit, self.max_pages_per_task)

class APIKeyManager:
    """Gerencia API keys e contexto de usuários/contas."""
    
    def __init__(self):
        self._create_default_config()
    
    def _create_default_config(self):
        """Cria configuração padrão."""
        self.api_keys = {
            "test_key_123": {
                "tenant_id": "tenant_1",
                "user_id": "user_1",
                "name": "Test User 1",
                "account_id": "acc_1",
                "active": True
            },
            "demo_key_456": {
                "tenant_id": "tenant_1",
                "user_id": "user_2", 
                "name": "Test User 2",
                "account_id": "acc_1",
                "active": True
            },
            "prod_key_789": {
                "tenant_id": "tenant_2",
                "user_id": "user_3",
                "name": "Prod User",
                "account_id": "acc_2",
                "active": True
            }
        }
        
        self.tenants = {
            "tenant_1": {
                "name": "Tenant 1",
                "rate_limits": {
                    "requests_per_minute": 20,
                    "max_concurrent_tasks": 5
                }
            },
            "tenant_2": {
                "name": "Tenant 2",
                "rate_limits": {
                    "requests_per_minute": 15,
                    "max_concurrent_tasks": 3
                }
            }
        }
        
        # Mapeamento de knowledge_base_id para tenant_id
        self.knowledge_base_mapping = {
            "kb_empresa_a_001": "tenant_1",
            "kb_empresa_a_002": "tenant_1", 
             "kb_empresa_b_001": "tenant_2",
             "kb_admin_001": "admin",
             "kb_user1_001": "tenant_1",
             "kb_user2_001": "tenant_1",
             "kb_user3_001": "tenant_2",
             "kb_user1_rate_test": "tenant_1",
             "kb_user3_concurrent_test": "tenant_2"
        }
    
    def verify_and_get_context(self, api_key: str) -> Optional[dict]:
        """Verifica API key e retorna contexto do usuário."""
        return self.api_keys.get(api_key)
    
    def get_tenant_id(self, api_key: str) -> Optional[str]:
        """Extrai tenant_id da API key."""
        context = self.verify_and_get_context(api_key)
        return context.get("tenant_id") if context else None
    
    def get_tenant_by_knowledge_base(self, knowledge_base_id: str) -> Optional[str]:
        """Obtém tenant_id através do knowledge_base_id."""
        return self.knowledge_base_mapping.get(knowledge_base_id)
    
    def add_knowledge_base_mapping(self, knowledge_base_id: str, tenant_id: str):
        """Adiciona mapeamento de knowledge base para tenant."""
        self.knowledge_base_mapping[knowledge_base_id] = tenant_id

class MultiTenantScrapingService:
    """Serviço de scraping com isolamento multi-tenant."""
    
    def __init__(self):
        self._tenant_services: Dict[str, ScrapingService] = {}
        self._tenant_locks: Dict[str, asyncio.Lock] = {}
        self.rate_limiter = RateLimiter()
        self.api_key_manager = APIKeyManager()
        
        # Estatísticas por tenant
        self._tenant_stats: Dict[str, dict] = defaultdict(lambda: {
            "total_requests": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0
        })
    
    def _get_service_for_tenant(self, tenant_id: str) -> ScrapingService:
        """Obtém ou cria um serviço de scraping isolado para o tenant."""
        if tenant_id not in self._tenant_services:
            self._tenant_services[tenant_id] = ScrapingService()
            self._tenant_locks[tenant_id] = asyncio.Lock()
            logger.info(f"Criado novo serviço para tenant: {tenant_id}")
        
        return self._tenant_services[tenant_id]
    
    async def start_scraping(
        self, 
        tenant_id: str, 
        url: str, 
        limit: int = 10, 
        callback_url: Optional[str] = None,
        knowledge_base_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Inicia scraping com isolamento por tenant."""
        
        # Verifica rate limiting
        if not await self.rate_limiter.check_rate_limit(tenant_id):
            raise ValueError("Rate limit excedido. Tente novamente em alguns minutos.")
        
        # Verifica limite de tarefas concorrentes
        if self._tenant_stats[tenant_id]["active_tasks"] >= 5:  # Limite padrão de 5 tarefas
            raise ValueError("Limite de tarefas concorrentes atingido")
        
        # Valida e ajusta limite
        validated_limit = self.rate_limiter.validate_limit(limit)
        if validated_limit != limit:
            logger.warning(f"Limite ajustado de {limit} para {validated_limit} para tenant {tenant_id}")
        
        # Obtém serviço isolado para o tenant
        service = self._get_service_for_tenant(tenant_id)
        
        # Registra a requisição
        await self.rate_limiter.record_request(tenant_id)
        self._tenant_stats[tenant_id]["total_requests"] += 1
        self._tenant_stats[tenant_id]["active_tasks"] += 1
        
        try:
            # Inicia o scraping no serviço isolado
            task_id = await service.start_scraping(url, callback_url, validated_limit)
            
            # Se knowledge_base_id foi fornecido, adiciona mapeamento
            if knowledge_base_id:
                self.api_key_manager.add_knowledge_base_mapping(knowledge_base_id, tenant_id)
            
            # Adiciona monitoramento para liberar recursos quando terminar
            asyncio.create_task(self._monitor_task_completion(tenant_id, task_id))
            
            logger.info(f"Scraping iniciado para tenant {tenant_id}, task {task_id}, knowledge_base: {knowledge_base_id}")
            
            return {
                "id": task_id,
                "status": "pending",
                "tenant_id": tenant_id,
                "knowledge_base_id": knowledge_base_id
            }
            
        except Exception as e:
            # Libera recursos em caso de erro
            await self.rate_limiter.release_task(tenant_id)
            self._tenant_stats[tenant_id]["active_tasks"] -= 1
            raise e
            self._tenant_stats[tenant_id]["failed_tasks"] += 1
            raise e
    
    async def get_task_status(self, api_key: str, task_id: str) -> Optional[ScrapeResponse]:
        """Obtém status de uma tarefa com verificação de acesso."""
        
        try:
            # Verifica contexto do usuário
            user_context = self.api_key_manager.verify_and_get_context(api_key)
            if not user_context:
                raise ValueError("API key inválida")
            
            tenant_id = user_context["tenant_id"]
            logger.info(f"Buscando tarefa {task_id} para tenant {tenant_id}")
            
            # Obtém serviço do tenant
            service = self._get_service_for_tenant(tenant_id)
            
            # Busca tarefa apenas no contexto do tenant
            task = service.get_task(task_id)
            
            if task is None:
                logger.info(f"Tarefa {task_id} não encontrada no tenant {tenant_id}")
            else:
                logger.info(f"Tarefa {task_id} encontrada no tenant {tenant_id} com status {task.status}")
            
            return task
            
        except Exception as e:
            logger.error(f"Erro detalhado ao buscar tarefa {task_id}: {type(e).__name__}: {str(e)}")
            raise e
    
    async def _monitor_task_completion(self, tenant_id: str, task_id: str):
        """Monitora conclusão de tarefa para liberar recursos."""
        service = self._get_service_for_tenant(tenant_id)
        
        # Polling para verificar conclusão (em produção, usar eventos)
        while True:
            await asyncio.sleep(5)  # Verifica a cada 5 segundos
            
            task = service.get_task(task_id)
            if not task:
                break
            
            if task.status in ["completed", "failed"]:
                # Libera recursos
                await self.rate_limiter.release_task(tenant_id)
                self._tenant_stats[tenant_id]["active_tasks"] -= 1
                
                if task.status == "completed":
                    self._tenant_stats[tenant_id]["completed_tasks"] += 1
                else:
                    self._tenant_stats[tenant_id]["failed_tasks"] += 1
                
                logger.info(f"Tarefa {task_id} finalizada para tenant {tenant_id} com status {task.status}")
                break
    
    def get_tenant_stats(self, api_key: str) -> dict:
        """Obtém estatísticas do tenant."""
        user_context = self.api_key_manager.verify_and_get_context(api_key)
        if not user_context:
            raise ValueError("API key inválida")
        
        tenant_id = user_context["tenant_id"]
        stats = self._tenant_stats[tenant_id].copy()
        
        # Adiciona informações de rate limiting
        stats["rate_limit"] = {
            "requests_this_minute": len(self.rate_limiter.request_counts[tenant_id]),
            "max_requests_per_minute": self.rate_limiter.max_requests_per_minute,
            "concurrent_tasks": self.rate_limiter.concurrent_tasks[tenant_id],
            "max_concurrent_tasks": self.rate_limiter.max_concurrent_tasks
        }
        
        return stats
    
    def list_active_tenants(self) -> list:
        """Lista tenants ativos (para monitoramento)."""
        return list(self._tenant_services.keys())