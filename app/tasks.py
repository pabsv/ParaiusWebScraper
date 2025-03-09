# app/tasks.py
from app import db, scheduler
from app.models import Subscription, City
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def setup_scheduler(app):
    """Set up the scheduler with the application context"""
    logger.info("Setting up scheduler...")

    # Clear any existing jobs
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # Define a function that will run with app context
    def run_check_with_context():
        logger.info("Running scheduled task to scrape apartment listings...")
        with app.app_context():
            check_all_cities()

    # Schedule the job
    interval = app.config.get('SCRAPER_INTERVAL', 300)  # Default: 5 minutes
    scheduler.add_job(
        run_check_with_context,
        'interval',
        seconds=interval,
        id='scrape_apartments',
        replace_existing=True
    )

    logger.info(f"Scheduled task to run every {interval} seconds")

def check_all_cities():
    """Run scrapers for all active cities"""
    logger.info("Starting scrapers for all active cities...")

    active_cities = City.query.filter_by(active=True).all()
    logger.info(f"Found {len(active_cities)} active cities")

    results = {}

    for city in active_cities:
        try:
            logger.info(f"Running scraper for {city.name}...")
            from app.scraper.utils import run_scraper_for_city

            success, total_count, new_count = run_scraper_for_city(city)

            if success:
                logger.info(f"{city.name} scraper completed: {total_count} listings found, {new_count} new listings added")
                results[city.name] = f"Found {total_count} listings, {new_count} new"

                # Update last_checked timestamp for all active subscriptions for this city
                active_subscriptions = Subscription.query.filter_by(active=True, city_id=city.id).all()
                now = datetime.now()

                for subscription in active_subscriptions:
                    subscription.last_checked = now

                try:
                    db.session.commit()
                    logger.info(f"Updated last_checked timestamp for {len(active_subscriptions)} active subscriptions")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error updating subscription timestamps: {str(e)}")
            else:
                logger.error(f"{city.name} scraper failed")
                results[city.name] = "Scraper failed"

        except Exception as e:
            logger.error(f"Error in scraper for {city.name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            results[city.name] = f"Error: {str(e)}"

    return results

def check_city(city_id):
    """Run scraper for a specific city"""
    try:
        city = City.query.get(city_id)
        if not city or not city.active:
            logger.error(f"City with ID {city_id} not found or not active")
            return f"City with ID {city_id} not found or not active"

        logger.info(f"Running scraper for {city.name}...")
        from app.scraper.utils import run_scraper_for_city

        success, total_count, new_count = run_scraper_for_city(city)

        if success:
            return f"{city.name}: Found {total_count} listings, {new_count} new"
        else:
            return f"{city.name}: Scraper failed"

    except Exception as e:
        logger.error(f"Error in check_city: {str(e)}")
        return f"Error: {str(e)}"