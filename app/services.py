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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Extrair o conteúdo
            content = await page.inner_text('body')
            content = ' '.join(content.split())

            # Extrair links
            links = await page.eval_on_selector_all(
                'a[href]',
                'elements => elements.map(element => element.href)'
            )

            # Filtrar apenas links do mesmo domínio
            filtered_links = [
                link for link in links
                if urlparse(link).netloc == base_domain
            ]

            await browser.close()

            return {
                "content": content,
                "links": list(set(filtered_links))
            }

    async def _send_callback(self, callback_url: str, result: ScrapeResult):
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    callback_url,
                    json=result.dict(),
                    headers={"Content-Type": "application/json"}
                )
        except Exception as e:
            logger.error(f"Error sending callback: {str(e)}")
