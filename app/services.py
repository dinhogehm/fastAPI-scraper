from urllib.parse import urlparse, urljoin
import asyncio
import aiohttp
from datetime import datetime
import uuid
from typing import Dict, Optional
from .models import ScrapeResult, ProcessingStatus
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingService:
    def __init__(self):
        self._tasks: Dict[str, ScrapeResult] = {}

    def create_task(self, url: str) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = ScrapeResult(
            id=task_id,
            url=url,
            status=ProcessingStatus.PENDING,
            created_at=datetime.now()
        )
        return task_id

    def get_task_status(self, task_id: str) -> Optional[ScrapeResult]:
        return self._tasks.get(task_id)

    async def process_url(self, task_id: str, url: str, callback_url: Optional[str] = None):
        try:
            self._tasks[task_id].status = ProcessingStatus.PROCESSING
            result = await self._scrape_url(url)
            
            self._tasks[task_id].status = ProcessingStatus.COMPLETED
            self._tasks[task_id].content = result["content"]
            self._tasks[task_id].links = result["links"]
            self._tasks[task_id].completed_at = datetime.now()

            if callback_url:
                await self._send_callback(callback_url, self._tasks[task_id])

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {str(e)}")
            self._tasks[task_id].status = ProcessingStatus.FAILED
            self._tasks[task_id].error = str(e)
            self._tasks[task_id].completed_at = datetime.now()

            if callback_url:
                await self._send_callback(callback_url, self._tasks[task_id])

    async def _scrape_url(self, url: str) -> dict:
        base_domain = urlparse(url).netloc
        logger.info(f"Iniciando scraping de {url} (domínio base: {base_domain})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                logger.info("Página carregada com sucesso")

                # Extrair o conteúdo
                content = await page.inner_text('body')
                content = ' '.join(content.split())
                logger.info(f"Conteúdo extraído: {len(content)} caracteres")

                # Extrair links
                links = await page.evaluate('''() => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors)
                        .map(a => a.href)
                        .filter(href => href && href.startsWith('http'));
                }''')

                # Filtrar apenas links do mesmo domínio
                filtered_links = []
                for link in links:
                    try:
                        link_domain = urlparse(link).netloc.replace('www.', '')
                        base_domain_clean = base_domain.replace('www.', '')
                        if link_domain == base_domain_clean:
                            filtered_links.append(link)
                    except Exception as e:
                        logger.error(f"Erro ao processar link {link}: {str(e)}")

                logger.info(f"Links encontrados: {len(links)}, Filtrados: {len(filtered_links)}")
                if filtered_links:
                    logger.info(f"Exemplos de links filtrados: {filtered_links[:3]}")

                await browser.close()
                return {
                    "content": content,
                    "links": list(set(filtered_links))
                }
            except Exception as e:
                logger.error(f"Erro durante o scraping: {str(e)}")
                await browser.close()
                raise

    async def _send_callback(self, callback_url: str, result: ScrapeResult):
        try:
            callback_data = {
                "id": result.id,
                "status": result.status,
                "content": result.content,
                "links": result.links,
                "error": result.error,
                "created_at": result.created_at.isoformat(),
                "completed_at": result.completed_at.isoformat() if result.completed_at else None
            }
            
            async with aiohttp.ClientSession() as session:
                response = await session.post(
                    callback_url,
                    json=callback_data,
                    headers={"Content-Type": "application/json"}
                )
                logger.info(f"Callback enviado para {callback_url}. Status: {response.status}")
                if response.status not in (200, 201, 202):
                    logger.error(f"Erro no callback. Status: {response.status}, Response: {await response.text()}")
        except Exception as e:
            logger.error(f"Erro ao enviar callback: {str(e)}")
