#routes.py
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from app import db
from app.models import User, Subscription, Listing
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange, Optional

main_bp = Blueprint('main', __name__)

@main_bp.before_request
def before_request():
    g.now = datetime.now()

class SubscriptionForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    min_price = IntegerField('Minimum Price (€)', default=0, validators=[NumberRange(min=0, max=10000), Optional()])
    max_price = IntegerField('Maximum Price (€)', default=3000, validators=[NumberRange(min=0, max=10000), Optional()])
    min_bedrooms = IntegerField('Minimum Bedrooms', default=1, validators=[NumberRange(min=0, max=10), Optional()])
    max_bedrooms = IntegerField('Maximum Bedrooms', default=5, validators=[NumberRange(min=0, max=10), Optional()])
    submit = SubmitField('Subscribe')

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    form = SubscriptionForm()
    if form.validate_on_submit():
        # Check if user exists, create if not
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            user = User(email=form.email.data)
            db.session.add(user)
        
        # Prepare subscription parameters
        min_price = max(0, form.min_price.data or 0)
        max_price = min(10000, form.max_price.data or 3000)
        min_bedrooms = max(0, form.min_bedrooms.data or 0)
        max_bedrooms = min(10, form.max_bedrooms.data or 5)
        
        # Check if this subscription already exists
        existing_sub = Subscription.query.filter_by(
            user_id=user.id,
            min_price=min_price,
            max_price=max_price,
            min_bedrooms=min_bedrooms,
            max_bedrooms=max_bedrooms
        ).first()
        
        if existing_sub:
            if not existing_sub.active:
                existing_sub.active = True
                db.session.commit()
                flash('Your subscription has been reactivated!', 'success')
            else:
                flash('You are already subscribed with these criteria!', 'info')
        else:
            # Create new subscription
            subscription = Subscription(
                min_price=min_price,
                max_price=max_price,
                min_bedrooms=min_bedrooms,
                max_bedrooms=max_bedrooms,
                user=user
            )
            db.session.add(subscription)
            db.session.commit()
            flash('Subscription added successfully! You will receive emails when new listings match your criteria.', 'success')
        
        return redirect(url_for('main.index'))
    
    return render_template('index.html', form=form)

@main_bp.route('/subscriptions')
def subscriptions():
    email = request.args.get('email', '')
    if not email:
        return render_template('subscriptions.html', subscriptions=None)
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No subscriptions found for this email.', 'info')
        return render_template('subscriptions.html', subscriptions=None)
    
    return render_template('subscriptions.html', subscriptions=user.subscriptions, email=email)

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

@main_bp.route('/test_scraper')
def test_scraper():
    from app.tasks import run_eindhoven_scraper
    result = run_eindhoven_scraper()
    
    if result:
        flash('Successfully ran the Eindhoven scraper! Check the logs for details.', 'success')
    else:
        flash('Failed to run the scraper.', 'danger')
    
    return redirect(url_for('main.index'))

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