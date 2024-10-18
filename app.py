# Seu código ajustado da aplicação Streamlit
import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin
import json

# Função para extrair texto visível e links do URL fornecido
def scrape_visible_text_and_links_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
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

        # Extrair todos os links da página
        links = []
        for link_tag in soup.find_all('a', href=True):
            href = link_tag.get('href')
            href = urljoin(url, href)  # Resolver URLs relativas
            links.append(href)

        # Criar o objeto JSON
        result = {
            "content": visible_text,
            "links": links
        }

        return result
    except Exception as e:
        st.error(f"Erro ao extrair os dados: {e}")
        return None

# Interface do Streamlit
def main():
    st.title("Web Data Scraper")

    # Obter parâmetros de consulta
    params = st.experimental_get_query_params()
    url_input = params.get('url', [''])[0]  # Obter o parâmetro 'url' da query string

    # Se a URL não for fornecida via query string, usar entrada de texto
    if not url_input:
        url_input = st.text_input("Digite a URL da página web:", "")

    # Se a URL for fornecida, realizar a extração automaticamente
    if url_input:
        # Extrair texto visível e links da URL
        result = scrape_visible_text_and_links_from_url(url_input)
        if result:
            st.success("Dados extraídos com sucesso!")
            st.subheader("Resultado em JSON:")
            st.json(result)
        else:
            st.warning("Falha ao extrair os dados da URL.")
    else:
        st.warning("Por favor, insira uma URL válida.")

if __name__ == "__main__":
    main()
