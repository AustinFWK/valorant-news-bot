from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from config import (
    VALORANT_NEWS_URL,
    ARTICLE_LINK_SELECTOR,
    ARTICLE_CONTENT_SELECTOR
)

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

#can comment out for testing
options.binary_location = "/usr/bin/chromium-browser"
service = Service("/usr/bin/chromedriver")

def is_youtube_link(url):
    """Check if a given URL is a YouTube link."""
    return "youtube.com" in url or "youtu.be" in url


def get_latest_patch_notes():
    """Scrape the latest patch notes from Valorant's website."""

    #can comment out for testing
    driver = webdriver.Chrome(options=options, service=service)

    try:
        # Navigate to the news page
        driver.get(VALORANT_NEWS_URL)
        driver.implicitly_wait(5)

        # Find the most recent article link
        article_link = driver.find_element(By.CSS_SELECTOR, ARTICLE_LINK_SELECTOR)
        article_url = article_link.get_attribute('href')

        #check if it's a youtube link
        if is_youtube_link(article_url):
            return None, article_url, 'video'

        # Navigate to the article
        driver.get(article_url)
        driver.implicitly_wait(10)

        try:
            # Get the article content as HTML to preserve formatting
            content_divs = driver.find_elements(By.CSS_SELECTOR, ARTICLE_CONTENT_SELECTOR)
            html_content = '\n'.join(div.get_attribute('innerHTML') for div in content_divs)
            return html_content, article_url, 'article'
        except NoSuchElementException:
            return None, article_url, 'video'
    finally:
        driver.quit()


def get_latest_article_url():
    """Get just the URL of the latest article (for checking updates)."""
    driver = webdriver.Chrome(options=options, service=service)

    try:
        driver.get(VALORANT_NEWS_URL)
        driver.implicitly_wait(5)

        article_link = driver.find_element(By.CSS_SELECTOR, ARTICLE_LINK_SELECTOR)
        return article_link.get_attribute('href')

    finally:
        driver.quit()
