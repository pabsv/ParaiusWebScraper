#routes.py
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from app import db
from app.models import User, Subscription
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email, URL

main_bp = Blueprint('main', __name__)

@main_bp.before_request
def before_request():
    g.now = datetime.now()

class SubscriptionForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    url = StringField('Pararius URL', validators=[DataRequired(), URL()])
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
        
        # Check if this subscription already exists
        existing_sub = Subscription.query.filter_by(
            user_id=user.id, 
            url=form.url.data
        ).first()
        
        if existing_sub:
            if not existing_sub.active:
                existing_sub.active = True
                db.session.commit()
                flash('Your subscription has been reactivated!', 'success')
            else:
                flash('You are already subscribed to this search!', 'info')
        else:
            # Create new subscription
            subscription = Subscription(url=form.url.data, user=user)
            db.session.add(subscription)
            db.session.commit()
            flash('Subscription added successfully! You will receive emails when new listings are found.', 'success')
        
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

@main_bp.route('/test_scraper/<int:sub_id>')
def test_scraper(sub_id):
    from app.tasks import run_manual_check
    result = run_manual_check(sub_id)
    
    if result:
        flash('Successfully ran the scraper! Check your email for any new listings.', 'success')
    else:
        flash('Failed to run the scraper.', 'danger')
    
    return redirect(url_for('main.subscriptions'))

@main_bp.route('/test_email/<int:sub_id>')
def test_email(sub_id):
    from app.scraper.utils import test_email_notification
    result = test_email_notification(sub_id)
    
    if result:
        flash('Test email sent successfully! Check your inbox.', 'success')
    else:
        flash('Failed to send test email. Check the logs for more information.', 'danger')
    
    return redirect(url_for('main.subscriptions', email=request.args.get('email', '')))