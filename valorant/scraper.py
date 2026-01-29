from selenium import webdriver
from selenium.webdriver.common.by import By
from config import (
    VALORANT_NEWS_URL,
    ARTICLE_LINK_SELECTOR,
    ARTICLE_CONTENT_SELECTOR
)


def get_latest_patch_notes():
    """Scrape the latest patch notes from Valorant's website."""
    driver = webdriver.Chrome()

    try:
        # Navigate to the news page
        driver.get(VALORANT_NEWS_URL)
        driver.implicitly_wait(5)

        # Find the most recent article link
        article_link = driver.find_element(By.CSS_SELECTOR, ARTICLE_LINK_SELECTOR)
        article_url = article_link.get_attribute('href')

        # Navigate to the article
        driver.get(article_url)
        driver.implicitly_wait(10)

        # Get the article content
        content_div = driver.find_element(By.CSS_SELECTOR, ARTICLE_CONTENT_SELECTOR)
        text_content = content_div.text

        return text_content, article_url

    finally:
        driver.quit()


def get_latest_article_url():
    """Get just the URL of the latest article (for checking updates)."""
    driver = webdriver.Chrome()

    try:
        driver.get(VALORANT_NEWS_URL)
        driver.implicitly_wait(5)

        article_link = driver.find_element(By.CSS_SELECTOR, ARTICLE_LINK_SELECTOR)
        return article_link.get_attribute('href')

    finally:
        driver.quit()
