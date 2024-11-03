from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import os

from playwright.sync_api import sync_playwright

app = FastAPI()

# Definir a chave de API a partir de uma variável de ambiente
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("A variável de ambiente API_KEY não está definida.")

# Criar o esquema de segurança
security = HTTPBearer()

# Dependência para verificar a chave de API
def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Chave de API inválida ou ausente.")

# Função para extrair texto visível e links do URL fornecido
def scrape_visible_text_and_links_from_url(url):
    try:
        # Definir os cabeçalhos
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/58.0.3029.110 Safari/537.3'
            )
        }

        # Fazer uma requisição HEAD para obter o tipo de conteúdo
        import requests
        head_response = requests.head(url, headers=headers, allow_redirects=True)
        content_type = head_response.headers.get('Content-Type', '')

        if 'xml' in content_type:
            # Processar conteúdo XML (como sitemap.xml)
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml-xml')

            # Extrair URLs do sitemap
            urls = [loc.get_text() for loc in soup.find_all('loc')]
            result = {
                "content": "",
                "links": urls
            }
            return result
        else:
            # Usar Playwright para renderizar páginas HTML com JavaScript
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers(headers)
                page.goto(url, timeout=60000)  # Timeout de 60 segundos
                page.wait_for_load_state("networkidle", timeout=60000)
                html_content = page.content()
                browser.close()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Remover tags não visíveis (ajustado)
            for tag in soup(["script", "style", "meta", "link", "noscript", "footer", "aside", "nav", "img"]):
                tag.extract()

            # Obter todo o texto visível
            visible_text = soup.get_text(separator=' ', strip=True)

            # Remover espaços em branco múltiplos
            visible_text = re.sub(r'\s+', ' ', visible_text).strip()

            # Extrair todos os links da página sem duplicatas
            links = set()
            for link_tag in soup.find_all('a', href=True):
                href = link_tag.get('href')
                href = urljoin(url, href)  # Resolver URLs relativas
                links.add(href)

            # Converter o conjunto de links de volta para uma lista
            links = list(links)

            # Criar o objeto JSON
            result = {
                "content": visible_text,
                "links": links
            }

            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar a URL: {str(e)}")

# Rota principal da API com autenticação
@app.get("/scrape")
def scrape(url: str, credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    result = scrape_visible_text_and_links_from_url(url)
    if result:
        return JSONResponse(content=result)
    else:
        raise HTTPException(status_code=404, detail="Falha ao extrair dados da URL.")
