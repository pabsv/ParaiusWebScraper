from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
import logging
import atexit

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
scheduler = BackgroundScheduler()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import and register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Import models to ensure they're known to Flask-Migrate
    from app import models
    
    # Register a function to set up the scheduler after the first request
    with app.app_context():
        from app.tasks import setup_scheduler
        setup_scheduler(app)
    
    # Start the scheduler
    if not scheduler.running:
        scheduler.start()
        # Make sure scheduler shuts down when app exits
        atexit.register(lambda: scheduler.shutdown())
    
    # Add a route to manually trigger the scheduler for testing
    @app.route('/run_scheduler')
    def run_scheduled_task():
        from app.tasks import check_all_subscriptions
        with app.app_context():
            result = check_all_subscriptions()
        return f"Scheduled task executed: {result}"
    
    return app