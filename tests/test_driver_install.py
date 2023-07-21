from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument('--headless')

driver = webdriver.Chrome(options=chrome_options)
driver.get("https://www.duckduckgo.com")

title = driver.title

driver.quit()

assert title == 'DuckDuckGo — Privacy, simplified.', \
    'Mismatch between DuckDuckGo\'s title and fetched title (you should investigate this further)'

print('Successful')
