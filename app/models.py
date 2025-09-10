from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from enum import Enum
from datetime import datetime

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapeRequest(BaseModel):
    """
    Modelo para requisição de scraping.
    
    Attributes:
        url: URL da página a ser processada
        knowledge_base_id: ID da base de conhecimento que identifica o tenant/conta
        callback_url: URL opcional para receber notificação quando o processamento for concluído
        limit: Limite máximo de páginas a serem processadas (padrão: 10)
    """
    url: HttpUrl
    knowledge_base_id: str
    callback_url: Optional[HttpUrl] = None
    limit: Optional[int] = 10
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://crmpiperun.com",
                "knowledge_base_id": "kb_empresa_a_001",
                "callback_url": "https://your-callback-url.com/webhook",
                "limit": 500
            }
        }

class ScrapeResult(BaseModel):
    id: str
    url: HttpUrl
    status: ProcessingStatus
    content: Optional[str] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    limit: Optional[int] = 10
    processed_count: Optional[int] = 0
    queue_size: Optional[int] = 0
    all_content: Optional[List[dict]] = None

class ScrapeResponse(BaseModel):
    """
    Modelo para resposta do scraping.
    
    Attributes:
        id: Identificador único da tarefa
        status: Status atual do processamento (pending, processing, completed, error)
        message: Mensagem descritiva sobre o status
        content: Conteúdo extraído da página (disponível apenas quando completed)
        links: Lista de links encontrados na página (disponível apenas quando completed)
        error: Detalhes do erro, se houver
        limit: Limite máximo de páginas configurado
        processed_count: Número de páginas já processadas
        queue_size: Tamanho atual da fila de processamento
        all_content: Lista com todo o conteúdo extraído de todas as páginas
    """
    id: str
    status: str
    message: str
    content: Optional[str] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None
    limit: Optional[int] = None
    processed_count: Optional[int] = None
    queue_size: Optional[int] = None
    all_content: Optional[List[dict]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
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
        }

class StatusResponse(BaseModel):
    id: str
    status: ProcessingStatus
    message: Optional[str] = None
    content: Optional[str] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None
