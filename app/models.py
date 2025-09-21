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
    callsheet_entries = db.relationship('CallsheetEntry', backref='entered_by', lazy=True)
    callsheets_created = db.relationship('Callsheet', backref='created_by_user', lazy=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    contact_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)
    callsheet_entries = db.relationship('CallsheetEntry', backref='customer', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_number': self.account_number,
            'name': self.name,
            'contact_name': self.contact_name,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'notes': self.notes
        }

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

class Callsheet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday-Friday only
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    entries = db.relationship('CallsheetEntry', backref='callsheet', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Callsheet {self.name} - {self.day_of_week}>'

class CallsheetEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    callsheet_id = db.Column(db.Integer, db.ForeignKey('callsheet.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    
    # Call status: 'not_called', 'no_answer', 'declined', 'ordered', 'callback'
    call_status = db.Column(db.String(20), default='not_called')
    
    # Track who made the call (automatically set from logged-in user)
    called_by = db.Column(db.String(100))  
    call_date = db.Column(db.DateTime)
    
    # Order information - simplified
    person_spoken_to = db.Column(db.String(100))  # Name of person who placed the order
    
    # Notes for this specific call
    call_notes = db.Column(db.Text)
    
    # Callback information
    callback_time = db.Column(db.String(50))  # When to call back
    
    # Tracking
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Position in the callsheet (for ordering)
    position = db.Column(db.Integer, default=0)
    
    def get_status_badge(self):
        """Return HTML badge class for status"""
        status_badges = {
            'not_called': 'secondary',
            'no_answer': 'warning',
            'declined': 'danger',
            'ordered': 'success',
            'callback': 'info'
        }
        return status_badges.get(self.call_status, 'secondary')
    
    def get_status_display(self):
        """Return display text for status"""
        status_display = {
            'not_called': 'Not Called',
            'no_answer': 'No Answer',
            'declined': 'Declined',
            'ordered': 'Ordered',
            'callback': 'Callback'
        }
        return status_display.get(self.call_status, 'Not Called')

class CallsheetArchive(db.Model):
    """Store archived callsheet data for historical viewing"""
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Text, nullable=False)  # JSON string
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    archived_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    archived_by_user = db.relationship('User', backref='archived_callsheets')

class Form(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)