from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Optional
from urllib.parse import urlparse
from app.models import ScrapeRequest, ScrapeResponse
from app.multi_tenant_service import MultiTenantScrapingService
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Tenant Web Scraper API",
    description="""
    API para extração de conteúdo de páginas web com isolamento multi-tenant.
    
    ## Funcionalidades
    
    * ✅ Isolamento completo entre contas/usuários
    * ✅ Rate limiting por tenant
    * ✅ Controle de concorrência
    * ✅ Monitoramento de recursos
    * ✅ Autenticação por API key
    * ✅ Processamento assíncrono
    * ✅ Notificação via webhook
    
    ## Sistema Multi-Tenant
    
    Cada conta possui:
    - Isolamento completo de dados
    - Limites independentes de rate limiting
    - Controle próprio de tarefas concorrentes
    - Estatísticas separadas
    
    ## Rate Limits
    
    - **Requisições por minuto**: 20
    - **Tarefas concorrentes**: 5
    - **Páginas por tarefa**: 500 (máximo)
    
    ## API Keys de Exemplo
    
    - `test_key_123` - Tenant 1, Usuário 1
    - `demo_key_456` - Tenant 1, Usuário 2  
    - `prod_key_789` - Tenant 2, Usuário 3
    """,
    version="2.0.0"
)

# Instância global do serviço multi-tenant
multi_tenant_service = MultiTenantScrapingService()

async def verify_api_key(authorization: str = Header(...)):
    """Verifica API key e retorna contexto do usuário."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    api_key = authorization.split(" ")[1]
    user_context = multi_tenant_service.api_key_manager.verify_and_get_context(api_key)
    
    if not user_context:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key, user_context

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_endpoint(
    request: ScrapeRequest,
    auth_data: tuple = Depends(verify_api_key)
):
    """Inicia processo de scraping com controle multi-tenant baseado em knowledge_base_id."""
    api_key, user_context = auth_data
    
    try:
        # Obtém tenant através do knowledge_base_id
        tenant_id = multi_tenant_service.api_key_manager.get_tenant_by_knowledge_base(request.knowledge_base_id)
        if not tenant_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Knowledge base '{request.knowledge_base_id}' não encontrada"
            )
        
        # Verifica se o usuário tem acesso ao tenant da knowledge base
        user_tenant = user_context["tenant_id"]
        if user_tenant != tenant_id and user_tenant != "admin":
            raise HTTPException(
                status_code=403, 
                detail="Acesso negado à knowledge base especificada"
            )
        
        # Verifica rate limiting
        if not await multi_tenant_service.rate_limiter.check_rate_limit(tenant_id):
            raise HTTPException(
                status_code=429, 
                detail="Rate limit excedido. Tente novamente em alguns minutos."
            )
        
        # Verifica limite de tarefas concorrentes (será verificado no start_scraping)
        # A verificação de limite é feita internamente no método start_scraping
        
        # Valida URL
        if not str(request.url).startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="URL deve começar com http:// ou https://")
        
        # Inicia scraping
        result = await multi_tenant_service.start_scraping(
            tenant_id=tenant_id,
            url=str(request.url),
            limit=request.limit or 10,
            callback_url=str(request.callback_url) if request.callback_url else None,
            knowledge_base_id=request.knowledge_base_id
        )
        
        return ScrapeResponse(
            id=result["id"],
            status=result["status"],
            message=f"Scraping iniciado para knowledge base '{request.knowledge_base_id}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/status/{task_id}", response_model=ScrapeResponse,
    description="Verifica o status de uma tarefa com verificação de acesso",
    responses={
        200: {
            "description": "Status da tarefa",
        },
        401: {
            "description": "Erro de autenticação"
        },
        404: {
            "description": "Tarefa não encontrada ou sem acesso",
            "content": {
                "application/json": {
                    "example": {"detail": "Tarefa não encontrada"}
                }
            }
        }
    }
)
async def get_task_status(task_id: str, auth_data: tuple = Depends(verify_api_key)):
    """
    Verifica o status de uma tarefa com isolamento de acesso.
    
    Apenas o tenant que criou a tarefa pode acessá-la.
    """
    api_key, user_context = auth_data
    
    try:
        task = await multi_tenant_service.get_task_status(api_key, task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
        return task
        
    except HTTPException:
        # Re-raise HTTPExceptions (como 404) sem modificar
        raise
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao buscar status da tarefa: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/stats", 
    description="Obtém estatísticas do tenant atual",
    responses={
        200: {
            "description": "Estatísticas do tenant",
            "content": {
                "application/json": {
                    "example": {
                        "total_requests": 15,
                        "active_tasks": 2,
                        "completed_tasks": 12,
                        "failed_tasks": 1,
                        "rate_limit": {
                            "requests_this_minute": 3,
                            "max_requests_per_minute": 20,
                            "concurrent_tasks": 2,
                            "max_concurrent_tasks": 5
                        }
                    }
                }
            }
        }
    }
)
async def get_tenant_stats(auth_data: tuple = Depends(verify_api_key)):
    """
    Obtém estatísticas de uso do tenant atual.
    
    Inclui:
    - Contadores de tarefas
    - Status de rate limiting
    - Recursos utilizados
    """
    api_key, user_context = auth_data
    
    try:
        stats = multi_tenant_service.get_tenant_stats(api_key)
        
        # Adiciona informações do usuário
        stats["user_info"] = {
            "name": user_context["name"],
            "user_id": user_context["user_id"],
            "account_id": user_context["account_id"],
            "tenant_id": user_context["tenant_id"]
        }
        
        return stats
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/health")
async def health_check():
    """Endpoint de health check."""
    active_tenants = multi_tenant_service.list_active_tenants()
    
    return {
        "status": "healthy",
        "active_tenants": len(active_tenants),
        "tenant_ids": active_tenants
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)