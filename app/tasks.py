#tasks.py
from app import db, scheduler
from app.models import Subscription
from app.scraper.utils import scrape_eindhoven_apartments
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_scheduler(app):
    """Set up the scheduler with the application context"""
    logger.info("Setting up scheduler...")
    
    # Clear any existing jobs
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)
    
    # Define a function that will run with app context
    def run_check_with_context():
        logger.info("Running scheduled task to scrape Eindhoven listings...")
        with app.app_context():
            run_eindhoven_scraper()
    
    # Schedule the job
    interval = app.config.get('SCRAPER_INTERVAL', 300)  # Default: 5 minutes (300 seconds)
    scheduler.add_job(
        run_check_with_context,
        'interval',
        seconds=interval,
        id='scrape_eindhoven',
        replace_existing=True
    )
    
    logger.info(f"Scheduled task to run every {interval} seconds")

def run_eindhoven_scraper():
    """Run the Eindhoven apartment scraper"""
    logger.info("Starting Eindhoven apartment scraper...")
    
    try:
        success, total_count, new_count = scrape_eindhoven_apartments()
        
        if success:
            logger.info(f"Scraper completed successfully: {total_count} listings found, {new_count} new listings added")
            
            # Update last_checked timestamp for all active subscriptions
            active_subscriptions = Subscription.query.filter_by(active=True).all()
            now = datetime.now()
            
            for subscription in active_subscriptions:
                subscription.last_checked = now
            
            try:
                db.session.commit()
                logger.info(f"Updated last_checked timestamp for {len(active_subscriptions)} active subscriptions")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating subscription timestamps: {str(e)}")
            
            return f"Found {total_count} listings, {new_count} new"
        else:
            logger.error("Scraper failed")
            return "Scraper failed"
    
    except Exception as e:
        logger.error(f"Error in run_eindhoven_scraper: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"