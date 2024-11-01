from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import os

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
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/58.0.3029.110 Safari/537.3'
            )
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Verificar o tipo de conteúdo
        content_type = response.headers.get('Content-Type', '')
        if 'xml' in content_type:
            # Processar conteúdo XML (como sitemap.xml)
            soup = BeautifulSoup(response.content, 'lxml-xml')
            # Extrair URLs do sitemap
            urls = [loc.get_text() for loc in soup.find_all('loc')]
            result = {
                "content": "",
                "links": urls
            }
            return result
        else:
            # Processar conteúdo HTML normal
            soup = BeautifulSoup(response.content, 'html.parser')

            # Remover tags não visíveis
            for tag in soup(["script", "style", "meta", "link", "noscript", "header", "footer", "aside", "nav", "img"]):
                tag.extract()

            # Obter o conteúdo do cabeçalho
            header_content = soup.find("header")
            header_text = header_content.get_text() if header_content else ""

            # Obter o conteúdo dos parágrafos
            paragraph_content = soup.find_all("p")
            paragraph_text = " ".join([p.get_text() for p in paragraph_content])

            # Combinar o texto do cabeçalho e dos parágrafos
            visible_text = f"{header_text}\n\n{paragraph_text}"

            # Remover espaços em branco múltiplos e novas linhas
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
        raise HTTPException(status_code=500, detail=str(e))

# Rota principal da API com autenticação
@app.get("/scrape")
def scrape(url: str, credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    result = scrape_visible_text_and_links_from_url(url)
    if result:
        return JSONResponse(content=result)
    else:
        raise HTTPException(status_code=404, detail="Falha ao extrair dados da URL.")
