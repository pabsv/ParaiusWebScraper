#routes.py
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from app import db
from app.models import User, Subscription, Listing, City  # Add City
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField, SelectField  # Add SelectField
from wtforms.validators import DataRequired, Email, Optional

main_bp = Blueprint('main', __name__)

@main_bp.before_request
def before_request():
    g.now = datetime.now()

class SubscriptionForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    city_id = SelectField('City', coerce=int, validators=[DataRequired()])
    min_price = HiddenField('Min Price', default='0')
    max_price = HiddenField('Max Price', default='3000')
    min_bedrooms = HiddenField('Min Bedrooms', default='1')
    max_bedrooms = HiddenField('Max Bedrooms', default='5')
    submit = SubmitField('Subscribe')

    def __init__(self, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        # Populate city choices - we'll set these in the route
        self.city_id.choices = []

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    form = SubscriptionForm()
    # Set the city choices
    form.city_id.choices = [(c.id, c.name) for c in City.query.filter_by(active=True).all()]

    if form.validate_on_submit():
        # Check if user exists, create if not
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            user = User(email=form.email.data)
            db.session.add(user)

        # Prepare subscription parameters
        try:
            min_price = max(0, int(form.min_price.data or 0))
            max_price = min(10000, int(form.max_price.data or 3000))
            min_bedrooms = max(0, int(form.min_bedrooms.data or 0))
            max_bedrooms = min(10, int(form.max_bedrooms.data or 5))
            city_id = int(form.city_id.data)

            # Validate city exists
            city = City.query.get(city_id)
            if not city:
                flash('Invalid city selected', 'danger')
                return redirect(url_for('main.index'))

        except ValueError:
            flash('Invalid input values', 'danger')
            return redirect(url_for('main.index'))

        # Check if this subscription already exists
        existing_sub = Subscription.query.filter_by(
            user_id=user.id,
            city_id=city_id,
            min_price=min_price,
            max_price=max_price,
            min_bedrooms=min_bedrooms,
            max_bedrooms=max_bedrooms
        ).first()

        if existing_sub:
            if not existing_sub.active:
                existing_sub.active = True
                db.session.commit()
                flash(f'Your subscription for {city.name} has been reactivated!', 'success')
            else:
                flash(f'You are already subscribed to {city.name} with these criteria!', 'info')
        else:
            # Create new subscription
            subscription = Subscription(
                min_price=min_price,
                max_price=max_price,
                min_bedrooms=min_bedrooms,
                max_bedrooms=max_bedrooms,
                city_id=city_id,
                user=user
            )
            db.session.add(subscription)
            db.session.commit()
            flash(f'Subscription added for {city.name}! You will receive emails when new listings match your criteria.', 'success')

        return redirect(url_for('main.index'))

    return render_template('index.html', form=form)

# app/routes.py
@main_bp.route('/subscriptions')
def subscriptions():
    email = request.args.get('email', '')
    if not email:
        return render_template('subscriptions.html', subscriptions=None)

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No subscriptions found for this email.', 'info')
        return render_template('subscriptions.html', subscriptions=None)

    # Add City to the template context
    return render_template('subscriptions.html', subscriptions=user.subscriptions,
                          email=email, City=City)

@main_bp.route('/unsubscribe/<int:sub_id>')
def unsubscribe(sub_id):
    subscription = Subscription.query.get_or_404(sub_id)
    email = subscription.user.email

    subscription.active = False
    db.session.commit()
    flash('Subscription deactivated successfully.', 'success')

    return redirect(url_for('main.subscriptions', email=email))

@main_bp.route('/reactivate/<int:sub_id>')
def reactivate(sub_id):
    subscription = Subscription.query.get_or_404(sub_id)
    email = subscription.user.email

    subscription.active = True
    db.session.commit()
    flash('Subscription reactivated successfully.', 'success')

    return redirect(url_for('main.subscriptions', email=email))

@main_bp.route('/test_email/<int:sub_id>')
def test_email(sub_id):
    from app.scraper.utils import test_email_notification
    result = test_email_notification(sub_id)

    if result:
        flash('Test email sent successfully! Check your inbox.', 'success')
    else:
        flash('Failed to send test email. Check the logs for more information.', 'danger')

    return redirect(url_for('main.subscriptions', email=request.args.get('email', '')))

@main_bp.route('/browse_listings')
def browse_listings():
    page = request.args.get('page', 1, type=int)
    min_price = request.args.get('min_price', 0, type=int)
    max_price = request.args.get('max_price', 10000, type=int)
    min_bedrooms = request.args.get('min_bedrooms', 0, type=int)
    max_bedrooms = request.args.get('max_bedrooms', 10, type=int)

    query = Listing.query

    if min_price > 0:
        query = query.filter(Listing.price >= min_price)
    if max_price < 10000:
        query = query.filter(Listing.price <= max_price)
    if min_bedrooms > 0:
        query = query.filter(Listing.bedrooms >= min_bedrooms)
    if max_bedrooms < 10:
        query = query.filter(Listing.bedrooms <= max_bedrooms)

    listings = query.order_by(Listing.date_found.desc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('listings.html', listings=listings,
                          min_price=min_price, max_price=max_price,
                          min_bedrooms=min_bedrooms, max_bedrooms=max_bedrooms)

@main_bp.route('/test_scraper/<int:city_id>')
def test_scraper_city(city_id):
    from app.tasks import check_city
    result = check_city(city_id)

    if "Error" not in result:
        flash(f'Successfully ran the scraper! {result}', 'success')
    else:
        flash(f'Failed to run the scraper: {result}', 'danger')

    return redirect(url_for('main.index'))

@main_bp.route('/test_scraper')
def test_scraper():
    from app.tasks import check_all_cities
    results = check_all_cities()

    success = all(["Error" not in result for result in results.values()])

    if success:
        flash_message = 'Successfully ran scrapers for all cities! Results:'
        for city, result in results.items():
            flash_message += f'<br>• {city}: {result}'
        flash(flash_message, 'success')
    else:
        flash_message = 'Some scrapers failed. Results:'
        for city, result in results.items():
            flash_message += f'<br>• {city}: {result}'
        flash(flash_message, 'danger')

    return redirect(url_for('main.index'))

@main_bp.route('/edit_subscription/<int:sub_id>', methods=['GET', 'POST'])
def edit_subscription(sub_id):
    subscription = Subscription.query.get_or_404(sub_id)
    email = subscription.user.email

    # Create form and populate it with the subscription's current values
    form = SubscriptionForm()
    form.city_id.choices = [(c.id, c.name) for c in City.query.filter_by(active=True).all()]

    if form.validate_on_submit():
        try:
            # Update subscription with new values
            subscription.min_price = max(0, int(form.min_price.data or 0))
            subscription.max_price = min(10000, int(form.max_price.data or 3000))
            subscription.min_bedrooms = max(0, int(form.min_bedrooms.data or 0))
            subscription.max_bedrooms = min(10, int(form.max_bedrooms.data or 5))
            subscription.city_id = int(form.city_id.data)
            subscription.active = True  # Ensure it's active

            db.session.commit()
            flash('Subscription updated successfully!', 'success')
            return redirect(url_for('main.subscriptions', email=email))

        except ValueError:
            flash('Invalid input values', 'danger')
            return redirect(url_for('main.edit_subscription', sub_id=sub_id))

    elif request.method == 'GET':
        # Populate form with existing subscription data
        form.email.data = email
        form.city_id.data = subscription.city_id
        form.min_price.data = subscription.min_price
        form.max_price.data = subscription.max_price
        form.min_bedrooms.data = subscription.min_bedrooms
        form.max_bedrooms.data = subscription.max_bedrooms

    return render_template('edit_subscription.html', form=form, subscription=subscription)