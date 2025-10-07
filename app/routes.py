from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Customer, CallsheetEntry, Form, Callsheet, CallsheetArchive, TodoItem, CompanyUpdate, CustomerStock, StockTransaction, StandingOrder, StandingOrderItem, StandingOrderLog, StandingOrderSchedule, Product, CustomerAddress
from app.forms import LoginForm, ReturnsForm, BrandedStockForm, InvoiceCorrectionForm, CreateUserForm, EditUserForm, ChangePasswordForm, ForcePasswordChangeForm
import json
from datetime import datetime, date, timedelta
import calendar
from functools import wraps
import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid
from bs4 import BeautifulSoup
import bleach
from sqlalchemy.orm import joinedload
from sqlalchemy import func


main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB

# Sample data for demonstration
SAMPLE_CUSTOMERS = [
    {'account_number': 'CUST001', 'name': 'Highland Hotel', 'contact_name': 'John Smith', 'phone': '01463 123456'},
    {'account_number': 'CUST002', 'name': 'Lochside Restaurant', 'contact_name': 'Emma Brown', 'phone': '01463 654321'},
    {'account_number': 'CUST003', 'name': 'Cafe Ness', 'contact_name': 'Robert Johnson', 'phone': '01463 789123'},
]

SAMPLE_PRODUCTS = [
    {'code': 'HYG001', 'name': 'Toilet Rolls (12 pack)'},
    {'code': 'HYG002', 'name': 'Hand Soap Refill'},
    {'code': 'CAT001', 'name': 'Disposable Plates'},
    {'code': 'CAT002', 'name': 'Plastic Cutlery Pack'},
]

def validate_company_update(data):
    """Validate company update input"""
    errors = []
    
    # Required fields
    if not data.get('title') or not data.get('title').strip():
        errors.append('Title is required')
    
    if not data.get('message') or not data.get('message').strip():
        errors.append('Message is required')
    
    # Length validation
    if len(str(data.get('title', ''))) > 100:
        errors.append('Title too long (max 100 characters)')
    
    if len(str(data.get('message', ''))) > 5000:
        errors.append('Message too long (max 5000 characters)')
    
    # Validate priority
    if data.get('priority') and data['priority'] not in ['normal', 'important', 'urgent']:
        errors.append('Invalid priority level')
    
    return errors

def validate_customer_data(data):
    """Validate customer input data"""
    errors = []
    
    # Required fields
    if not data.get('account_number') or not data.get('account_number').strip():
        errors.append('Account number is required')
    
    if not data.get('name') or not data.get('name').strip():
        errors.append('Customer name is required')
    
    # Length validation
    if len(str(data.get('account_number', ''))) > 50:
        errors.append('Account number too long (max 50 characters)')
    
    if len(str(data.get('name', ''))) > 100:
        errors.append('Customer name too long (max 100 characters)')
    
    if data.get('contact_name') and len(str(data['contact_name'])) > 100:
        errors.append('Contact name too long (max 100 characters)')
    
    if data.get('phone') and len(str(data['phone'])) > 20:
        errors.append('Phone number too long (max 20 characters)')
    
    if data.get('email') and len(str(data['email'])) > 100:
        errors.append('Email too long (max 100 characters)')
    
    # Email format validation (basic)
    if data.get('email'):
        email = str(data['email']).strip()
        if email and '@' not in email:
            errors.append('Invalid email format')
    
    return errors

def sanitize_html_content(html_content):
    """Sanitize HTML content to prevent XSS attacks - DEBUG VERSION"""
    print(f"  sanitize_html_content called with: '{html_content}' (type: {type(html_content)})")
    
    if html_content is None:
        print("  ERROR: html_content is None!")
        return None
        
    if not isinstance(html_content, str):
        print(f"  ERROR: html_content is not string, it's {type(html_content)}")
        return str(html_content)  # Try to convert
    
    allowed_tags = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'img', 'ol', 'ul', 'li'
    ]
    allowed_attributes = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height', 'style']
    }
    allowed_protocols = ['http', 'https', 'mailto']
    
    try:
        print("  About to call bleach.clean...")
        result = bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        print(f"  bleach.clean result: '{result}' (type: {type(result)})")
        return result
        
    except Exception as e:
        print(f"  ERROR in bleach.clean: {e}")
        import traceback
        traceback.print_exc()
        return html_content  # Return original if sanitization fails

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main.route('/users')
@login_required
@admin_required
def users():
    users = User.query.order_by(User.full_name).all()
    return render_template('users.html', title='User Management', users=users)

@main.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        # Check if email already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email address already registered.', 'danger')
            return render_template('user_form.html', form=form, title='Create New User')
        
        # Generate username from email
        username = form.email.data.split('@')[0].lower()
        base_username = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create new user with hashed password
        user = User(
            username=username,
            email=form.email.data,
            full_name=form.full_name.data,
            role=form.role.data,
            job_title=form.job_title.data or None,
            direct_phone=form.direct_phone.data or None,
            mobile_phone=form.mobile_phone.data or None,
            must_change_password=True
        )
        
        # Generate temporary password and hash it
        temp_password = user.generate_temp_password()
        user.set_password(temp_password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            flash(f'User created successfully! Temporary password: {temp_password}', 'success')
            return redirect(url_for('main.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
            return render_template('user_form.html', form=form, title='Create New User')
    
    return render_template('user_form.html', form=form, title='Create New User')

@main.route('/users/<int:user_id>')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Only admins can view other users, or users can view their own profile
    if current_user.role != 'admin' and current_user.id != user_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    # Get user activity
    activities = user.get_recent_activity()
    
    return render_template('user_profile.html', user=user, activities=activities)

@main.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        # Check if email is taken by another user
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user and existing_user.id != user_id:
            flash('Email address already taken.', 'danger')
            return render_template('user_form.html', form=form, title='Edit User', user=user)
        
        form.populate_obj(user)
        db.session.commit()
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('main.users'))
    
    return render_template('user_form.html', form=form, title='Edit User', user=user)


@main.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    
    try:
        # Generate new temporary password and hash it
        temp_password = user.generate_temp_password()
        user.set_password(temp_password)
        user.must_change_password = True
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password reset! New temporary password: {temp_password}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/staff-contacts')
@login_required
def get_staff_contacts():
    try:
        staff = User.query.filter_by(is_active=True).order_by(User.full_name).all()
        
        return jsonify([{
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'job_title': user.job_title,
            'role': user.role
        } for user in staff])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/api/users/<int:user_id>/contact-info')
@login_required
def get_user_contact_info(user_id):
    """Get contact information for a specific user"""
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'job_title': user.job_title,
        'direct_phone': user.direct_phone,
        'mobile_phone': user.mobile_phone,
        'role': user.role,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None
    })


@main.route('/api/customers/directory')
@login_required
def get_customers_directory():
    try:
        customers = Customer.query.order_by(Customer.name).all()
        
        return jsonify([{
            'id': customer.id,
            'account_number': customer.account_number,
            'name': customer.name,
            'contact_name': customer.contact_name,
            'phone': customer.phone,
            'email': customer.email
        } for customer in customers])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/dashboard')
@login_required
def dashboard():
    # Get customer count
    customer_count = Customer.query.count()
    
    # Get current date formatted
    current_date = datetime.now().strftime('%A, %B %d, %Y')
    
    return render_template(
        'dashboard.html', 
        title='Hygiene & Catering Admin Portal',
        customer_count=customer_count,
        current_date=current_date
    )

@main.route('/api/todos', methods=['GET'])
@login_required
def get_todos():
    try:
        todos = TodoItem.query.filter_by(user_id=current_user.id).order_by(TodoItem.created_at.desc()).all()
        return jsonify([{
            'id': todo.id,
            'text': todo.text,
            'completed': todo.completed,
            'created_at': todo.created_at.isoformat()
        } for todo in todos])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/api/todos', methods=['POST'])
@login_required
def create_todo():
    try:
        data = request.json
        todo = TodoItem(
            text=data['text'],
            user_id=current_user.id
        )
        db.session.add(todo)
        db.session.commit()
        return jsonify({'success': True, 'id': todo.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def toggle_todo(todo_id):
    try:
        todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
        todo.completed = not todo.completed
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    try:
        todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
        db.session.delete(todo)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

# Company Updates API Routes
@main.route('/api/company-updates', methods=['GET'])
@login_required
def get_company_updates():
    try:
        updates = CompanyUpdate.query.join(User).order_by(
            CompanyUpdate.sticky.desc(),
            CompanyUpdate.created_at.desc()
        ).limit(20).all()
        
        return jsonify([{
            'id': update.id,
            'title': update.title,
            'message': update.message,
            'category': getattr(update, 'category', 'general'),
            'priority': update.priority,
            'sticky': update.sticky,
            'is_event': update.is_event,
            'event_date': update.event_date.isoformat() if update.event_date else None,
            'created_at': update.created_at.isoformat(),
            'author_name': update.author.username,
            'can_delete': update.user_id == current_user.id
        } for update in updates])
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/api/company-updates/<int:update_id>', methods=['GET'])
@login_required
def get_company_update(update_id):
    """Get a specific company update for editing"""
    try:
        update = CompanyUpdate.query.get_or_404(update_id)
        
        # Only allow the author to view for editing (or admins)
        if update.user_id != current_user.id and current_user.role != 'admin':
            return jsonify({'error': 'Permission denied'}), 403
        
        return jsonify({
            'id': update.id,
            'title': update.title,
            'message': update.message,
            'category': getattr(update, 'category', 'general'),
            'priority': update.priority,
            'sticky': update.sticky,
            'is_event': update.is_event,
            'event_date': update.event_date.isoformat() if update.event_date else None,
            'created_at': update.created_at.isoformat(),
            'author_name': update.author.username,
            'can_delete': True
        })
    except Exception as e:
        print(f"Error fetching update {update_id}: {e}")
        return jsonify({'error': 'Failed to fetch update'}), 500


def get_category_config():
    """Get category configuration with colors"""
    return {
        'general': {'color': '#6c757d', 'name': 'General'},
        'safety': {'color': '#dc3545', 'name': 'Safety'},
        'training': {'color': '#28a745', 'name': 'Training'},
        'product': {'color': '#007bff', 'name': 'Product Updates'},
        'events': {'color': '#6f42c1', 'name': 'Events'},
        'policy': {'color': '#fd7e14', 'name': 'Policy Changes'},
        'maintenance': {'color': '#20c997', 'name': 'Maintenance'},
        'announcement': {'color': '#e83e8c', 'name': 'Announcements'}
    }

# Add route to get categories
@main.route('/api/categories')
@login_required
def get_categories():
    """Get available categories for company updates"""
    return jsonify(get_category_config())


@main.route('/api/company-updates/<int:update_id>', methods=['PUT'])
@login_required
def update_company_update(update_id):
    """Update an existing company update"""
    update = CompanyUpdate.query.get_or_404(update_id)
    
    # Only allow the author to edit
    if update.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.json
    
    validation_errors = validate_company_update(data)
    if validation_errors:
        return jsonify({
            'success': False, 
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400

    try:
        # Validate required fields
        if not data.get('title') or not data.get('message'):
            return jsonify({'success': False, 'message': 'Title and message are required'}), 400
        
        # Sanitize the message content
        message = sanitize_html_content(data['message'])
        if not message:
            return jsonify({'success': False, 'message': 'Message content is required'}), 400
        
        # Update the fields
        update.title = data['title'].strip()
        update.message = message
        update.category = data.get('category', 'general')
        update.priority = data.get('priority', 'normal')
        update.sticky = bool(data.get('sticky', False))
        update.is_event = bool(data.get('is_event', False))
        
        # Handle event date
        if update.is_event and data.get('event_date'):
            try:
                update.event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
            except ValueError:
                update.event_date = None
        else:
            update.event_date = None
        
        db.session.commit()
        
        return jsonify({'success': True, 'id': update.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/api/company-updates/<int:update_id>', methods=['DELETE'])
@login_required
def delete_company_update(update_id):
    try:
        update = CompanyUpdate.query.filter_by(id=update_id, user_id=current_user.id).first_or_404()
        db.session.delete(update)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/recent-forms', methods=['GET'])
@login_required
def get_recent_forms():
    try:
        forms = Form.query.filter_by(is_archived=False).join(User, Form.user_id == User.id).order_by(Form.date_created.desc()).limit(5).all()
        
        result = []
        for form in forms:
            form_data = json.loads(form.data)
            result.append({
                'id': form.id,
                'type': form.type.replace('_', ' ').title(),
                'date_created': form.date_created.isoformat(),
                'author': form.author.username,
                'customer_account': form_data.get('customer_account', 'N/A'),
                'customer_name': form_data.get('customer_name', 'N/A'),
                'is_completed': form.is_completed
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



@main.route('/api/customer/<int:customer_id>', methods=['GET'])
@login_required
def get_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return jsonify(customer.to_dict())

@main.route('/api/customer/<int:customer_id>/update', methods=['POST'])
@login_required
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.json
    
    try:
        # Update customer fields
        if 'account_number' in data:
            # Check if account number is unique
            existing = Customer.query.filter_by(account_number=data['account_number']).first()
            if existing and existing.id != customer_id:
                return jsonify({'success': False, 'message': 'Account number already exists'}), 400
            customer.account_number = data['account_number']
        
        if 'name' in data:
            customer.name = data['name']
        if 'contact_name' in data:
            customer.contact_name = data['contact_name']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'email' in data:
            customer.email = data['email']
        if 'address' in data:
            customer.address = data['address']
        if 'notes' in data:
            customer.notes = data['notes']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Customer updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/customers', methods=['POST'])
@login_required
def create_customer():
    """Create a new customer"""
    data = request.json

    validation_errors = validate_customer_data(data)
    if validation_errors:
        return jsonify({
            'success': False, 
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400
    
    try:
        # Check if account number already exists
        existing = Customer.query.filter_by(account_number=data['account_number']).first()
        if existing:
            return jsonify({'success': False, 'message': 'Account number already exists'}), 400
        
        # Validate addresses
        if 'addresses' not in data or len(data['addresses']) == 0:
            return jsonify({'success': False, 'message': 'At least one address is required'}), 400
        
        # Create customer
        customer = Customer(
            account_number=data['account_number'],
            name=data['name'],
            contact_name=data.get('contact_name', ''),
            phone=data.get('phone', ''),  # Main phone number
            email=data.get('email', ''),
            notes=data.get('notes', '')
        )
        
        db.session.add(customer)
        db.session.flush()  # Get the customer ID
        
        # Add addresses
        for idx, addr_data in enumerate(data['addresses']):
            if not addr_data.get('label'):
                return jsonify({'success': False, 'message': 'Each address must have a label'}), 400
            
            address = CustomerAddress(
                customer_id=customer.id,
                label=addr_data['label'],
                phone=addr_data.get('phone', ''),
                street=addr_data.get('street', ''),
                city=addr_data.get('city', ''),
                zip=addr_data.get('zip', ''),
                is_primary=(idx == 0)  # First address is primary
            )
            db.session.add(address)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Customer created successfully',
            'customer': customer.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/customer/<int:customer_id>', methods=['GET', 'PUT'])
@login_required
def customer_detail(customer_id):
    """Get or update customer details"""
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'GET':
        return jsonify(customer.to_dict())
    
    if request.method == 'PUT':
        data = request.json
        
        try:
            # Update basic customer fields
            if 'account_number' in data:
                existing = Customer.query.filter_by(account_number=data['account_number']).first()
                if existing and existing.id != customer_id:
                    return jsonify({'success': False, 'message': 'Account number already exists'}), 400
                customer.account_number = data['account_number']
            
            if 'name' in data:
                customer.name = data['name']
            if 'contact_name' in data:
                customer.contact_name = data['contact_name']
            if 'phone' in data:
                customer.phone = data['phone']
            if 'email' in data:
                customer.email = data['email']
            if 'notes' in data:
                customer.notes = data['notes']
            
            # Handle addresses
            if 'addresses' in data:
                # Remove old addresses
                CustomerAddress.query.filter_by(customer_id=customer_id).delete()
                
                # Add new addresses
                for idx, addr_data in enumerate(data['addresses']):
                    if not addr_data.get('label'):
                        return jsonify({'success': False, 'message': 'Each address must have a label'}), 400
                    
                    address = CustomerAddress(
                        customer_id=customer_id,
                        label=addr_data['label'],
                        phone=addr_data.get('phone', ''),
                        street=addr_data.get('street', ''),
                        city=addr_data.get('city', ''),
                        zip=addr_data.get('zip', ''),
                        is_primary=(idx == 0)  # First address is primary
                    )
                    db.session.add(address)
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'Customer updated successfully', 'customer': customer.to_dict()})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/customer/<int:customer_id>/addresses', methods=['GET'])
@login_required
def get_customer_addresses(customer_id):
    try:
        customer = Customer.query.get_or_404(customer_id)
        addresses = [addr.to_dict() for addr in customer.addresses]
        
        if not addresses and customer.address:
            addresses = [{
                'id': None,
                'label': 'Primary',
                'phone': '',
                'street': customer.address,
                'city': '',
                'zip': '',
                'is_primary': True
            }]
        
        return jsonify(addresses)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/api/products/search')
@login_required
def search_products():
    try:
        query = request.args.get('q', '').strip()
        
        if len(query) < 2:
            return jsonify([])
        
        products = Product.query.filter(
            db.or_(
                Product.code.ilike(f'%{query}%'),
                Product.name.ilike(f'%{query}%'),
                Product.description.ilike(f'%{query}%')
            )
        ).limit(20).all()
        
        results = []
        for product in products:
            results.append({
                'id': product.id,
                'code': product.code,
                'name': product.name,
            })
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/returns', methods=['GET', 'POST'])
@login_required
def returns():
    form = ReturnsForm()
    if form.validate_on_submit():
        # Update customer address if provided
        if form.customer_account.data and form.customer_address.data:
            customer = Customer.query.filter_by(account_number=form.customer_account.data).first()
            if customer and form.customer_address.data != customer.address:
                customer.address = form.customer_address.data
                db.session.commit()
        
        # Get products from the form - check if there are multiple products submitted via JavaScript
        products_data = []
        
        # Check for additional products submitted via JavaScript
        additional_products = request.form.getlist('additional_products')
        if additional_products:
            import json
            try:
                products_data = json.loads(additional_products[0])
            except:
                products_data = []
        
        # Add the main product
        if form.product_code.data:
            products_data.insert(0, {
                'product_code': form.product_code.data,
                'product_name': form.product_name.data,
                'quantity': form.quantity.data
            })
        
        customer_contact = None
        if form.customer_account.data:
            customer = Customer.query.filter_by(account_number=form.customer_account.data).first()
            if customer:
                customer_contact = customer.contact_name

        form_data = {
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'customer_address': form.customer_address.data,
            'contact_name': customer_contact,
            'products': products_data,
            'reason': form.reason.data,
            'notes': form.notes.data
        }
        
        new_form = Form(
            type='returns',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash(f'Return form #{new_form.id} has been created successfully!', 'success')
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
            # Return JSON for AJAX request
            return jsonify({
                'success': True,
                'form_id': new_form.id,
                'message': f'Return form #{new_form.id} has been created successfully!'
            })
        else:
            # Return JavaScript for regular form submission (backward compatibility)
            return f'''
            <script>
                window.open('{url_for('main.print_form', form_id=new_form.id)}', '_blank');
                window.location.href = '{url_for('main.dashboard')}';
            </script>
            '''
    
    return render_template('returns_form.html', title='Returns Form', form=form)



@main.route('/invoice-correction', methods=['GET', 'POST'])
@login_required
def invoice_correction():
    form = InvoiceCorrectionForm()
    if form.validate_on_submit():
        # Update customer address if provided
        if form.customer_account.data and form.customer_address.data:
            customer = Customer.query.filter_by(account_number=form.customer_account.data).first()
            if customer and form.customer_address.data != customer.address:
                customer.address = form.customer_address.data
                db.session.commit()
        
        customer_contact = None
        if form.customer_account.data:
            customer = Customer.query.filter_by(account_number=form.customer_account.data).first()
            if customer:
                customer_contact = customer.contact_name
        
        # Get products from the form - check if there are multiple products submitted via JavaScript
        products_data = []
        
        # Check for additional products submitted via JavaScript
        additional_products = request.form.getlist('additional_products')
        if additional_products:
            try:
                products_data = json.loads(additional_products[0])
            except:
                products_data = []
        
        # Add the main product
        if form.product_code.data:
            ordered = int(form.ordered_quantity.data) if form.ordered_quantity.data else 0
            delivered = int(form.delivered_quantity.data) if form.delivered_quantity.data else 0
            outstanding = ordered - delivered
            
            products_data.insert(0, {
                'product_code': form.product_code.data,
                'product_name': form.product_name.data,
                'ordered_quantity': ordered,
                'delivered_quantity': delivered,
                'outstanding_quantity': outstanding
            })
        
        form_data = {
            'invoice_number': form.invoice_number.data,
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'customer_address': form.customer_address.data,
            'address_label': request.form.get('address_label', ''),
            'contact_name': customer_contact,
            'products': products_data,
            'notes': form.notes.data
        }
        
        new_form = Form(
            type='invoice_correction',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash(f'Invoice correction form #{new_form.id} has been created successfully!', 'success')
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({
                'success': True,
                'form_id': new_form.id,
                'message': f'Invoice correction form #{new_form.id} has been created successfully!'
            })
        
        return redirect(url_for('main.dashboard'))
    
    return render_template('invoice_correction.html', title='Invoice Correction - Delivery Only', form=form)

@main.route('/api/customers')
@login_required
def api_customers():
    return jsonify(SAMPLE_CUSTOMERS)

@main.route('/api/products')
@login_required
def api_products():
    return jsonify(SAMPLE_PRODUCTS)

@main.route('/forms')
@login_required
def forms():
    # Get filter parameters
    form_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    submitted_by = request.args.get('submitted_by', '')
    customer_search = request.args.get('customer', '')
    show_archived = request.args.get('show_archived', 'false') == 'true'
    
    # Base query
    query = Form.query
    
    # Apply archived filter
    if not show_archived:
        query = query.filter_by(is_archived=False)
    
    # Apply filters
    if form_type:
        query = query.filter(Form.type == form_type)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Form.date_created >= date_from_obj)
        except:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(Form.date_created <= date_to_obj)
        except:
            pass
    
    if submitted_by:
        query = query.join(User, Form.user_id == User.id).filter(User.username.ilike(f'%{submitted_by}%'))
    
    # Order by date
    all_forms = query.order_by(Form.date_created.desc()).all()
    
    # Filter by customer if specified (this needs to be done after loading since customer data is in JSON)
    if customer_search:
        filtered_forms = []
        for form in all_forms:
            form_data = json.loads(form.data)
            customer_account = form_data.get('customer_account', '')
            customer_name = form_data.get('customer_name', '')
            if customer_search.lower() in customer_account.lower() or customer_search.lower() in customer_name.lower():
                filtered_forms.append(form)
        all_forms = filtered_forms
    
    # Prepare forms with data
    forms_with_data = []
    for form in all_forms:
        form_data = json.loads(form.data)
        form_dict = {
            'id': form.id,
            'type': form.type.replace('_', ' ').title(),
            'type_raw': form.type,
            'date_created': form.date_created,
            'author': User.query.get(form.user_id).username if User.query.get(form.user_id) else 'Unknown',
            'data': form_data,
            'customer_account': form_data.get('customer_account', 'N/A'),
            'customer_name': form_data.get('customer_name', 'N/A'),
            'is_completed': form.is_completed,
            'completed_date': form.completed_date,
            'completed_by': User.query.get(form.completed_by).username if form.completed_by else None,
            'is_archived': form.is_archived
        }
        forms_with_data.append(form_dict)
    
    # Get unique form types for filter dropdown
    unique_types = db.session.query(Form.type).distinct().all()
    form_types = [t[0] for t in unique_types]
    
    # Get all users for filter dropdown
    all_users = User.query.all()
    
    return render_template('forms.html', 
                         title='All Forms', 
                         forms=forms_with_data,
                         form_types=form_types,
                         all_users=all_users,
                         current_filters={
                             'type': form_type,
                             'date_from': date_from,
                             'date_to': date_to,
                             'submitted_by': submitted_by,
                             'customer': customer_search,
                             'show_archived': show_archived
                         })

@main.route('/form/<int:form_id>')
@login_required
def view_form(form_id):
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    user = User.query.get(form.user_id)
    author = user.username if user else 'Unknown'
    
    return render_template(
        'view_form.html', 
        title=f'{form.type.replace("_", " ").title()} - #{form_id}',
        form_type=form.type,
        form_data=form_data,
        author=author,
        date_created=form.date_created,
        form_id=form_id,
        datetime=datetime
    )

@main.route('/api/form/<int:form_id>/complete', methods=['POST'])
@login_required
def complete_form(form_id):
    form = Form.query.get_or_404(form_id)
    
    try:
        form.is_completed = True
        form.completed_date = datetime.now()
        form.completed_by = current_user.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Form marked as completed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/form/<int:form_id>/archive', methods=['POST'])
@login_required
def archive_form(form_id):
    form = Form.query.get_or_404(form_id)
    
    try:
        form.is_archived = True
        if not form.is_completed:
            form.is_completed = True
            form.completed_date = datetime.now()
            form.completed_by = current_user.id
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Form archived successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/form/<int:form_id>/unarchive', methods=['POST'])
@login_required
def unarchive_form(form_id):
    form = Form.query.get_or_404(form_id)
    
    try:
        form.is_archived = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Form restored from archive'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/form/print/<int:form_id>')
@login_required
def print_form(form_id):
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    user = User.query.get(form.user_id)
    author = user.username if user else 'Unknown'
    
    # Determine which template to use based on form type
    if form.type == 'branded_stock':
        return render_template(
            'print_branded_stock.html',
            title=f'Stock Order - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )
    elif form.type == 'invoice_correction':
        return render_template(
            'print_invoice_correction.html',
            title=f'Invoice Correction - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )
    else:
        # Default to returns/credit uplift template
        return render_template(
            'print_form.html', 
            title=f'{form.type.replace("_", " ").title()} - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )

@main.route('/api/customers/search')
@login_required
def search_customers():
    """Search customers by account number or name"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    # Search in both account number and name fields
    customers = Customer.query.filter(
        db.or_(
            Customer.account_number.ilike(f'%{query}%'),
            Customer.name.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'account_number': customer.account_number,
            'name': customer.name,
            'display': f'{customer.account_number} - {customer.name}',
            'contact_name': customer.contact_name,
            'phone': customer.phone,
            'address': customer.address
        })
    
    return jsonify(results)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_dir():
    """Create upload directory if it doesn't exist"""
    now = datetime.now()
    upload_dir = os.path.join('static', 'uploads', 'company_updates', str(now.year), f"{now.month:02d}")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir

def resize_image(image_path, max_width=800, max_height=600):
    """Resize image while maintaining aspect ratio"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG saving)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Calculate new dimensions
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            img.save(image_path, 'JPEG', quality=85, optimize=True)
    except Exception as e:
        print(f"Error resizing image: {e}")

@main.route('/api/upload-image', methods=['POST'])
@login_required
def upload_image():
    """Handle image uploads for company updates"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No image file provided'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WebP files.'}), 400
    
    # Check file size
    if len(file.read()) > MAX_IMAGE_SIZE:
        return jsonify({'success': False, 'message': 'File too large. Maximum size is 2MB.'}), 400
    
    file.seek(0)  # Reset file pointer after reading
    
    try:
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{name}{ext}"
        
        # Create upload directory
        upload_dir = ensure_upload_dir()
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        file.save(file_path)
        
        # Resize image
        resize_image(file_path)
        
        # Return URL for frontend
        relative_path = file_path.replace('static/', '/')
        image_url = url_for('static', filename=file_path.replace('static/', ''))
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'message': 'Image uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500

@main.route('/api/company-updates', methods=['POST'])
@login_required
def create_company_update():
    data = request.json

    validation_errors = validate_company_update(data)
    if validation_errors:
        return jsonify({
            'success': False, 
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400
    
    try:
        # Validate required fields
        if not data.get('title') or not data.get('message'):
            return jsonify({'success': False, 'message': 'Title and message are required'}), 400
        
        # Sanitize the message content
        message = sanitize_html_content(data['message'])
        if not message:
            return jsonify({'success': False, 'message': 'Message content is required'}), 400
        
        # Create new update
        update = CompanyUpdate(
            title=data['title'].strip(),
            message=message,
            category=data.get('category', 'general'),  # Include category
            priority=data.get('priority', 'normal'),
            sticky=bool(data.get('sticky', False)),
            is_event=bool(data.get('is_event', False)),
            user_id=current_user.id
        )
        
        # Handle event date
        if update.is_event and data.get('event_date'):
            try:
                update.event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
            except ValueError:
                update.event_date = None
        
        db.session.add(update)
        db.session.commit()
        
        return jsonify({'success': True, 'id': update.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@main.route('/api/recent-activity')
@login_required
def get_recent_activity():
    """Get recent activity across the system from all users"""
    activities = []
    
    try:
        # Recent forms (created by any user)
        recent_forms = Form.query.join(User, Form.user_id == User.id).order_by(Form.date_created.desc()).limit(5).all()
        for form in recent_forms:
            activities.append({
                'type': 'form_created',
                'description': f'Created {form.type.replace("_", " ").title()} form',
                'user': form.author.username,
                'timestamp': form.date_created,
                'link': url_for('main.view_form', form_id=form.id),
                'icon': 'bi-file-text'
            })
    except Exception as e:
        print(f"Error loading recent forms: {e}")
    
    try:
        # Recently completed forms (by any user)
        completed_forms = Form.query.filter(
            Form.is_completed == True,
            Form.completed_date.isnot(None)
        ).join(User, Form.completed_by == User.id).order_by(Form.completed_date.desc()).limit(3).all()
        
        for form in completed_forms:
            if form.completer:
                activities.append({
                    'type': 'form_completed',
                    'description': f'Completed {form.type.replace("_", " ").title()} form',
                    'user': form.completer.username,
                    'timestamp': form.completed_date,
                    'link': url_for('main.view_form', form_id=form.id),
                    'icon': 'bi-check-circle'
                })
    except Exception as e:
        print(f"Error loading completed forms: {e}")
    
    try:
        # Recent company updates (by any user)
        recent_updates = CompanyUpdate.query.join(User, CompanyUpdate.user_id == User.id).order_by(CompanyUpdate.created_at.desc()).limit(4).all()
        for update in recent_updates:
            activities.append({
                'type': 'company_update',
                'description': f'Posted update: {update.title}',
                'user': update.author.username,
                'timestamp': update.created_at,
                'link': None,
                'icon': 'bi-megaphone'
            })
    except Exception as e:
        print(f"Error loading company updates: {e}")
    
    try:
        # Recent callsheet creation (by any user)
        recent_callsheets = Callsheet.query.join(User, Callsheet.created_by == User.id).order_by(Callsheet.created_at.desc()).limit(3).all()
        for callsheet in recent_callsheets:
            activities.append({
                'type': 'callsheet_created',
                'description': f'Created callsheet "{callsheet.name}" for {callsheet.day_of_week}',
                'user': callsheet.created_by_user.username,
                'timestamp': callsheet.created_at,
                'link': url_for('callsheets.callsheets'),
                'icon': 'bi-calendar-plus'
            })
    except Exception as e:
        print(f"Error loading recent callsheets: {e}")
    
    try:
        # Recent customers added to callsheets (by any user)
        recent_callsheet_additions = CallsheetEntry.query.join(
            User, CallsheetEntry.user_id == User.id
        ).join(
            Customer, CallsheetEntry.customer_id == Customer.id
        ).join(
            Callsheet, CallsheetEntry.callsheet_id == Callsheet.id
        ).order_by(CallsheetEntry.id.desc()).limit(5).all()  # Use id.desc() to get most recently added
        
        for entry in recent_callsheet_additions:
            # Only show if this was recently created (within last few days)
            if (datetime.now() - entry.callsheet.created_at).days <= 7:
                activities.append({
                    'type': 'callsheet_customer_added',
                    'description': f'Added {entry.customer.name} to callsheet "{entry.callsheet.name}"',
                    'user': User.query.get(entry.user_id).username,
                    'timestamp': entry.callsheet.created_at,  # Use callsheet creation time as proxy
                    'link': url_for('callsheets.callsheets'),
                    'icon': 'bi-person-plus'
                })
    except Exception as e:
        print(f"Error loading callsheet customer additions: {e}")
    
    try:
        # Recent callsheet call activity (status changes)
        recent_callsheet_calls = CallsheetEntry.query.filter(
            CallsheetEntry.call_status != 'not_called',
            CallsheetEntry.updated_at.isnot(None)
        ).join(User, CallsheetEntry.user_id == User.id).join(Customer, CallsheetEntry.customer_id == Customer.id).order_by(CallsheetEntry.updated_at.desc()).limit(5).all()
        
        for entry in recent_callsheet_calls:
            # Get the status description
            status_descriptions = {
                'no_answer': 'called (no answer)',
                'declined': 'called (declined)', 
                'ordered': 'took order from',
                'callback': 'scheduled callback with'
            }
            
            status_desc = status_descriptions.get(entry.call_status, f'updated callsheet for')
            
            activities.append({
                'type': 'callsheet_call',
                'description': f'{status_desc.title()} {entry.customer.name}',
                'user': User.query.get(entry.user_id).username,
                'timestamp': entry.updated_at,
                'link': url_for('callsheets.callsheets'),
                'icon': 'bi-telephone'
            })
    except Exception as e:
        print(f"Error loading callsheet call activity: {e}")
    
    try:
        # Recent standing order creation (if the model exists)
        recent_standing_orders = StandingOrder.query.join(User, StandingOrder.created_by == User.id).order_by(StandingOrder.created_at.desc()).limit(3).all()
        for order in recent_standing_orders:
            activities.append({
                'type': 'standing_order_created',
                'description': f'Created standing order for {order.customer.name}',
                'user': order.created_by_user.username,
                'timestamp': order.created_at,
                'link': url_for('standing_orders.view_standing_order', order_id=order.id),
                'icon': 'bi-arrow-repeat'
            })
    except Exception as e:
        print(f"Error loading standing orders (may not exist): {e}")
    
    try:
        # Recent standing order actions (pause, resume, end) - if the model exists
        recent_so_logs = StandingOrderLog.query.filter(
            StandingOrderLog.action_type.in_(['paused', 'resumed', 'ended'])
        ).join(User, StandingOrderLog.performed_by == User.id).order_by(StandingOrderLog.performed_at.desc()).limit(3).all()
        
        for log in recent_so_logs:
            action_descriptions = {
                'paused': f'Paused standing order for {log.standing_order.customer.name}',
                'resumed': f'Resumed standing order for {log.standing_order.customer.name}',
                'ended': f'Ended standing order for {log.standing_order.customer.name}'
            }
            
            activities.append({
                'type': f'standing_order_{log.action_type}',
                'description': action_descriptions.get(log.action_type, f'{log.action_type.title()} standing order'),
                'user': log.user.username,
                'timestamp': log.performed_at,
                'link': url_for('standing_orders.view_standing_order', order_id=log.standing_order_id),
                'icon': 'bi-arrow-repeat'
            })
    except Exception as e:
        print(f"Error loading standing order logs (may not exist): {e}")
    
    try:
        # Recent customer stock transactions (if the model exists)
        recent_stock_transactions = StockTransaction.query.join(User, StockTransaction.created_by == User.id).order_by(StockTransaction.transaction_date.desc()).limit(3).all()
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
                'user': transaction.user.username,
                'timestamp': transaction.transaction_date,
                'link': url_for('customer_stock.customer_stock'),
                'icon': 'bi-box-seam'
            })
    except Exception as e:
        print(f"Error loading stock transactions (may not exist): {e}")
    
    # User logins removed - not needed in activity feed
    # Sort all activities by timestamp and limit to 15 (since we're pulling from multiple sources)
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    activities = activities[:15]
    
    # Convert timestamps to ISO format for JavaScript
    for activity in activities:
        if hasattr(activity['timestamp'], 'isoformat'):
            activity['timestamp'] = activity['timestamp'].isoformat()
    
    return jsonify(activities)
   