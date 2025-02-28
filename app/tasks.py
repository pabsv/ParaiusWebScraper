#tasks.py
from app import db, scheduler
from app.models import Subscription
from app.scraper.utils import run_spider_for_subscription
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
        logger.info("Running scheduled task...")
        with app.app_context():
            check_all_subscriptions()
    
    # Schedule the job
    interval = app.config.get('SCRAPER_INTERVAL', 100)  # Use configured interval
    scheduler.add_job(
        run_check_with_context,
        'interval',
        seconds=interval,
        id='check_subscriptions',
        replace_existing=True
    )
    
    logger.info(f"Scheduled task to run every {interval} seconds")

def check_all_subscriptions():
    """Check all active subscriptions for new listings."""
    logger.info("Checking all active subscriptions for new listings...")
    
    try:
        # Get all active subscriptions
        active_subscriptions = Subscription.query.filter_by(active=True).all()
        logger.info(f"Found {len(active_subscriptions)} active subscriptions")
        
        success_count = 0
        for subscription in active_subscriptions:
            try:
                result = run_spider_for_subscription(subscription.id)
                if result:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error checking subscription {subscription.id}: {str(e)}")
        
        logger.info(f"Finished checking all active subscriptions. Success: {success_count}/{len(active_subscriptions)}")
        return f"Checked {len(active_subscriptions)} subscriptions, {success_count} successful"
    except Exception as e:
        logger.error(f"Error in check_all_subscriptions: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"

def run_manual_check(subscription_id):
    """Run a manual check for a specific subscription."""
    logger.info(f"Running manual check for subscription {subscription_id}")
    return run_spider_for_subscription(subscription_id)