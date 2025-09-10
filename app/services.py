from typing import Optional, Dict, List, Set
import asyncio
import uuid
from datetime import datetime
import logging
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
import aiohttp
from langdetect import detect
import xml.etree.ElementTree as ET
from app.models import ScrapeResult, ProcessingStatus, ScrapeResponse

logger = logging.getLogger(__name__)

class ScrapingService:
    def __init__(self):
        self._tasks: Dict[str, ScrapeResult] = {}
        self._processing_queues: Dict[str, List[str]] = {}
        self._processed_urls: Dict[str, Set[str]] = {}
        self._all_content: Dict[str, List[dict]] = {}

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
        
        queue_size = len(self._processing_queues.get(task_id, []))
        processed_count = task.processed_count or 0
        
        message = "Processamento concluído com sucesso"
        if task.status == ProcessingStatus.PROCESSING:
            message = f"Processando... {processed_count}/{task.limit or 10} páginas. Fila: {queue_size}"
        elif task.error:
            message = "Erro: " + task.error
        elif task.status == ProcessingStatus.PENDING:
            message = "Processamento iniciado"
            
        return ScrapeResponse(
            id=task.id,
            status=task.status.value,
            message=message,
            content=task.content if task.status == ProcessingStatus.COMPLETED else None,
            links=task.links if task.status == ProcessingStatus.COMPLETED else None,
            error=task.error,
            limit=task.limit,
            processed_count=processed_count,
            queue_size=queue_size,
            all_content=task.all_content if task.status == ProcessingStatus.COMPLETED else None
        )

    async def start_scraping(self, url: str, callback_url: Optional[str] = None, limit: int = 10) -> str:
        """
        Inicia o processo de scraping de uma URL com sistema de fila.
        
        Args:
            url: URL para fazer scraping
            callback_url: URL opcional para webhook de notificação
            limit: Limite máximo de páginas a processar
            
        Returns:
            str: ID da tarefa criada
        """
        task_id = str(uuid.uuid4())
        
        # Cria a tarefa com status inicial
        self._tasks[task_id] = ScrapeResult(
            id=task_id,
            url=str(url),
            status=ProcessingStatus.PENDING,
            created_at=datetime.now(),
            limit=limit,
            processed_count=0
        )
        
        # Inicializa estruturas de controle da fila
        self._processing_queues[task_id] = []
        self._processed_urls[task_id] = set()
        self._all_content[task_id] = []
        
        # Inicia o processamento em background
        asyncio.create_task(self.process_queue(task_id, str(url), str(callback_url) if callback_url else None))
        
        return task_id

    async def process_queue(self, task_id: str, initial_url: str, callback_url: Optional[str] = None):
        """Processa a fila de URLs iterativamente até atingir o limite."""
        try:
            self._tasks[task_id].status = ProcessingStatus.PROCESSING
            
            # Busca arquivos centralizadores primeiro
            centralized_urls = await self._find_centralized_urls(initial_url)
            
            # Adiciona URLs centralizadas à fila
            if centralized_urls:
                self._processing_queues[task_id].extend(centralized_urls)
                logger.info(f"Encontrados {len(centralized_urls)} URLs em arquivos centralizadores")
            
            # Adiciona URL inicial à fila se não estiver nos centralizadores
            if initial_url not in centralized_urls:
                self._processing_queues[task_id].insert(0, initial_url)
            
            task = self._tasks[task_id]
            limit = task.limit or 10
            
            # Processa URLs da fila até atingir o limite
            while (self._processing_queues[task_id] and 
                   task.processed_count < limit):
                
                current_url = self._processing_queues[task_id].pop(0)
                
                # Evita processar URLs duplicadas
                if current_url in self._processed_urls[task_id]:
                    continue
                
                self._processed_urls[task_id].add(current_url)
                
                try:
                    # Processa a URL atual
                    result = await self._scrape_url(current_url)
                    
                    # Adiciona conteúdo à lista completa
                    self._all_content[task_id].append({
                        "url": current_url,
                        "content": result["content"],
                        "links_found": len(result["links"])
                    })
                    
                    # Adiciona novos links à fila (se ainda não processados)
                    for link in result["links"]:
                        if (link not in self._processed_urls[task_id] and 
                            link not in self._processing_queues[task_id] and
                            len(self._processing_queues[task_id]) + task.processed_count < limit):
                            self._processing_queues[task_id].append(link)
                    
                    task.processed_count += 1
                    logger.info(f"Processada {task.processed_count}/{limit}: {current_url}")
                    
                except Exception as e:
                    logger.error(f"Erro ao processar URL {current_url}: {str(e)}")
                    continue
            
            # Finaliza a tarefa
            await self._finalize_task(task_id, callback_url)
                
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
    
    async def _find_centralized_urls(self, base_url: str) -> List[str]:
        """Busca por arquivos centralizadores de links (llm.txt e sitemap.xml)."""
        centralized_urls = []
        
        try:
            from urllib.parse import urljoin, urlparse
            parsed_url = urlparse(base_url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Lista de arquivos centralizadores para verificar
            centralized_files = [
                "/llm.txt",
                "/sitemap.xml",
                "/robots.txt"  # Pode conter referências a sitemaps
            ]
            
            for file_path in centralized_files:
                try:
                    file_url = urljoin(base_domain, file_path)
                    logger.info(f"Verificando arquivo centralizador: {file_url}")
                    
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(file_url) as response:
                            if response.status == 200:
                                content = await response.text()
                                
                                if file_path.endswith('.txt'):
                                    # Para arquivos .txt, cada linha é uma URL
                                    urls = self._parse_text_file(content, base_domain)
                                    centralized_urls.extend(urls)
                                    logger.info(f"Encontradas {len(urls)} URLs em {file_url}")
                                    
                                elif file_path.endswith('.xml'):
                                    # Para sitemaps XML
                                    urls = self._parse_sitemap_xml(content)
                                    centralized_urls.extend(urls)
                                    logger.info(f"Encontradas {len(urls)} URLs em {file_url}")
                                    
                except Exception as e:
                    logger.debug(f"Arquivo {file_url} não encontrado ou inacessível: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erro ao buscar arquivos centralizadores: {str(e)}")
            
        return list(set(centralized_urls))  # Remove duplicatas
    
    def _parse_text_file(self, content: str, base_domain: str) -> List[str]:
        """Extrai URLs de arquivos de texto."""
        urls = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Se a linha não começa com http, assume que é relativa
                if not line.startswith(('http://', 'https://')):
                    line = urljoin(base_domain, line)
                urls.append(line)
                
        return urls
    
    def _parse_sitemap_xml(self, content: str) -> List[str]:
        """Extrai URLs de sitemaps XML."""
        urls = []
        
        try:
            root = ET.fromstring(content)
            
            # Namespace comum para sitemaps
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            # Busca por elementos <url><loc>
            for url_elem in root.findall('.//sitemap:url/sitemap:loc', namespaces):
                if url_elem.text:
                    urls.append(url_elem.text.strip())
            
            # Se não encontrou com namespace, tenta sem
            if not urls:
                for url_elem in root.findall('.//loc'):
                    if url_elem.text:
                        urls.append(url_elem.text.strip())
                        
        except ET.ParseError as e:
            logger.error(f"Erro ao parsear XML do sitemap: {str(e)}")
            
        return urls
    
    async def _finalize_task(self, task_id: str, callback_url: Optional[str] = None):
        """Finaliza uma tarefa de scraping."""
        task = self._tasks[task_id]
        
        # Combina todo o conteúdo processado
        all_content_text = "\n\n".join([
            f"=== {item['url']} ===\n{item['content']}"
            for item in self._all_content[task_id]
        ])
        
        # Coleta todos os links únicos encontrados
        all_links = set()
        for item in self._all_content[task_id]:
            # Extrai links do conteúdo se necessário
            pass
        
        # Atualiza a tarefa final
        task.status = ProcessingStatus.COMPLETED
        task.content = all_content_text
        task.links = list(all_links) if all_links else []
        task.all_content = self._all_content[task_id]
        task.completed_at = datetime.now()
        
        # Limpa estruturas temporárias
        self._processing_queues.pop(task_id, None)
        self._processed_urls.pop(task_id, None)
        # Mantém _all_content para consulta posterior
        
        # Envia callback se necessário
        if callback_url:
            await self._send_callback(callback_url, task)
            
        logger.info(f"Tarefa {task_id} finalizada: {task.processed_count} páginas processadas")

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
