import streamlit as st
import requests
from bs4 import BeautifulSoup
import re

# Function to scrape only visible text from the given URL
def scrape_visible_text_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script, style, and other non-visible tags
        for tag in soup(["script", "style", "meta", "link", "noscript", "header", "footer", "aside", "nav", "img"]):
            tag.extract()

        # Get the header content
        header_content = soup.find("header")
        header_text = header_content.get_text() if header_content else ""

        # Get the paragraph content
        paragraph_content = soup.find_all("p")
        paragraph_text = " ".join([p.get_text() for p in paragraph_content])

        # Combine header and paragraph text
        visible_text = f"{header_text}\n\n{paragraph_text}"

        # Remove multiple whitespaces and newlines
        visible_text = re.sub(r'\s+', ' ', visible_text)
        return visible_text.strip()
    except Exception as e:
        st.error(f"Error occurred while scraping the data: {e}")
        return None

# Streamlit UI
def main():
    st.title("Web Data Scraper")

    # Get query parameters
    params = st.experimental_get_query_params()
    url_input = params.get('url', [''])[0]  # Get 'url' parameter from query string

    # If URL is not provided via query string, use text input
    if not url_input:
        url_input = st.text_input("Enter the URL of the web page:", "")

    # If URL is provided, automatically scrape
    if url_input:
        # Extract visible text from the URL
        data = scrape_visible_text_from_url(url_input)
        if data:
            st.success("Visible text successfully scraped!")
            st.subheader("Scraped Text:")
            st.write(data)
        else:
            st.warning("Failed to scrape visible text from the URL.")
    else:
        st.warning("Please enter a valid URL.")

if __name__ == "__main__":
    main()
