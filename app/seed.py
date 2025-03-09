# app/seed.py
from app import db, create_app
from app.models import City

def seed_cities():
    """Seed the database with initial cities."""
    app = create_app()

    with app.app_context():
        # Check if cities already exist
        if City.query.count() > 1:  # Assuming Eindhoven already exists
            print("Cities already seeded.")
            return

        # Add Rotterdam
        rotterdam = City(
            name='Rotterdam',
            url_name='rotterdam',
            base_url='https://www.pararius.com/apartments/rotterdam',
            active=True
        )

        db.session.add(rotterdam)
        db.session.commit()
        print("Added Rotterdam to the database.")

if __name__ == "__main__":
    seed_cities()