from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import os
import asyncio

from app.models import ScrapeRequest, StatusResponse
from app.services import ScrapingService

app = FastAPI(title="Web Scraper API",
             description="API para extrair conteúdo e links de páginas web",
             version="1.0.0")

# Definir a chave de API a partir de uma variável de ambiente
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("A variável de ambiente API_KEY não está definida.")

# Criar o esquema de segurança
security = HTTPBearer()
scraping_service = ScrapingService()

# Dependência para verificar a chave de API
def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Chave de API inválida ou ausente.")
    return credentials

@app.post("/scrape", response_model=StatusResponse)
async def scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    task_id = scraping_service.create_task(str(request.url))
    
    background_tasks.add_task(
        scraping_service.process_url,
        task_id,
        str(request.url),
        str(request.callback_url) if request.callback_url else None
    )
    
    return StatusResponse(
        id=task_id,
        status="pending",
        message="Processamento iniciado com sucesso"
    )

@app.get("/status/{task_id}", response_model=StatusResponse)
async def get_status(
    task_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    task = scraping_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    return StatusResponse(
        id=task.id,
        status=task.status,
        message="Erro: " + task.error if task.error else None
    )
