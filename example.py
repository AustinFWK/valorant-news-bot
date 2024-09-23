#thsese are imports that you need in order to properly web scrape websites
#importing BeautifulSoup so we can use it
from bs4 import BeautifulSoup

#Importing Selenium so we can use it
from selenium.webdriver.common.by import By
from selenium import webdriver

@client.command()
async def scrape_patch_notes(ctx):
    # Initialize Chrome WebDriver
    driver = webdriver.Chrome()

    #insert the web page you want to scrape within the partenthese
    driver.get('page url')

    # Wait for dynamic content to load
    driver.implicitly_wait(5)

    # Get the HTML content after the page is fully loaded
    #HTML has differnet kinds of content such as a <div>, <container>, <header>, etc and we need to load all of this from the website
    html_content = driver.page_source

    # Parse the HTML content with BeautifulSoup, not sure if this is required but this is what I used in my scraping
    soup = BeautifulSoup(html_content, 'html.parser')

    #here we have a variable that uses selenium to find a specific element by the class name of that element 
    specific_div = driver.find_element(By.CLASS_NAME, 'insert class name here')


    #The variable finds the div from the specified link and find the specific class within that div, and then retrieves the
    #text from that div, which is going to be the review in this case
    div_in_href = new_page_soup.find('div', {'class': 'sectionWrapper NewsArticleContent-module--articleSectionWrapper--a5tPH'})
    text_content = div_in_href.get_text()


    # Close the WebDriver
    driver.quit()

    
#This is just to web scrape and actually retrieve the content, after we retrieve the content we still have to
#manipulate the data but I'm sure there is a way to do that whether it be with pandas for visual, or the NLTK library for sentiment analysis
