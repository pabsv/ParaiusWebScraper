#models.py
from datetime import datetime
from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscriptions = db.relationship('Subscription', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.email}>'

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_checked = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listings = db.relationship('Listing', backref='subscription', lazy='dynamic')
    
    def __repr__(self):
        return f'<Subscription {self.url}>'

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.String(50), nullable=False)
    url = db.Column(db.String(500), nullable=False, unique=True)
    address = db.Column(db.String(200), nullable=True)
    specs = db.Column(db.Text, nullable=True)
    date_found = db.Column(db.DateTime, default=datetime.utcnow)
    notified = db.Column(db.Boolean, default=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    
    def __repr__(self):
        return f'<Listing {self.title}>'