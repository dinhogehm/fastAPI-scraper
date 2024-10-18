import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin

# Function to scrape visible text and links from the given URL
def scrape_visible_text_and_links_from_url(url):
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
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()

        # Now extract all links that are from the same domain
        domain = urlparse(url).netloc

        # Collect all links from the page
        links = []
        for link_tag in soup.find_all('a', href=True):
            href = link_tag.get('href')
            # Resolve relative URLs
            href = urljoin(url, href)
            href_parsed = urlparse(href)
            # Check if the domain matches
            if href_parsed.netloc == domain:
                links.append(href)

        return visible_text, links
    except Exception as e:
        st.error(f"Error occurred while scraping the data: {e}")
        return None, None

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
        # Extract visible text and links from the URL
        data, links = scrape_visible_text_and_links_from_url(url_input)
        if data:
            st.success("Visible text successfully scraped!")
            st.subheader("Scraped Text:")
            st.write(data)

            # Display the links
            if links:
                st.subheader("Links from the same domain:")
                for link in links:
                    st.write(link)
            else:
                st.warning("No links from the same domain were found.")
        else:
            st.warning("Failed to scrape visible text from the URL.")
    else:
        st.warning("Please enter a valid URL.")

if __name__ == "__main__":
    main()
