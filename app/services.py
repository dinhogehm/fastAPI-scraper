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
from langdetect import detect
import unicodedata

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

    async def _clean_text(self, text: str, language: str = 'pt') -> str:
        """Limpa e formata o texto extraído preservando acentos."""
        # Remove espaços extras e quebras de linha
        text = ' '.join(text.split())
        
        if language in ['pt', 'es']:
            # Para idiomas latinos, preserva acentos e caracteres especiais
            # Remove apenas caracteres realmente indesejados
            text = ''.join(c for c in unicodedata.normalize('NFKC', text)
                         if not unicodedata.combining(c) and c != '\u200b')
        else:
            # Para outros idiomas, remove caracteres não ASCII
            text = text.encode('ascii', 'ignore').decode('ascii')
        
        # Remove múltiplos espaços
        text = ' '.join(filter(None, text.split(' ')))
        return text.strip()

    async def _extract_content(self, page) -> str:
        """Extrai o conteúdo relevante da página."""
        try:
            # Remove elementos que geralmente contêm conteúdo irrelevante
            await page.evaluate('''() => {
                const elementsToRemove = document.querySelectorAll('header, footer, nav, style, script, iframe, img, svg, .cookie-banner, .popup, .modal, [role="banner"], [role="navigation"], [class*="menu"], [class*="icon"], [class*="social"], [class*="cookie"], [class*="banner"], [class*="popup"], [class*="modal"]');
                elementsToRemove.forEach(el => el.remove());
            }''')

            # Extrai todo o texto primeiro para detectar o idioma
            full_text = await page.evaluate('() => document.body.innerText')
            language = self._detect_language(full_text)
            logger.info(f"Idioma detectado: {language}")

            # Extrai títulos principais (apenas h1 e h2)
            headings = await page.evaluate('''() => {
                const headings = document.querySelectorAll('h1, h2');
                return Array.from(headings)
                    .map(h => h.textContent.trim())
                    .filter(text => text.length > 0 && !text.includes('{{') && !text.includes('}}'));
            }''')

            # Extrai parágrafos principais
            paragraphs = await page.evaluate('''() => {
                const paragraphs = document.querySelectorAll('p, article, [class*="content"] > div');
                return Array.from(paragraphs)
                    .map(p => p.textContent.trim())
                    .filter(text => 
                        text.length > 50 && 
                        !text.includes('{{') && 
                        !text.includes('}}') &&
                        !text.includes('http') &&
                        !text.includes('www.') &&
                        !/^[0-9\s\-+:]+$/.test(text)
                    );
            }''')

            # Extrai texto de listas importantes
            lists = await page.evaluate('''() => {
                const lists = document.querySelectorAll('ul:not([class*="menu"]), ol:not([class*="menu"])');
                return Array.from(lists)
                    .map(list => Array.from(list.querySelectorAll('li'))
                        .map(li => li.textContent.trim())
                        .filter(text => 
                            text.length > 0 && 
                            !text.includes('{{') && 
                            !text.includes('}}') &&
                            !text.includes('http') &&
                            !text.includes('www.')
                        )
                        .join('\\n• '))
                    .filter(text => text.length > 0)
                    .map(text => '• ' + text);
            }''')

            # Combina todo o conteúdo extraído
            content_parts = []
            
            # Adiciona títulos principais sem repetição
            seen_headings = set()
            for heading in headings:
                clean_heading = await self._clean_text(heading, language)
                if clean_heading and clean_heading not in seen_headings:
                    seen_headings.add(clean_heading)
                    content_parts.append(clean_heading)

            # Adiciona parágrafos sem repetição
            seen_paragraphs = set()
            for paragraph in paragraphs:
                clean_paragraph = await self._clean_text(paragraph, language)
                if clean_paragraph and clean_paragraph not in seen_paragraphs:
                    seen_paragraphs.add(clean_paragraph)
                    content_parts.append(clean_paragraph)

            # Adiciona listas sem repetição
            seen_lists = set()
            for list_text in lists:
                clean_list = await self._clean_text(list_text, language)
                if clean_list and clean_list not in seen_lists:
                    seen_lists.add(clean_list)
                    content_parts.append(clean_list)

            # Junta todo o conteúdo com formatação adequada
            content = "\n\n".join(filter(None, content_parts))
            
            # Remove linhas vazias múltiplas e linhas que são apenas caracteres especiais
            content = "\n".join(
                line for line in content.splitlines() 
                if line.strip() and not all(c in '•-_=+#' for c in line.strip())
            )
            
            return content

        except Exception as e:
            logger.error(f"Erro ao extrair conteúdo: {str(e)}")
            # Em caso de erro, tenta extrair o conteúdo de forma mais simples
            content = await page.inner_text('body')
            language = self._detect_language(content)
            return await self._clean_text(content, language)

    def _detect_language(self, text: str) -> str:
        """Detecta o idioma do texto."""
        try:
            return detect(text)
        except:
            return 'pt'  # Padrão para português se não conseguir detectar

    def _normalize_url(self, url: str) -> str:
        """Normaliza a URL removendo âncoras e parâmetros de query."""
        parsed = urlparse(url)
        # Remove a âncora (#) e os parâmetros de query
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    async def _scrape_url(self, url: str) -> dict:
        base_domain = urlparse(url).netloc
        logger.info(f"Iniciando scraping de {url} (domínio base: {base_domain})")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                logger.info("Página carregada com sucesso")

                # Extrai o conteúdo usando o método existente
                content = await self._extract_content(page)
                logger.info(f"Conteúdo extraído: {len(content)} caracteres")

                # Extrai links
                links = await page.evaluate('''() => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors)
                        .map(a => a.href)
                        .filter(href => href && href.startsWith('http'));
                }''')

                # Filtrar apenas links do mesmo domínio e normalizar URLs
                filtered_links = set()  # Usando set para evitar duplicatas
                for link in links:
                    try:
                        # Normaliza o link removendo âncoras e parâmetros
                        normalized_link = self._normalize_url(link)
                        
                        # Verifica se é do mesmo domínio
                        link_domain = urlparse(normalized_link).netloc.replace('www.', '')
                        base_domain_clean = base_domain.replace('www.', '')
                        
                        if link_domain == base_domain_clean:
                            filtered_links.add(normalized_link)
                    except Exception as e:
                        logger.error(f"Erro ao processar link {link}: {str(e)}")

                logger.info(f"Links encontrados: {len(links)}, Filtrados únicos: {len(filtered_links)}")
                if filtered_links:
                    logger.info(f"Exemplos de links filtrados: {list(filtered_links)[:3]}")

                await browser.close()
                return {
                    "content": content,
                    "links": sorted(list(filtered_links))  # Converte o set para lista ordenada
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
