import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app import db
from app.models import Listing, Subscription, User
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

def send_email_notification(user_email, new_listings):
    """Send email notification about new listings."""
    if not new_listings:
        logger.warning(f"No new listings to send to {user_email}")
        return False
        
    logger.info(f"Preparing email with {len(new_listings)} new listings for {user_email}")
    
    config = current_app.config
    sender = config.get('MAIL_USERNAME')
    password = config.get('MAIL_PASSWORD')
    
    if not sender or not password:
        logger.error("Email credentials not configured properly")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = user_email
    msg['Subject'] = f"🏠 New Apartments Found - {datetime.now().strftime('%d %B %Y')}"

    # Create both plain text and HTML versions
    text_body = "New listings found:\n\n"
    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
            }
            .header {
                background-color: #2c5282;
                color: white;
                padding: 15px;
                border-radius: 8px 8px 0 0;
                text-align: center;
            }
            .listing {
                margin-bottom: 20px;
                padding: 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #f9f9f9;
            }
            .title {
                color: #2c5282;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .price {
                color: #38a169;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 8px;
            }
            .specs {
                color: #4a5568;
                margin-bottom: 8px;
            }
            .address {
                color: #718096;
                font-style: italic;
                margin-bottom: 8px;
            }
            .link-button {
                display: inline-block;
                background-color: #3182ce;
                color: white;
                padding: 8px 15px;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 10px;
            }
            .footer {
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
            }
            .date {
                color: #718096;
                font-size: 14px;
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h2>🏠 New Apartments Found</h2>
        </div>
    """

    for listing in new_listings:
        # Plain text version
        text_body += f"📍 {listing.title}\n"
        text_body += f"💶 {listing.price}\n"
        if listing.address:
            text_body += f"🏠 {listing.address}\n"
        if listing.specs:
            text_body += f"ℹ️ {listing.specs}\n"
        text_body += f"🔎 Found: {listing.date_found.strftime('%Y-%m-%d %H:%M')}\n"
        text_body += f"🔗 {listing.url}\n"
        text_body += "-" * 50 + "\n"

        # HTML version
        html_body += f"""
        <div class="listing">
            <div class="title">📍 {listing.title}</div>
            <div class="price">💶 {listing.price}</div>
            <div class="date">🔎 Found: {listing.date_found.strftime('%Y-%m-%d %H:%M')}</div>
        """
        if listing.address:
            html_body += f'<div class="address">🏠 {listing.address}</div>'
        if listing.specs:
            html_body += f'<div class="specs">ℹ️ {listing.specs}</div>'
        
        html_body += f'<a href="{listing.url}" class="link-button">View Property 🔗</a>'
        html_body += '</div>'

    html_body += """
        <div class="footer">
            <p>This is an automated message from your Pararius Apartment Finder.<br>
            New listings will be sent as they become available.</p>
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
def run_spider_for_subscription(subscription_id):
    """Run spider for a specific subscription using direct Selenium approach without Scrapy."""
    try:
        # Get subscription details
        subscription = Subscription.query.get(subscription_id)
        if not subscription or not subscription.active:
            logger.info(f"Subscription {subscription_id} is not active or does not exist.")
            return False
        
        logger.info(f"Running scraper for subscription {subscription_id} ({subscription.url})")
        
        # Get existing listing URLs for this subscription
        existing_urls = set([listing.url for listing in subscription.listings])
        
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
            
            # Navigate to the URL
            driver.get(subscription.url)
            logger.info(f"Navigated to {subscription.url}")
            
            # Wait for the listings to load
            wait = WebDriverWait(driver, 10)
            listings = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.search-list__item--listing')))
            
            logger.info(f"Found {len(listings)} total listings")
            
            new_listings = []
            new_listings_data = []
            
            for listing in listings:
                try:
                    # Extract listing details
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
                    
                    if all([title, price, url]) and url not in existing_urls:
                        # Store listing data first, add to database later
                        new_listings_data.append({
                            'title': title,
                            'price': price,
                            'url': url,
                            'address': address,
                            'specs': specs_str,
                            'date_found': datetime.now(),
                            'subscription_id': subscription_id
                        })
                        logger.info(f"Found new listing: {title} - {price}")
                except Exception as e:
                    logger.error(f"Error processing listing: {str(e)}")
                    continue
            
            # Now add all listings to the database with proper error handling
            for data in new_listings_data:
                try:
                    # Check if URL already exists in database (double-check)
                    existing_listing = Listing.query.filter_by(url=data['url']).first()
                    if existing_listing:
                        logger.info(f"Listing with URL {data['url']} already exists in database.")
                        continue
                        
                    # Create new listing in database
                    listing_obj = Listing(
                        title=data['title'],
                        price=data['price'],
                        url=data['url'],
                        address=data['address'],
                        specs=data['specs'],
                        date_found=data['date_found'],
                        subscription_id=data['subscription_id']
                    )
                    db.session.add(listing_obj)
                    db.session.commit()  # Commit each listing individually to avoid losing all on error
                    new_listings.append(listing_obj)
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error saving listing to database: {str(e)}")
                    continue
            
            if new_listings:
                logger.info(f"Found {len(new_listings)} new listings for subscription {subscription_id}")
                # Send email notification
                user_email = subscription.user.email
                send_email_notification(user_email, new_listings)
                
                # Mark listings as notified
                for listing in new_listings:
                    listing.notified = True
                db.session.commit()
            else:
                logger.info(f"No new listings found for subscription {subscription_id}")
            
            # Update last checked timestamp
            subscription.last_checked = datetime.now()
            db.session.commit()
            
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during scraping: {str(e)}")
            logger.error(traceback.format_exc())
            return False
        finally:
            # Clean up
            if driver:
                driver.quit()
                logger.info("WebDriver closed")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error running scraper for subscription {subscription_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def run_manual_check(subscription_id):
    """Run a manual check for a specific subscription."""
    logger.info(f"Running manual check for subscription {subscription_id}")
    return run_spider_for_subscription(subscription_id)


#Test notificaitons without adding stuff to the database

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
            price="€1,500 per month",
            url="https://www.pararius.com/test-listing",
            address="Test Street 123, Eindhoven",
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