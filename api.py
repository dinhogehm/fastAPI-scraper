from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Optional
from urllib.parse import urlparse
from app.models import ScrapeRequest, ScrapeResponse
from app.services import ScrapingService
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Web Scraper API",
    description="""
    API para extração de conteúdo de páginas web.
    
    ## Funcionalidades
    
    * Extração de conteúdo textual relevante
    * Extração de links internos
    * Processamento assíncrono
    * Notificação via webhook
    * Preservação de acentos e caracteres especiais
    * Detecção automática de idioma
    
    ## Exemplos de Uso
    
    ### Iniciando um Scraping
    
    ```bash
    curl -X POST "http://localhost:8080/scrape" \\
         -H "Authorization: Bearer your_api_key" \\
         -H "Content-Type: application/json" \\
         -d '{
           "url": "https://crmpiperun.com",
           "callback_url": "https://your-callback-url.com/webhook"
         }'
    ```
    
    Resposta:
    ```json
    {
        "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
        "status": "pending",
        "message": "Processamento iniciado com sucesso",
        "content": null,
        "links": null,
        "error": null
    }
    ```
    
    ### Verificando Status do Scraping
    
    ```bash
    curl "http://localhost:8080/status/53473fca-bd52-4ce9-bc5f-c20a0b7436ef" \\
         -H "Authorization: Bearer your_api_key"
    ```
    
    Resposta (Em Processamento):
    ```json
    {
        "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
        "status": "processing",
        "message": "Processamento em andamento",
        "content": null,
        "links": null,
        "error": null
    }
    ```
    
    Resposta (Concluído):
    ```json
    {
        "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
        "status": "completed",
        "message": "Processamento concluído com sucesso",
        "content": "O CRM que organiza para vender melhor\\nDe Vendedor para Vendedor: O CRM que entende suas necessidades reais.\\nA piperun é completa e fácil de usar...",
        "links": [
            "https://crmpiperun.com/",
            "https://crmpiperun.com/legal/politica-de-privacidade/",
            "https://crmpiperun.com/trial/"
        ],
        "error": null
    }
    ```
    
    Resposta (Erro):
    ```json
    {
        "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
        "status": "error",
        "message": "Erro ao processar a URL",
        "content": null,
        "links": null,
        "error": "Detalhes do erro encontrado"
    }
    ```
    """,
    version="1.0.0"
)

API_KEY = os.getenv("API_KEY", "test_key_123")
scraping_service = ScrapingService()

async def verify_api_key(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    api_key = authorization.split(" ")[1]
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@app.post("/scrape", response_model=ScrapeResponse, 
    description="Inicia o processo de extração de conteúdo de uma URL",
    responses={
        200: {
            "description": "Scraping iniciado com sucesso",
            "content": {
                "application/json": {
                    "example": {
                        "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
                        "status": "pending",
                        "message": "Processamento iniciado com sucesso (limite: 10 páginas)",
                        "content": None,
                        "links": None,
                        "error": None
                    }
                }
            }
        },
        401: {
            "description": "Erro de autenticação",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid API key"}
                }
            }
        }
    }
)
async def scrape_url(request: ScrapeRequest, api_key: str = Depends(verify_api_key)):
    """
    Inicia o processo de scraping de uma URL com sistema de fila.
    
    - **url**: URL do site para fazer scraping
    - **callback_url**: URL opcional para receber notificação quando o scraping for concluído
    - **limit**: Limite máximo de páginas a processar (padrão: 10)
    
    O sistema busca automaticamente por arquivos centralizadores (llm.txt, sitemap.xml)
    e processa URLs em fila até atingir o limite especificado.
    
    Retorna um task_id que pode ser usado para verificar o status do scraping.
    """
    try:
        # Valida a URL
        parsed_url = urlparse(str(request.url))
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="URL inválida")
        
        # Inicia o scraping com limite
        task_id = await scraping_service.start_scraping(
            str(request.url), 
            str(request.callback_url) if request.callback_url else None,
            request.limit
        )
        
        return ScrapeResponse(
            task_id=task_id,
            status="pending",
            message=f"Scraping iniciado para {request.url} (limite: {request.limit} páginas)",
            url=str(request.url),
            limit=request.limit,
            processed_count=0,
            queue_size=0
        )
        
    except Exception as e:
        logger.error(f"Erro ao iniciar scraping: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/status/{task_id}", response_model=ScrapeResponse,
    description="Verifica o status de uma tarefa de scraping",
    responses={
        200: {
            "description": "Status da tarefa",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {
                            "value": {
                                "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
                                "status": "pending",
                                "message": "Processamento iniciado com sucesso",
                                "content": None,
                                "links": None,
                                "error": None
                            }
                        },
                        "processing": {
                            "value": {
                                "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
                                "status": "processing",
                                "message": "Processamento em andamento",
                                "content": None,
                                "links": None,
                                "error": None
                            }
                        },
                        "completed": {
                            "value": {
                                "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
                                "status": "completed",
                                "message": "Processamento concluído com sucesso",
                                "content": "O CRM que organiza para vender melhor\nDe Vendedor para Vendedor: O CRM que entende suas necessidades reais.\nA piperun é completa e fácil de usar...",
                                "links": [
                                    "https://crmpiperun.com/",
                                    "https://crmpiperun.com/legal/politica-de-privacidade/",
                                    "https://crmpiperun.com/trial/"
                                ],
                                "error": None
                            }
                        },
                        "error": {
                            "value": {
                                "id": "53473fca-bd52-4ce9-bc5f-c20a0b7436ef",
                                "status": "error",
                                "message": "Erro ao processar a URL",
                                "content": None,
                                "links": None,
                                "error": "Detalhes do erro encontrado"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Erro de autenticação",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid API key"}
                }
            }
        },
        404: {
            "description": "Tarefa não encontrada",
            "content": {
                "application/json": {
                    "example": {"detail": "Task not found"}
                }
            }
        }
    }
)
async def get_task_status(task_id: str, api_key: str = Depends(verify_api_key)):
    task = scraping_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
