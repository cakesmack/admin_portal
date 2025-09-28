from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)  # Keep for system use
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)  # Primary identifier
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Changed from 'password' to 'password_hash'
    role = db.Column(db.String(20), nullable=False)
    
    # New fields for user management
    job_title = db.Column(db.String(100))
    direct_phone = db.Column(db.String(20))
    mobile_phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Existing relationships...
    forms = db.relationship('Form', foreign_keys='Form.user_id', backref='author', lazy=True)
    callsheet_entries = db.relationship('CallsheetEntry', backref='entered_by', lazy=True)
    callsheets_created = db.relationship('Callsheet', backref='created_by_user', lazy=True)
    todo_items = db.relationship('TodoItem', backref='user', lazy=True, cascade='all, delete-orphan')
    company_updates = db.relationship('CompanyUpdate', backref='author', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash from plain password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        if not self.password_hash:
            # Handle case where password_hash is None or empty
            print(f"Warning: User {self.username} has no password hash")
            return False
        
        try:
            return check_password_hash(self.password_hash, password)
        except (ValueError, AttributeError) as e:
            print(f"Error checking password for user {self.username}: {e}")
            return False
    
    def generate_temp_password(self):
        """Generate a secure temporary password"""
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = ''.join(secrets.choice(chars) for _ in range(12))
        return temp_password
    
    # Replace the get_recent_activity method in your User model (app/models.py)

    def get_recent_activity(self, limit=10):
        activities = []
        
        try:
            # Recent forms created by this user
            recent_forms = Form.query.filter_by(user_id=self.id).order_by(Form.date_created.desc()).limit(5).all()
            for form in recent_forms:
                activities.append({
                    'type': 'form_created',
                    'description': f'Created {form.type.replace("_", " ").title()} form',
                    'date': form.date_created,
                    'link': f'/form/{form.id}'
                })
        except Exception as e:
            print(f"Error loading forms for user {self.id}: {e}")
        
        try:
            # Recent company updates by this user
            recent_updates = CompanyUpdate.query.filter_by(user_id=self.id).order_by(CompanyUpdate.created_at.desc()).limit(3).all()
            for update in recent_updates:
                activities.append({
                    'type': 'company_update',
                    'description': f'Posted company update: {update.title}',
                    'date': update.created_at,
                    'link': None
                })
        except Exception as e:
            print(f"Error loading company updates for user {self.id}: {e}")
        
        try:
            # Recent callsheet activity by this user
            # Note: Fixed the relationship issue by using proper query
            recent_callsheet_entries = CallsheetEntry.query.filter_by(user_id=self.id).order_by(CallsheetEntry.updated_at.desc()).limit(3).all()
            for entry in recent_callsheet_entries:
                activities.append({
                    'type': 'callsheet_update',
                    'description': f'Updated callsheet entry for {entry.customer.name}',
                    'date': entry.updated_at,
                    'link': '/callsheets'
                })
        except Exception as e:
            print(f"Error loading callsheet entries for user {self.id}: {e}")
        
        try:
            # Recent forms completed by this user
            recent_completed_forms = Form.query.filter_by(completed_by=self.id).filter(
                Form.completed_date.isnot(None)
            ).order_by(Form.completed_date.desc()).limit(3).all()
            
            for form in recent_completed_forms:
                activities.append({
                    'type': 'form_completed',
                    'description': f'Completed {form.type.replace("_", " ").title()} form',
                    'date': form.completed_date,
                    'link': f'/form/{form.id}'
                })
        except Exception as e:
            print(f"Error loading completed forms for user {self.id}: {e}")
        
        # Try to load standing order activities if the models exist
        try:
            # Recent standing order creation
            if 'StandingOrder' in globals():
                recent_standing_orders = StandingOrder.query.filter_by(created_by=self.id).order_by(StandingOrder.created_at.desc()).limit(3).all()
                for order in recent_standing_orders:
                    activities.append({
                        'type': 'standing_order_created',
                        'description': f'Created standing order for {order.customer.name}',
                        'date': order.created_at,
                        'link': f'/standing-orders/{order.id}'
                    })
        except Exception as e:
            print(f"Error loading standing orders for user {self.id}: {e}")
        
        try:
            # Recent standing order actions if the models exist
            if 'StandingOrderLog' in globals():
                recent_so_logs = StandingOrderLog.query.filter_by(performed_by=self.id).filter(
                    StandingOrderLog.action_type.in_(['paused', 'resumed', 'ended'])
                ).order_by(StandingOrderLog.performed_at.desc()).limit(3).all()
                
                for log in recent_so_logs:
                    action_descriptions = {
                        'paused': f'Paused standing order for {log.standing_order.customer.name}',
                        'resumed': f'Resumed standing order for {log.standing_order.customer.name}',
                        'ended': f'Ended standing order for {log.standing_order.customer.name}'
                    }
                    
                    activities.append({
                        'type': f'standing_order_{log.action_type}',
                        'description': action_descriptions.get(log.action_type, f'{log.action_type.title()} standing order'),
                        'date': log.performed_at,
                        'link': f'/standing-orders/{log.standing_order_id}'
                    })
        except Exception as e:
            print(f"Error loading standing order logs for user {self.id}: {e}")
        
        try:
            # Recent stock transactions if the models exist
            if 'StockTransaction' in globals():
                recent_stock_transactions = StockTransaction.query.filter_by(created_by=self.id).order_by(StockTransaction.transaction_date.desc()).limit(3).all()
                for transaction in recent_stock_transactions:
                    transaction_types = {
                        'stock_in': 'Added stock for',
                        'stock_out': 'Processed stock order for', 
                        'adjustment': 'Adjusted stock for'
                    }
                    
                    description = transaction_types.get(transaction.transaction_type, 'Updated stock for')
                    activities.append({
                        'type': f'stock_{transaction.transaction_type}',
                        'description': f'{description} {transaction.stock_item.customer.name}',
                        'date': transaction.transaction_date,
                        'link': '/customer-stock'
                    })
        except Exception as e:
            print(f"Error loading stock transactions for user {self.id}: {e}")
        
        # Sort by date and return limited results
        activities.sort(key=lambda x: x['date'], reverse=True)
        return activities[:limit]

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
    category = db.Column(db.String(50), default='general')



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
    
    # New fields for completion tracking
    is_completed = db.Column(db.Boolean, default=False)
    completed_date = db.Column(db.DateTime, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_archived = db.Column(db.Boolean, default=False)
    
    # Define the completer relationship separately
    completer = db.relationship('User', foreign_keys=[completed_by], backref='completed_forms')

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

# Add these models to your app/models.py

class StandingOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    
    # Weekly delivery schedule (store as comma-separated day numbers: 0=Monday, 6=Sunday)
    delivery_days = db.Column(db.String(20), nullable=False)  # e.g., "0,3" for Monday & Thursday
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)  # Null means ongoing
    
    status = db.Column(db.String(20), default='active')  # active, paused, ended
    
    # Special instructions for this standing order
    special_instructions = db.Column(db.Text)
    

    # Tracking
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = db.relationship('Customer', backref='standing_orders')
    created_by_user = db.relationship('User', backref='created_standing_orders')
    items = db.relationship('StandingOrderItem', backref='standing_order', cascade='all, delete-orphan')
    schedules = db.relationship('StandingOrderSchedule', backref='standing_order', cascade='all, delete-orphan')
    logs = db.relationship('StandingOrderLog', backref='standing_order', cascade='all, delete-orphan')
    
    # Add these methods to your StandingOrder model in models.py

    def get_delivery_days_list(self):
        """Return list of day numbers (excluding weekends)"""
        if self.delivery_days:
            days = [int(d) for d in self.delivery_days.split(',')]
            # Filter out weekends (5=Saturday, 6=Sunday)
            return [d for d in days if d < 5]
        return []

    def get_delivery_days_names(self):
        """Return readable day names (weekdays only)"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day_numbers = self.get_delivery_days_list()
        return [days[d] for d in day_numbers if d < 5]

    def validate_delivery_days(self):
        """Validate that only weekdays are selected"""
        day_numbers = self.get_delivery_days_list()
        weekend_days = [d for d in day_numbers if d >= 5]
        if weekend_days:
            raise ValueError("Weekend deliveries are not supported. Please select Monday through Friday only.")

class StandingOrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    standing_order_id = db.Column(db.Integer, db.ForeignKey('standing_order.id'), nullable=False)
    
    product_code = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_type = db.Column(db.String(20), default='units')  # units, cases, boxes, etc.
    
    special_notes = db.Column(db.Text)  # Item-specific notes
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class StandingOrderSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    standing_order_id = db.Column(db.Integer, db.ForeignKey('standing_order.id'), nullable=False)
    
    scheduled_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, created, skipped
    
    # Track when the actual order was created
    order_created_date = db.Column(db.DateTime, nullable=True)
    order_created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Optional order reference from main system
    order_reference = db.Column(db.String(50))
    
    notes = db.Column(db.Text)
    
    # Relationships
    created_by_user = db.relationship('User', backref='created_orders_from_standing')
    
    # Unique constraint to prevent duplicate schedules
    __table_args__ = (db.UniqueConstraint('standing_order_id', 'scheduled_date'),)

class StandingOrderLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    standing_order_id = db.Column(db.Integer, db.ForeignKey('standing_order.id'), nullable=False)
    
    action_type = db.Column(db.String(50), nullable=False)  # created, modified, paused, resumed, ended, item_added, item_removed, etc.
    action_details = db.Column(db.Text)  # JSON string with details of the change
    
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    performed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='standing_order_actions')