from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    forms = db.relationship('Form', backref='author', lazy=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    callsheet_entries = db.relationship('CallsheetEntry', backref='customer', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

class CallsheetEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    week_1 = db.Column(db.Boolean, default=False)
    week_2 = db.Column(db.Boolean, default=False)
    week_3 = db.Column(db.Boolean, default=False)
    week_4 = db.Column(db.Boolean, default=False)
    order_placed_by = db.Column(db.String(100))
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)

class Form(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # 'returns', 'branded_stock', etc.
    data = db.Column(db.Text, nullable=False)  # JSON string of form data
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)