#spider.py
import scrapy
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
from datetime import datetime

class ParariusSpider(scrapy.Spider):
    name = 'pararius'
    allowed_domains = ['pararius.com']
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 5,
    }
    
    def __init__(self, url=None, subscription_id=None, *args, **kwargs):
        super(ParariusSpider, self).__init__(*args, **kwargs)
        
        if not url:
            raise ValueError("URL is required for the spider")
        
        self.start_urls = [url]
        self.subscription_id = subscription_id
        self.new_listings = []
        
        # Configure selenium logging
        selenium_logger = logging.getLogger('selenium')
        selenium_logger.setLevel(logging.ERROR)
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.ERROR)
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")
        
        try:
            # Try to initialize the Chrome WebDriver with automatic driver management
            self.driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("Successfully initialized Chrome WebDriver")
        except Exception as e:
            self.logger.error(f"Error initializing Chrome WebDriver with automatic driver: {str(e)}")
            try:
                # Try using the ChromeDriverManager as a fallback
                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()), 
                    options=chrome_options
                )
                self.logger.info("Successfully initialized Chrome WebDriver with ChromeDriverManager")
            except Exception as e:
                self.logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
                # Create a dummy driver to prevent errors (will be detected in parse method)
                self.driver = None

    def parse(self, response):
        if self.driver is None:
            self.logger.error("WebDriver is not available. Stopping the spider.")
            return
            
        self.logger.info(f"Scraping URL: {response.url}")
        
        try:
            self.driver.get(response.url)
            
            # Wait for the listings to load
            wait = WebDriverWait(self.driver, 10)
            listings = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.search-list__item--listing')))
            
            self.logger.info(f"Found {len(listings)} total listings")
            
            for listing in listings:
                try:
                    # Extract listing details using Selenium
                    title = listing.find_element(By.CSS_SELECTOR, 'h2.listing-search-item__title').text
                    price = listing.find_element(By.CSS_SELECTOR, 'div.listing-search-item__price').text
                    url = listing.find_element(By.CSS_SELECTOR, 'a.listing-search-item__link--title').get_attribute('href')
                    
                    try:
                        address = listing.find_element(By.CSS_SELECTOR, 'div.listing-search-item__sub-title').text
                    except:
                        address = None
                    
                    # Get specifications
                    try:
                        specs = [elem.text for elem in listing.find_elements(By.CSS_SELECTOR, 'ul.illustrated-features__list li')]
                        specs_str = ', '.join(specs)
                    except:
                        specs_str = ""
                    
                    if all([title, price, url]):  # Address is optional
                        item = {
                            'title': title,
                            'price': price,
                            'url': url,
                            'address': address,
                            'specs': specs_str,
                            'date_found': datetime.now(),
                            'subscription_id': self.subscription_id
                        }
                        self.new_listings.append(item)
                        self.logger.info(f"Found listing: {title}")
                            
                except Exception as e:
                    self.logger.error(f"Error processing listing: {str(e)}")
                    continue

            # Check for next page and follow if exists
            try:
                next_page = self.driver.find_element(By.CSS_SELECTOR, 'a[rel="next"]').get_attribute('href')
                if next_page:
                    self.logger.info(f"Following next page: {next_page}")
                    yield scrapy.Request(next_page, callback=self.parse)
            except:
                self.logger.info("No next page found")
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
    
    def closed(self, reason):
        """Clean up resources when the spider closes."""
        self.logger.info("Cleaning up resources...")
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
                self.logger.info("WebDriver closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing WebDriver: {str(e)}")