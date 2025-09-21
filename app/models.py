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
    todo_items = db.relationship('TodoItem', backref='user', lazy=True, cascade='all, delete-orphan')
    company_updates = db.relationship('CompanyUpdate', backref='author', lazy=True, cascade='all, delete-orphan')

class TodoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class CompanyUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='normal')  # normal, important, urgent
    is_event = db.Column(db.Boolean, default=False)  # True for calendar events
    event_date = db.Column(db.DateTime, nullable=True)  # For events/meetings
    sticky = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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

# Add this to your models.py

class CustomerStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    current_stock = db.Column(db.Integer, nullable=False, default=0)
    unit_type = db.Column(db.String(20), default='cases')  # cases, boxes, units, etc.
    reorder_level = db.Column(db.Integer, default=5)  # Alert when stock gets low
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = db.relationship('Customer', backref=db.backref('stock_items', lazy=True))
    transactions = db.relationship('StockTransaction', backref='stock_item', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': self.customer.name,
            'product_code': self.product_code,
            'product_name': self.product_name,
            'current_stock': self.current_stock,
            'unit_type': self.unit_type,
            'reorder_level': self.reorder_level,
            'is_low_stock': self.current_stock <= self.reorder_level
        }

class StockTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stock_item_id = db.Column(db.Integer, db.ForeignKey('customer_stock.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'stock_in', 'stock_out', 'adjustment'
    quantity = db.Column(db.Integer, nullable=False)
    reference = db.Column(db.String(100))  # Order number, delivery note, etc.
    notes = db.Column(db.Text)
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='stock_transactions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'reference': self.reference,
            'notes': self.notes,
            'transaction_date': self.transaction_date.isoformat(),
            'created_by': self.user.username
        }