from typing import Optional, Dict, List
import asyncio
import uuid
from datetime import datetime
import logging
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import aiohttp
from langdetect import detect
from app.models import ScrapeResult, ProcessingStatus, ScrapeResponse

logger = logging.getLogger(__name__)

class ScrapingService:
    def __init__(self):
        self._tasks: Dict[str, ScrapeResult] = {}

    def get_task(self, task_id: str) -> Optional[ScrapeResponse]:
        """
        Retorna o status de uma tarefa.
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            Optional[ScrapeResponse]: Detalhes da tarefa ou None se não encontrada
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
            
        return ScrapeResponse(
            id=task.id,
            status=task.status.value,
            message="Processamento concluído com sucesso" if task.status == ProcessingStatus.COMPLETED 
                   else "Erro: " + task.error if task.error 
                   else "Processamento em andamento",
            content=task.content if task.status == ProcessingStatus.COMPLETED else None,
            links=task.links if task.status == ProcessingStatus.COMPLETED else None,
            error=task.error
        )

    async def start_scraping(self, url: str, callback_url: Optional[str] = None) -> str:
        """
        Inicia o processo de scraping de uma URL.
        
        Args:
            url: URL para fazer scraping
            callback_url: URL opcional para webhook de notificação
            
        Returns:
            str: ID da tarefa criada
        """
        task_id = str(uuid.uuid4())
        
        # Cria a tarefa com status inicial
        self._tasks[task_id] = ScrapeResult(
            id=task_id,
            url=str(url),
            status=ProcessingStatus.PENDING,
            created_at=datetime.now()
        )
        
        # Inicia o processamento em background
        asyncio.create_task(self.process_url(task_id, str(url), str(callback_url) if callback_url else None))
        
        return task_id

    async def process_url(self, task_id: str, url: str, callback_url: Optional[str] = None):
        """Processa uma URL e atualiza o status da tarefa."""
        try:
            self._tasks[task_id].status = ProcessingStatus.PROCESSING
            
            # Executa o scraping
            result = await self._scrape_url(url)
            
            # Atualiza a tarefa com o resultado
            task = self._tasks[task_id]
            task.status = ProcessingStatus.COMPLETED
            task.content = result["content"]
            task.links = result["links"]
            task.completed_at = datetime.now()
            
            # Envia callback se necessário
            if callback_url:
                await self._send_callback(callback_url, task)
                
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {str(e)}")
            task = self._tasks[task_id]
            task.status = ProcessingStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            
            if callback_url:
                try:
                    await self._send_callback(callback_url, task)
                except Exception as e:
                    logger.error(f"Erro ao enviar callback: {str(e)}")

    async def _scrape_url(self, url: str) -> dict:
        """
        Executa o scraping de uma URL usando Playwright.
        
        Args:
            url: URL para fazer scraping
            
        Returns:
            dict: Dicionário com o conteúdo extraído e links encontrados
        """
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

                # Extrai links com uma abordagem mais abrangente
                links = await page.evaluate('''() => {
                    function getAllLinks() {
                        // Pega todos os elementos <a> da página
                        const anchors = Array.from(document.querySelectorAll('a[href]'));
                        
                        // Pega elementos que podem ter URLs em atributos específicos
                        const otherElements = Array.from(document.querySelectorAll('[src], [data-url], [data-href]'));
                        
                        let urls = new Set();
                        
                        // Processa links de âncoras
                        anchors.forEach(a => {
                            if (a.href && a.href.startsWith('http')) {
                                urls.add(a.href);
                            }
                        });
                        
                        // Processa outros elementos com URLs
                        otherElements.forEach(el => {
                            if (el.src && el.src.startsWith('http')) {
                                urls.add(el.src);
                            }
                            if (el.dataset.url && el.dataset.url.startsWith('http')) {
                                urls.add(el.dataset.url);
                            }
                            if (el.dataset.href && el.dataset.href.startsWith('http')) {
                                urls.add(el.dataset.href);
                            }
                        });
                        
                        return Array.from(urls);
                    }
                    return getAllLinks();
                }''')

                # Filtrar e normalizar URLs
                filtered_links = set()  # Usando set para evitar duplicatas
                base_domain_clean = base_domain.replace('www.', '')
                
                for link in links:
                    try:
                        # Normaliza o link removendo âncoras e parâmetros
                        normalized_link = self._normalize_url(link)
                        parsed_link = urlparse(normalized_link)
                        
                        # Verifica se é do mesmo domínio
                        link_domain = parsed_link.netloc.replace('www.', '')
                        
                        if link_domain == base_domain_clean:
                            # Verifica se o link não é apenas uma âncora ou página em branco
                            if parsed_link.path and parsed_link.path != '/' and not parsed_link.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.css', '.js')):
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

    async def _extract_content(self, page) -> str:
        """
        Extrai o conteúdo textual relevante da página.
        
        Args:
            page: Página do Playwright
            
        Returns:
            str: Conteúdo textual extraído e limpo
        """
        # Remove elementos que geralmente não contêm conteúdo relevante
        await page.evaluate('''() => {
            const elementsToRemove = document.querySelectorAll('script, style, noscript, iframe, img');
            elementsToRemove.forEach(el => el.remove());
        }''')
        
        # Extrai o texto visível
        content = await page.evaluate('''() => {
            function extractText(element) {
                let text = '';
                for (let node of element.childNodes) {
                    if (node.nodeType === 3) { // Node.TEXT_NODE
                        text += node.textContent.trim() + '\\n';
                    } else if (node.nodeType === 1) { // Node.ELEMENT_NODE
                        const style = window.getComputedStyle(node);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            text += extractText(node);
                        }
                    }
                }
                return text;
            }
            return extractText(document.body);
        }''')
        
        # Limpa e normaliza o texto
        return self._clean_text(content)

    def _clean_text(self, text: str) -> str:
        """
        Limpa e normaliza o texto extraído.
        
        Args:
            text: Texto para limpar
            
        Returns:
            str: Texto limpo e normalizado
        """
        # Remove espaços extras e linhas em branco
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        
        # Junta as linhas com quebras de linha
        return '\n'.join(lines)

    def _normalize_url(self, url: str) -> str:
        """
        Normaliza a URL removendo âncoras, parâmetros de query e trailing slashes.
        
        Args:
            url: URL para normalizar
            
        Returns:
            str: URL normalizada
        """
        try:
            parsed = urlparse(url)
            # Remove a âncora (#) e os parâmetros de query
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # Remove trailing slash se não for a raiz
            if normalized != f"{parsed.scheme}://{parsed.netloc}/" and normalized.endswith('/'):
                normalized = normalized[:-1]
            return normalized
        except Exception as e:
            logger.error(f"Erro ao normalizar URL {url}: {str(e)}")
            return url

    async def _send_callback(self, callback_url: str, task: ScrapeResult):
        """
        Envia o resultado para a URL de callback.
        
        Args:
            callback_url: URL para enviar o callback
            task: Tarefa com o resultado
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "id": task.id,
                "status": task.status.value,
                "content": task.content if task.status == ProcessingStatus.COMPLETED else None,
                "links": task.links if task.status == ProcessingStatus.COMPLETED else None,
                "error": task.error if task.error else None
            }
            async with session.post(callback_url, json=payload) as response:
                if response.status >= 400:
                    raise Exception(f"Erro ao enviar callback: {response.status}")
