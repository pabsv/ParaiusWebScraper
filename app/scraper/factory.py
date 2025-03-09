# app/scraper/factory.py
from app.scraper.cities.eindhoven import EindhovenScraper
from app.scraper.cities.rotterdam import RotterdamScraper

class ScraperFactory:
    """Factory class to create appropriate scrapers based on city."""

    @staticmethod
    def get_scraper(city):
        """Get the appropriate scraper for the given city."""
        url_name = city.url_name.lower()

        if url_name == 'eindhoven':
            return EindhovenScraper(city)
        elif url_name == 'rotterdam':
            return RotterdamScraper(city)
        else:
            # Default to base scraper if no specific implementation exists
            from app.scraper.base import BaseScraper
            return BaseScraper(city)