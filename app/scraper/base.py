# app/scraper/base.py
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import db
from app.models import Listing, City
from app.scraper.utils import parse_price, parse_bedrooms, parse_area

logger = logging.getLogger(__name__)

class BaseScraper:
    """Base scraper class that all city-specific scrapers inherit from."""

    def __init__(self, city, max_pages=10):
        self.city = city
        self.max_pages = max_pages
        self.base_url = city.base_url

    def setup_driver(self):
        """Set up and return a configured Chrome WebDriver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
            return None

    def scrape(self):
        """Main scraping method that coordinates the scraping process."""
        logger.info(f"Starting apartment scraper for {self.city.name} (URL: {self.base_url})")

        driver = self.setup_driver()
        if not driver:
            logger.error("Failed to initialize WebDriver. Aborting scrape.")
            return False, 0, 0

        try:
            # Get existing listing URLs from the database for this city
            existing_urls = set(url[0] for url in
                              db.session.query(Listing.url).filter(Listing.city_id == self.city.id).all())
            logger.info(f"Found {len(existing_urls)} existing listings for {self.city.name} in database")

            all_listings = []
            new_listings = []

            current_url = self.base_url
            page_num = 1

            while current_url and page_num <= self.max_pages:
                success, page_listings, next_url = self.scrape_page(driver, current_url, page_num, existing_urls)

                if success and page_listings:
                    all_listings.extend(page_listings)

                    # Filter new listings
                    new_page_listings = [l for l in page_listings if l['url'] not in existing_urls]
                    new_listings.extend(new_page_listings)

                    # Update existing URLs to avoid duplicates
                    for listing in new_page_listings:
                        existing_urls.add(listing['url'])

                current_url = next_url
                page_num += 1

                if not current_url:
                    logger.info(f"No more pages to scrape for {self.city.name}")
                    break

            # Save new listings to database
            new_listing_objects = self.save_listings(new_listings)

            # Match listings to subscriptions
            if new_listing_objects:
                from app.scraper.utils import match_listings_to_subscriptions
                match_listings_to_subscriptions(new_listing_objects)

            return True, len(all_listings), len(new_listing_objects)

        except Exception as e:
            logger.error(f"Error in {self.city.name} scraper: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, 0, 0

        finally:
            if driver:
                driver.quit()
                logger.info(f"WebDriver closed for {self.city.name} scraper")

    def scrape_page(self, driver, page_url, page_num, existing_urls):
        """Scrape a single page of apartment listings."""
        logger.info(f"Scraping page {page_num} for {self.city.name}: {page_url}")

        try:
            driver.get(page_url)

            # Wait for the listings to load
            wait = WebDriverWait(driver, 10)
            listings = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.search-list__item--listing')))

            logger.info(f"Found {len(listings)} listings on page {page_num} for {self.city.name}")

            page_listings = []
            for listing in listings:
                try:
                    listing_data = self.parse_listing(listing)
                    if listing_data:
                        page_listings.append(listing_data)
                except Exception as e:
                    logger.error(f"Error processing listing in {self.city.name}: {str(e)}")
                    continue

            # Find the next page link if it exists
            try:
                next_page = driver.find_element(By.CSS_SELECTOR, 'a[rel="next"]')
                next_url = next_page.get_attribute('href')
            except:
                logger.info(f"No next page found for {self.city.name}, ending scrape")
                next_url = None

            return True, page_listings, next_url

        except Exception as e:
            logger.error(f"Error scraping page {page_num} for {self.city.name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False, [], None

    def parse_listing(self, listing_element):
        """Extract data from a listing element. Override in city-specific subclasses if needed."""
        try:
            title = listing_element.find_element(By.CSS_SELECTOR, 'h2.listing-search-item__title').text
            price_text = listing_element.find_element(By.CSS_SELECTOR, 'div.listing-search-item__price').text
            url = listing_element.find_element(By.CSS_SELECTOR, 'a.listing-search-item__link--title').get_attribute('href')

            try:
                address = listing_element.find_element(By.CSS_SELECTOR, 'div.listing-search-item__sub-title').text
            except:
                address = None

            # Get specifications
            try:
                specs_elems = listing_element.find_elements(By.CSS_SELECTOR, 'ul.illustrated-features__list li')
                specs = [elem.text for elem in specs_elems]
                specs_str = ', '.join(specs)
            except:
                specs = []
                specs_str = ""

            # Parse numeric values
            price = parse_price(price_text)
            bedrooms = parse_bedrooms(specs_str)
            area = parse_area(specs_str)

            if all([title, price_text, url, price]):
                return {
                    'title': title,
                    'price': price,
                    'price_text': price_text,
                    'url': url,
                    'address': address,
                    'bedrooms': bedrooms,
                    'area': area,
                    'specs': specs_str,
                    'date_found': datetime.now(),
                    'city_id': self.city.id
                }
            return None
        except Exception as e:
            logger.error(f"Error parsing listing in {self.city.name}: {str(e)}")
            return None

    def save_listings(self, new_listings):
        """Save new listings to the database."""
        if not new_listings:
            logger.info(f"No new listings to save for {self.city.name}")
            return []

        logger.info(f"Saving {len(new_listings)} new listings for {self.city.name}")

        new_listing_objects = []
        for data in new_listings:
            try:
                # Create new listing object
                listing_obj = Listing(
                    title=data['title'],
                    price=data['price'],
                    price_text=data['price_text'],
                    url=data['url'],
                    address=data['address'],
                    bedrooms=data['bedrooms'],
                    area=data['area'],
                    specs=data['specs'],
                    date_found=data['date_found'],
                    city_id=data['city_id']
                )

                db.session.add(listing_obj)
                db.session.flush()  # Get the ID without committing
                new_listing_objects.append(listing_obj)

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding listing for {self.city.name} to database: {str(e)}")
                continue

        # Commit all new listings
        if new_listing_objects:
            try:
                db.session.commit()
                logger.info(f"Added {len(new_listing_objects)} new listings for {self.city.name} to database")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error committing new listings for {self.city.name}: {str(e)}")

        return new_listing_objects