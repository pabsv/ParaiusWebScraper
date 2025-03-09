import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re
from app import db
from app.models import Listing, Subscription, User, City
from flask import current_app
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

def parse_price(price_text):
    """Extract price as integer from price text"""
    if not price_text:
        return None

    # Extract numeric value using regex
    match = re.search(r'€\s*([\d.,]+)', price_text)
    if match:
        # Remove thousand separators and convert to integer
        price_str = match.group(1).replace('.', '').replace(',', '')
        try:
            return int(price_str)
        except ValueError:
            logger.error(f"Failed to parse price: {price_text}")

    return None

def parse_bedrooms(specs_text):
    """Extract number of bedrooms from specifications text"""
    if not specs_text:
        return None

    # Look for patterns like "2 rooms" or "2 kamers"
    match = re.search(r'(\d+)\s*(?:room|rooms|kamer|kamers)', specs_text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    return None

def parse_area(specs_text):
    """Extract area in m² from specifications text"""
    if not specs_text:
        return None

    # Look for patterns like "80 m²"
    match = re.search(r'(\d+)\s*m²', specs_text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    return None

def scrape_eindhoven_apartments():
    """Scrape all apartment listings in Eindhoven"""
    base_url = "https://www.pararius.com/apartments/eindhoven"
    logger.info(f"Starting Eindhoven apartment scraper for URL: {base_url}")

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        # Initialize Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Successfully initialized Chrome WebDriver")

        # Get existing listing URLs from the database
        existing_urls = set(url[0] for url in db.session.query(Listing.url).all())
        logger.info(f"Found {len(existing_urls)} existing listings in database")

        # Lists to track all listings and new listings
        all_listings = []
        new_listings = []

        current_url = base_url
        page_num = 1
        max_pages = 10  # Limit to 10 pages to avoid overloading

        while current_url and page_num <= max_pages:
            logger.info(f"Scraping page {page_num}: {current_url}")

            try:
                # Navigate to the current page
                driver.get(current_url)

                # Wait for the listings to load
                wait = WebDriverWait(driver, 10)
                listings = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.search-list__item--listing')))

                logger.info(f"Found {len(listings)} listings on page {page_num}")

                # Process each listing
                for listing in listings:
                    try:
                        # Extract listing details
                        title = listing.find_element(By.CSS_SELECTOR, 'h2.listing-search-item__title').text
                        price_text = listing.find_element(By.CSS_SELECTOR, 'div.listing-search-item__price').text
                        url = listing.find_element(By.CSS_SELECTOR, 'a.listing-search-item__link--title').get_attribute('href')

                        try:
                            address = listing.find_element(By.CSS_SELECTOR, 'div.listing-search-item__sub-title').text
                        except:
                            address = None

                        # Get specifications
                        try:
                            specs_elems = listing.find_elements(By.CSS_SELECTOR, 'ul.illustrated-features__list li')
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
                            listing_data = {
                                'title': title,
                                'price': price,
                                'price_text': price_text,
                                'url': url,
                                'address': address,
                                'bedrooms': bedrooms,
                                'area': area,
                                'specs': specs_str,
                                'date_found': datetime.now(),
                                'subscription_id': None  # No specific subscription yet
                            }

                            all_listings.append(listing_data)

                            # Check if this is a new listing
                            if url not in existing_urls:
                                new_listings.append(listing_data)
                                logger.info(f"Found new listing: {title} - {price_text}")

                    except Exception as e:
                        logger.error(f"Error processing listing: {str(e)}")
                        continue

                # Find the next page link if it exists
                try:
                    next_page = driver.find_element(By.CSS_SELECTOR, 'a[rel="next"]')
                    current_url = next_page.get_attribute('href')
                    page_num += 1
                except:
                    logger.info("No next page found, ending scrape")
                    current_url = None

            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {str(e)}")
                logger.error(traceback.format_exc())
                current_url = None

        # Save new listings to database
        new_listing_objects = []
        for data in new_listings:
            try:
                # Double-check URL is not in database
                if data['url'] in existing_urls:
                    continue

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
                    date_found=data['date_found']
                )

                db.session.add(listing_obj)
                db.session.flush()  # Get the ID without committing
                existing_urls.add(data['url'])  # Update set to prevent duplicates
                new_listing_objects.append(listing_obj)

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding listing to database: {str(e)}")
                continue

        # Commit all new listings
        if new_listing_objects:
            try:
                db.session.commit()
                logger.info(f"Added {len(new_listing_objects)} new listings to database")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error committing new listings: {str(e)}")

        # Match new listings with subscriptions and send notifications
        if new_listing_objects:
            match_listings_to_subscriptions(new_listing_objects)

        return True, len(all_listings), len(new_listing_objects)

    except Exception as e:
        logger.error(f"Error in Eindhoven scraper: {str(e)}")
        logger.error(traceback.format_exc())
        return False, 0, 0

    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

# Update match_listings_to_subscriptions function in app/scraper/utils.py
def match_listings_to_subscriptions(new_listings):
    """Match new listings with active subscriptions and send notifications"""
    if not new_listings:
        logger.info("No new listings to match")
        return

    logger.info(f"Matching {len(new_listings)} new listings to subscriptions")

    # Group listings by city
    listings_by_city = {}
    for listing in new_listings:
        if listing.city_id not in listings_by_city:
            listings_by_city[listing.city_id] = []
        listings_by_city[listing.city_id].append(listing)

    # For each city, get active subscriptions and match
    for city_id, city_listings in listings_by_city.items():
        # Get all active subscriptions for this city
        active_subscriptions = Subscription.query.filter_by(active=True, city_id=city_id).all()
        logger.info(f"Found {len(active_subscriptions)} active subscriptions for city {city_id}")

        # Group subscriptions by user
        user_subscriptions = {}
        for sub in active_subscriptions:
            if sub.user_id not in user_subscriptions:
                user_subscriptions[sub.user_id] = {
                    'user': sub.user,
                    'matched_listings': [],
                    'subscriptions': []
                }
            user_subscriptions[sub.user_id]['subscriptions'].append(sub)

        # Match listings to subscriptions
        for listing in city_listings:
            for user_id, data in user_subscriptions.items():
                for sub in data['subscriptions']:
                    # Check if listing matches subscription criteria
                    if (listing.price >= sub.min_price and
                        listing.price <= sub.max_price and
                        (listing.bedrooms is None or  # If bedrooms unknown, include it
                         (listing.bedrooms >= sub.min_bedrooms and
                          listing.bedrooms <= sub.max_bedrooms))):

                        # Add to user's matched listings if not already there
                        if listing not in data['matched_listings']:
                            data['matched_listings'].append(listing)

        # Send notifications to users with matched listings
        for user_id, data in user_subscriptions.items():
            if data['matched_listings']:
                user = data['user']
                listings = data['matched_listings']
                city_name = City.query.get(city_id).name  # Get city name
                logger.info(f"Sending notification to {user.email} with {len(listings)} matched listings for {city_name}")
                send_email_notification(user.email, listings, city_name)

                # Mark listings as notified
                for listing in listings:
                    listing.notified = True

                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error marking listings as notified: {str(e)}")


def send_email_notification(user_email, new_listings, city_name=None):
    """Send email notification about new listings."""
    if not new_listings:
        logger.warning(f"No new listings to send to {user_email}")
        return False

    # If no city_name provided, try to get it from the first listing
    if not city_name and new_listings and hasattr(new_listings[0], 'city') and new_listings[0].city:
        city_name = new_listings[0].city.name
    elif not city_name:
        city_name = "Eindhoven"  # Default fallback

    logger.info(f"Preparing email with {len(new_listings)} new listings for {user_email} in {city_name}")

    config = current_app.config
    sender = config.get('MAIL_USERNAME')
    password = config.get('MAIL_PASSWORD')

    if not sender or not password:
        logger.error("Email credentials not configured properly")
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = user_email
    msg['Subject'] = f"🏠 New Apartments Found in {city_name} - {datetime.now().strftime('%d %B %Y')}"

    # Create both plain text and HTML versions
    text_body = f"New listings found in {city_name} matching your criteria:\n\n"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
            }}
            .header {{
                background-color: #2c5282;
                color: white;
                padding: 15px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }}
            .listing {{
                margin-bottom: 20px;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f9f9f9;
            }}
            .title {{
                color: #2c5282;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .price {{
                color: #38a169;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
            }}
            .specs {{
                color: #4a5568;
                margin-bottom: 8px;
            }}
            .features {{
                color: #4a5568;
                margin-bottom: 8px;
            }}
            .address {{
                color: #718096;
                font-style: italic;
                margin-bottom: 8px;
            }}
            .link-button {{
                display: inline-block;
                background-color: #3182ce;
                color: white;
                padding: 8px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 10px;
            }}
            .footer {{
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }}
            .date {{
                color: #718096;
                font-size: 14px;
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🏠 New Apartments Found in {city_name}</h2>
        </div>
    """

    for listing in new_listings:
        # Plain text version
        text_body += f"📍 {listing.title}\n"
        text_body += f"💶 {listing.price_text}\n"
        if listing.address:
            text_body += f"🏠 {listing.address}\n"
        if listing.bedrooms:
            text_body += f"🛏️ {listing.bedrooms} bedrooms\n"
        if listing.area:
            text_body += f"📏 {listing.area} m²\n"
        if listing.specs:
            text_body += f"ℹ️ {listing.specs}\n"
        text_body += f"🔎 Found: {listing.date_found.strftime('%Y-%m-%d %H:%M')}\n"
        text_body += f"🔗 {listing.url}\n"
        text_body += "-" * 50 + "\n"

        # HTML version
        html_body += f"""
        <div class="listing">
            <div class="title">📍 {listing.title}</div>
            <div class="price">💶 {listing.price_text}</div>
            <div class="date">🔎 Found: {listing.date_found.strftime('%Y-%m-%d %H:%M')}</div>
        """
        if listing.address:
            html_body += f'<div class="address">🏠 {listing.address}</div>'

        features_html = ""
        if listing.bedrooms:
            features_html += f"🛏️ {listing.bedrooms} bedrooms"
        if listing.area:
            if features_html:
                features_html += " | "
            features_html += f"📏 {listing.area} m²"

        if features_html:
            html_body += f'<div class="features">{features_html}</div>'

        if listing.specs:
            html_body += f'<div class="specs">ℹ️ {listing.specs}</div>'

        html_body += f'<a href="{listing.url}" class="link-button">View Property 🔗</a>'
        html_body += '</div>'

    html_body += """
        <div class="footer">
            <p>This is an automated message from your Apartment Finder.<br>
            New listings will be sent as they match your subscription criteria.</p>
        </div>
    </body>
    </html>
    """

    # Attach both versions to the email
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email notification sent successfully to {user_email}!")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def test_email_notification(subscription_id):
    """Create a test listing and send a test email notification."""
    try:
        subscription = Subscription.query.get(subscription_id)
        if not subscription or not subscription.active:
            logger.info(f"Subscription {subscription_id} is not active or does not exist.")
            return False

        user_email = subscription.user.email

        # Create a test listing that won't be saved to the database
        test_listing = Listing(
            title="TEST LISTING - Please ignore",
            price=1500,
            price_text="€1,500 per month",
            url="https://www.pararius.com/test-listing",
            address="Test Street 123, Eindhoven",
            bedrooms=2,
            area=80,
            specs="80m², 2 rooms, 1 bathroom",
            date_found=datetime.now(),
            subscription_id=subscription.id
        )

        # Send test email with just this one listing
        result = send_email_notification(user_email, [test_listing])

        return result
    except Exception as e:
        logger.error(f"Error in test_email_notification: {str(e)}")
        return False

def run_scraper_for_city(city):
    """Run the appropriate scraper for the given city."""
    from app.scraper.factory import ScraperFactory

    scraper = ScraperFactory.get_scraper(city)
    return scraper.scrape()