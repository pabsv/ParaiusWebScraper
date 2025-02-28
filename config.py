#config.py
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-for-development'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smxtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'jeffhouser100@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'xsfh qhcd jeiu uazr'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'jeffhouser100@gmail.com'
    
    # Scraper configuration
    SCRAPER_INTERVAL = int(os.environ.get('SCRAPER_INTERVAL') or 300) # 5 minutes