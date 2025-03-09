# init_db.py
import os
import glob
from app import create_app, db
from app.models import City

def initialize_database():
    app = create_app()

    with app.app_context():
        # First, drop all tables if they exist
        print("Dropping all tables...")
        db.drop_all()

        # Create all tables
        print("Creating all tables...")
        db.create_all()

        # Add cities
        print("Adding cities...")
        eindhoven = City(
            name='Eindhoven',
            url_name='eindhoven',
            base_url='https://www.pararius.com/apartments/eindhoven',
            active=True
        )

        rotterdam = City(
            name='Rotterdam',
            url_name='rotterdam',
            base_url='https://www.pararius.com/apartments/rotterdam',
            active=True
        )

        db.session.add(eindhoven)
        db.session.add(rotterdam)

        db.session.commit()
        print("Cities added successfully!")

        # Verify cities were added
        cities = City.query.all()
        print(f"Verification - Found {len(cities)} cities in the database:")
        for city in cities:
            print(f"  - {city.name} (URL: {city.base_url})")

        print("\nDatabase initialization complete! You can now start your Flask app.")

if __name__ == "__main__":
    initialize_database()