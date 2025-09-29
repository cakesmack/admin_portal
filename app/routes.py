from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Customer, CallsheetEntry, Form, Callsheet, CallsheetArchive, TodoItem, CompanyUpdate, CustomerStock, StockTransaction, StandingOrder, StandingOrderItem, StandingOrderLog, StandingOrderSchedule, Product
from app.forms import LoginForm, ReturnsForm, BrandedStockForm, InvoiceCorrectionForm, SpecialOrderForm, CreateUserForm, EditUserForm, ChangePasswordForm, ForcePasswordChangeForm
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

@main.route('/')
def index():
    return redirect(url_for('main.login'))


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        # Try login by email first, then username
        user = User.query.filter_by(email=form.username.data).first() or \
               User.query.filter_by(username=form.username.data).first()
        
        # Updated to use password hashing
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user)
            user.last_login = datetime.now()
            db.session.commit()
            
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            
            # Check if password change is required
            if user.must_change_password:
                return redirect(url_for('main.force_password_change'))
            
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login unsuccessful. Please check your credentials.', 'danger')
    
    return render_template('login.html', title='Login', form=form)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

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

@main.route('/force-password-change', methods=['GET', 'POST'])
@login_required
def force_password_change():
    if not current_user.must_change_password:
        return redirect(url_for('main.dashboard'))
    
    form = ForcePasswordChangeForm()
    if form.validate_on_submit():
        # Use the new password hashing method
        current_user.set_password(form.new_password.data)
        current_user.must_change_password = False
        current_user.last_login = datetime.now()
        
        try:
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating password: {str(e)}', 'danger')
    
    return render_template('force_password_change.html', form=form)

@main.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Check current password using hash verification
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)
        
        # Set new password with hashing
        current_user.set_password(form.new_password.data)
        
        try:
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.user_profile', user_id=current_user.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
    
    return render_template('change_password.html', form=form)

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

@main.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

@main.route('/api/staff-contacts')
@login_required
def get_staff_contacts():
    """Get list of all active staff members for contacts"""
    staff = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    
    return jsonify([{
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'job_title': user.job_title,
        'role': user.role
    } for user in staff])

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
    """Get all customers for directory with contact details"""
    customers = Customer.query.order_by(Customer.name).all()
    
    return jsonify([{
        'id': customer.id,
        'account_number': customer.account_number,
        'name': customer.name,
        'contact_name': customer.contact_name,
        'phone': customer.phone,
        'email': customer.email
    } for customer in customers])


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

# Todo API Routes
@main.route('/api/todos', methods=['GET'])
@login_required
def get_todos():
    todos = TodoItem.query.filter_by(user_id=current_user.id).order_by(TodoItem.created_at.desc()).all()
    return jsonify([{
        'id': todo.id,
        'text': todo.text,
        'completed': todo.completed,
        'created_at': todo.created_at.isoformat()
    } for todo in todos])

@main.route('/api/todos', methods=['POST'])
@login_required
def create_todo():
    data = request.json
    todo = TodoItem(
        text=data['text'],
        user_id=current_user.id
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify({'success': True, 'id': todo.id})

@main.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def toggle_todo(todo_id):
    todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    todo.completed = not todo.completed
    db.session.commit()
    return jsonify({'success': True})

@main.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
    db.session.delete(todo)
    db.session.commit()
    return jsonify({'success': True})

# Company Updates API Routes
@main.route('/api/company-updates', methods=['GET'])
@login_required
def get_company_updates():
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
        'author_name': update.author.username,  # Fixed: use username instead of author
        'can_delete': update.user_id == current_user.id
    } for update in updates])

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


# Add this function to get category colors
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
    update = CompanyUpdate.query.filter_by(id=update_id, user_id=current_user.id).first_or_404()
    db.session.delete(update)
    db.session.commit()
    return jsonify({'success': True})

# Recent Forms API Route
@main.route('/api/recent-forms', methods=['GET'])
@login_required
def get_recent_forms():
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

# Callsheet Routes - Add these to your routes.py file
# Replace existing callsheet routes with these updated versions

from sqlalchemy.orm import joinedload
from sqlalchemy import func

@main.route('/callsheets')
@login_required
def callsheets():
    """Main callsheets page with improved query efficiency"""
    now = datetime.now()
    current_month = request.args.get('month', default=now.month, type=int)
    current_year = request.args.get('year', default=now.year, type=int)
    
    # Calculate previous and next month/year for navigation
    if current_month == 1:
        prev_month, prev_year = 12, current_year - 1
    else:
        prev_month, prev_year = current_month - 1, current_year
    
    if current_month == 12:
        next_month, next_year = 1, current_year + 1
    else:
        next_month, next_year = current_month + 1, current_year
    
    # Efficient query with eager loading
    callsheets = Callsheet.query.filter_by(
        month=current_month,
        year=current_year,
        is_active=True
    ).options(
        joinedload(Callsheet.entries).joinedload(CallsheetEntry.customer)
    ).order_by(
        Callsheet.day_of_week,
        Callsheet.name
    ).all()
    
    # Organize callsheets by day
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    callsheets_by_day = {day: [] for day in days_of_week}
    
    for callsheet in callsheets:
        if callsheet.day_of_week in callsheets_by_day:
            # Load entries and separate active from paused
            all_entries = sorted(callsheet.entries, key=lambda x: x.position)
            
            active_entries = [e for e in all_entries if not e.is_paused]
            paused_entries = [e for e in all_entries if e.is_paused]
            
            callsheet_data = {
                'id': callsheet.id,
                'name': callsheet.name,
                'entries': active_entries,
                'paused_entries': paused_entries
            }
            callsheets_by_day[callsheet.day_of_week].append(callsheet_data)
    
    # Get all customers for add customer modal
    all_customers = Customer.query.order_by(Customer.name).all()
    
    return render_template(
        'callsheets.html',
        title='Call Sheets',
        callsheets_by_day=callsheets_by_day,
        days_of_week=days_of_week,
        current_month=current_month,
        current_year=current_year,
        month_name=calendar.month_name[current_month],
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        all_customers=all_customers,
        current_user=current_user
    )


@main.route('/api/callsheet/create', methods=['POST'])
@login_required
def create_callsheet():
    """Create new callsheet with duplicate name checking"""
    data = request.json
    
    try:
        # Check for duplicate name on same day
        existing = Callsheet.query.filter_by(
            name=data['name'],
            day_of_week=data['day_of_week'],
            month=data['month'],
            year=data['year'],
            is_active=True
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': 'A callsheet with this name already exists for this day'
            }), 400
        
        callsheet = Callsheet(
            name=data['name'],
            day_of_week=data['day_of_week'],
            month=data['month'],
            year=data['year'],
            created_by=current_user.id
        )
        db.session.add(callsheet)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'id': callsheet.id, 
            'message': 'Callsheet created successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet/<int:callsheet_id>/update', methods=['POST'])
@login_required
def update_callsheet(callsheet_id):
    """Update callsheet - FIXED parameter name"""
    callsheet = Callsheet.query.get_or_404(callsheet_id)
    data = request.json
    
    try:
        if 'name' in data:
            # Check for duplicate name
            existing = Callsheet.query.filter(
                Callsheet.name == data['name'],
                Callsheet.day_of_week == callsheet.day_of_week,
                Callsheet.month == callsheet.month,
                Callsheet.year == callsheet.year,
                Callsheet.is_active == True,
                Callsheet.id != callsheet_id
            ).first()
            
            if existing:
                return jsonify({
                    'success': False, 
                    'message': 'A callsheet with this name already exists for this day'
                }), 400
            
            callsheet.name = data['name']
        
        if 'day_of_week' in data:
            callsheet.day_of_week = data['day_of_week']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Callsheet updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet/<int:callsheet_id>/delete', methods=['POST'])
@login_required
def delete_callsheet(callsheet_id):
    """Soft delete callsheet instead of permanent deletion"""
    callsheet = Callsheet.query.get_or_404(callsheet_id)
    
    try:
        # Soft delete - mark as inactive
        callsheet.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Callsheet deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet/<int:callsheet_id>/add-customer', methods=['POST'])
@login_required
def add_customer_to_callsheet(callsheet_id):
    """Add customer to callsheet"""
    data = request.json
    
    try:
        # Check if customer already exists in this callsheet
        existing = CallsheetEntry.query.filter_by(
            callsheet_id=callsheet_id,
            customer_id=data['customer_id']
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': 'Customer already in this callsheet'
            }), 400
        
        # Get the highest position in this callsheet
        max_position = db.session.query(func.max(CallsheetEntry.position))\
            .filter_by(callsheet_id=callsheet_id).scalar() or 0
        
        entry = CallsheetEntry(
            callsheet_id=callsheet_id,
            customer_id=data['customer_id'],
            user_id=current_user.id,
            position=max_position + 1,
            call_status='not_called'
        )
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Customer added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/update-status', methods=['POST'])
@login_required
def update_callsheet_entry_status(entry_id):
    """Update call status with automatic tracking"""
    entry = CallsheetEntry.query.get_or_404(entry_id)
    data = request.json
    
    try:
        # Update call status
        if 'call_status' in data:
            entry.call_status = data['call_status']
            
            # Record who called and when (if status changed from not_called)
            if data['call_status'] != 'not_called' and entry.called_by is None:
                entry.called_by = current_user.username
                entry.call_date = datetime.now()
            
            # Handle person_spoken_to for ALL statuses (not just ordered)
            if 'person_spoken_to' in data:
                entry.person_spoken_to = data['person_spoken_to']
            
            # Handle callback time
            if data['call_status'] == 'callback' and 'callback_time' in data:
                entry.callback_time = data['callback_time']
        
        # Track who made the update
        entry.user_id = current_user.id
        entry.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Entry updated successfully',
            'updated_by': current_user.username,
            'updated_at': entry.updated_at.strftime('%Y-%m-%d %H:%M')
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/update-notes', methods=['POST'])
@login_required
def update_customer_notes(entry_id):
    """Update customer's persistent callsheet notes"""
    entry = CallsheetEntry.query.get_or_404(entry_id)
    data = request.json
    
    try:
        customer = entry.customer
        customer.callsheet_notes = data.get('notes', '')
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Notes updated successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_callsheet_entry(entry_id):
    """Remove customer from callsheet"""
    entry = CallsheetEntry.query.get_or_404(entry_id)
    
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Customer removed from callsheet'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/toggle-pause', methods=['POST'])
@login_required
def toggle_pause_callsheet_entry(entry_id):
    """Pause or resume a customer on the callsheet"""
    entry = CallsheetEntry.query.get_or_404(entry_id)
    
    try:
        # Toggle pause status
        entry.is_paused = not entry.is_paused
        
        # When pausing, move to end of list
        if entry.is_paused:
            max_position = db.session.query(func.max(CallsheetEntry.position))\
                .filter_by(callsheet_id=entry.callsheet_id).scalar() or 0
            entry.position = max_position + 1
        
        db.session.commit()
        
        status = "paused" if entry.is_paused else "resumed"
        return jsonify({
            'success': True, 
            'message': f'Customer {status} successfully',
            'is_paused': entry.is_paused
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/reorder', methods=['POST'])
@login_required
def reorder_callsheet_entry(entry_id):
    """Update position of entry for drag-and-drop reordering"""
    entry = CallsheetEntry.query.get_or_404(entry_id)
    data = request.json
    
    try:
        new_position = data.get('position')
        old_position = entry.position
        callsheet_id = entry.callsheet_id
        
        # Update positions of other entries
        if new_position > old_position:
            # Moving down - decrement positions in between
            CallsheetEntry.query.filter(
                CallsheetEntry.callsheet_id == callsheet_id,
                CallsheetEntry.position > old_position,
                CallsheetEntry.position <= new_position
            ).update({'position': CallsheetEntry.position - 1})
        else:
            # Moving up - increment positions in between
            CallsheetEntry.query.filter(
                CallsheetEntry.callsheet_id == callsheet_id,
                CallsheetEntry.position >= new_position,
                CallsheetEntry.position < old_position
            ).update({'position': CallsheetEntry.position + 1})
        
        entry.position = new_position
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheets/reset-week', methods=['POST'])
@login_required
def reset_week():
    """Reset all callsheets for the current week - preserves customer notes"""
    data = request.json
    month = data.get('month')
    year = data.get('year')
    
    try:
        # Get all active callsheets for the month
        callsheets = Callsheet.query.filter_by(
            month=month, 
            year=year, 
            is_active=True
        ).all()
        
        for callsheet in callsheets:
            # Reset all entries to 'not_called'
            entries = CallsheetEntry.query.filter_by(callsheet_id=callsheet.id).all()
            for entry in entries:
                entry.call_status = 'not_called'
                entry.called_by = None
                entry.call_date = None
                entry.person_spoken_to = None
                entry.callback_time = None
                entry.updated_at = datetime.now()
                # Note: customer.callsheet_notes are preserved automatically!
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'All callsheets reset for {calendar.month_name[month]} {year}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheets/archive', methods=['POST'])
@login_required
def archive_callsheets():
    """Archive current month's callsheets"""
    data = request.json
    month = data.get('month')
    year = data.get('year')
    
    try:
        # Get all callsheets for the month
        callsheets = Callsheet.query.filter_by(
            month=month, 
            year=year, 
            is_active=True
        ).all()
        
        # Create archive data
        archive_data = []
        for cs in callsheets:
            entries = CallsheetEntry.query.filter_by(callsheet_id=cs.id).all()
            cs_data = {
                'name': cs.name,
                'day_of_week': cs.day_of_week,
                'entries': [
                    {
                        'customer_id': entry.customer_id,
                        'customer_name': entry.customer.name,
                        'customer_account': entry.customer.account_number,
                        'call_status': entry.call_status,
                        'called_by': entry.called_by,
                        'person_spoken_to': entry.person_spoken_to,
                        'callback_time': entry.callback_time,
                        'notes': entry.customer.callsheet_notes
                    } for entry in entries
                ]
            }
            archive_data.append(cs_data)
        
        # Create archive record
        archive = CallsheetArchive(
            month=month,
            year=year,
            data=json.dumps(archive_data),
            archived_by=current_user.id
        )
        db.session.add(archive)
        
        # Mark current callsheets as inactive
        for cs in callsheets:
            cs.is_active = False
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Callsheets for {calendar.month_name[month]} {year} archived successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/callsheets/archive/<int:month>/<int:year>')
@login_required
def view_archived_callsheets(month, year):
    """View archived callsheets for a specific month/year"""
    archive = CallsheetArchive.query.filter_by(month=month, year=year).first()
    
    if not archive:
        flash(f'No archived callsheets found for {calendar.month_name[month]} {year}', 'warning')
        return redirect(url_for('main.callsheets'))
    
    archive_data = json.loads(archive.data)
    
    return render_template(
        'archived_callsheets.html',
        title=f'Archived Callsheets - {calendar.month_name[month]} {year}',
        archive_data=archive_data,
        month=month,
        year=year,
        archived_by=archive.archived_by_user.username,
        archived_at=archive.archived_at
    )

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

@main.route('/api/customer/create', methods=['POST'])
@login_required
def create_customer():
    data = request.json
    
    try:
        # Check if account number already exists
        existing = Customer.query.filter_by(account_number=data['account_number']).first()
        if existing:
            return jsonify({'success': False, 'message': 'Account number already exists'}), 400
        
        customer = Customer(
            account_number=data['account_number'],
            name=data['name'],
            contact_name=data.get('contact_name', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address=data.get('address', ''),
            notes=data.get('notes', '')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Customer created successfully',
            'customer': customer.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/products/search')
@login_required
def search_products():
    """Search products by code or description"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    # Search in both product code and name fields
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
            'description': product.description,
            'display': f'{product.code} - {product.name}'
        })
    
    return jsonify(results)

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
        
        # Check for additional products submitted via JavaScript (we'll add this)
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
            'products': products_data,  # This will work with your existing print form
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
        
        flash('Return form has been created successfully!', 'success')
        
        # Return JavaScript to open print form and redirect
        return f'''
        <script>
            window.open('{url_for('main.print_form', form_id=new_form.id)}', '_blank');
            window.location.href = '{url_for('main.dashboard')}';
        </script>
        '''
    
    return render_template('returns_form.html', title='Returns Form', form=form)

@main.route('/branded-stock', methods=['GET', 'POST'])
@login_required
def branded_stock():
    form = BrandedStockForm()
    if form.validate_on_submit():
        stock_item_id = request.form.get('stock_item_id')
        
        if stock_item_id:
            stock_item = CustomerStock.query.get_or_404(stock_item_id)
            quantity_ordered = int(request.form.get('quantity_delivered', 0))
            
            if quantity_ordered > stock_item.current_stock:
                flash('Cannot order more than available stock', 'danger')
                return redirect(url_for('main.branded_stock'))
            
            transaction = StockTransaction(
                stock_item_id=stock_item_id,
                transaction_type='stock_out',
                quantity=quantity_ordered,
                reference=request.form.get('order_reference', ''),
                notes=request.form.get('order_notes', ''),
                created_by=current_user.id
            )
            
            stock_item.current_stock -= quantity_ordered
            stock_item.updated_at = datetime.now()
            
            db.session.add(transaction)
            
            form_data = {
                'customer_account': request.form.get('customer_account'),
                'customer_name': request.form.get('customer_name'),
                'product_code': request.form.get('product_code'),
                'product_name': request.form.get('product_name'),
                'quantity_delivered': quantity_ordered,
                'current_stock': stock_item.current_stock,
                'order_reference': request.form.get('order_reference', ''),
                'order_notes': request.form.get('order_notes', ''),
                'transaction_type': 'Customer Stock Order'
            }
            
            new_form = Form(
                type='branded_stock',
                data=json.dumps(form_data),
                user_id=current_user.id
            )
            db.session.add(new_form)
            db.session.commit()
            
            flash(f'Stock order #{new_form.id} has been processed successfully!', 'success')
            
            # Return JavaScript to open print form and redirect
            return f'''
            <script>
                window.open('{url_for('main.print_form', form_id=new_form.id)}', '_blank');
                window.location.href = '{url_for('main.branded_stock')}';
            </script>
            '''
    
    # GET request - display the form
    stock_items = CustomerStock.query.join(Customer).order_by(Customer.name, CustomerStock.product_name).all()
    
    recent_forms = Form.query.filter_by(type='branded_stock').order_by(Form.date_created.desc()).limit(5).all()
    recent_branded_stock = []
    
    for form_entry in recent_forms:
        form_dict = {
            'id': form_entry.id,
            'date_created': form_entry.date_created,
            'data': json.loads(form_entry.data)
        }
        recent_branded_stock.append(form_dict)
    
    return render_template('branded_stock.html', 
                         title='Customer Stock Orders', 
                         form=form,
                         stock_items=stock_items,
                         recent_branded_stock=recent_branded_stock)

@main.route('/invoice-correction', methods=['GET', 'POST'])
@login_required
def invoice_correction():
    form = InvoiceCorrectionForm()
    if form.validate_on_submit():
        form_data = {
            'invoice_number': form.invoice_number.data,
            'customer_account': form.customer_account.data,
            'product_code': form.product_code.data,
            'ordered_quantity': form.ordered_quantity.data,
            'delivered_quantity': form.delivered_quantity.data,
            'notes': form.notes.data
        }
        
        new_form = Form(
            type='Invoiced Goods, Delivery Only',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash('Invoice correction recorded successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('invoice_correction.html', title='Invoiced Goods, Delivery Only', form=form)

@main.route('/special-order', methods=['GET', 'POST'])
@login_required
def special_order():
    form = SpecialOrderForm()
    if form.validate_on_submit():
        form_data = {
            'supplier': form.supplier.data,
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'product_code': form.product_code.data,
            'product_description': form.product_description.data,
            'quantity': form.quantity.data,
            'cost_price' : form.cost_price.data,
            'sell_price' : form.sell_price.data,
            'notes': form.notes.data
        }
        
        new_form = Form(
            type='special_order',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash('Special order request submitted successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('special_order.html', title='Special Order', form=form)

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


@main.route('/customers/import', methods=['GET', 'POST'])
@login_required
def import_customers():
    """Page for importing customers from CSV/Excel file"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
            try:
                import pandas as pd
                
                # Read the file
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
                # Expected columns: 'account_number' and 'name' (or similar)
                # Normalize column names
                df.columns = df.columns.str.lower().str.replace(' ', '_')
                
                # Check for required columns
                if 'account_number' not in df.columns and 'account' not in df.columns:
                    flash('File must contain an "account_number" or "account" column', 'danger')
                    return redirect(request.url)
                
                if 'name' not in df.columns and 'customer_name' not in df.columns:
                    flash('File must contain a "name" or "customer_name" column', 'danger')
                    return redirect(request.url)
                
                # Rename columns if needed
                if 'account' in df.columns:
                    df.rename(columns={'account': 'account_number'}, inplace=True)
                if 'customer_name' in df.columns:
                    df.rename(columns={'customer_name': 'name'}, inplace=True)
                
                # Import customers
                imported = 0
                skipped = 0
                
                for _, row in df.iterrows():
                    account_number = str(row['account_number']).strip()
                    name = str(row['name']).strip()
                    
                    if not account_number or not name:
                        skipped += 1
                        continue
                    
                    # Check if customer already exists
                    existing = Customer.query.filter_by(account_number=account_number).first()
                    if existing:
                        # Update existing customer
                        existing.name = name
                        if 'contact_name' in row and pd.notna(row['contact_name']):
                            existing.contact_name = str(row['contact_name']).strip()
                        if 'phone' in row and pd.notna(row['phone']):
                            existing.phone = str(row['phone']).strip()
                        if 'email' in row and pd.notna(row['email']):
                            existing.email = str(row['email']).strip()
                        if 'address' in row and pd.notna(row['address']):
                            existing.address = str(row['address']).strip()
                    else:
                        # Create new customer
                        customer = Customer(
                            account_number=account_number,
                            name=name,
                            contact_name=str(row.get('contact_name', '')).strip() if 'contact_name' in row and pd.notna(row.get('contact_name')) else None,
                            phone=str(row.get('phone', '')).strip() if 'phone' in row and pd.notna(row.get('phone')) else None,
                            email=str(row.get('email', '')).strip() if 'email' in row and pd.notna(row.get('email')) else None,
                            address=str(row.get('address', '')).strip() if 'address' in row and pd.notna(row.get('address')) else None
                        )
                        db.session.add(customer)
                        imported += 1
                
                db.session.commit()
                flash(f'Successfully imported {imported} customers ({skipped} skipped)', 'success')
                return redirect(url_for('main.callsheets'))
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            flash('Please upload a CSV or Excel file', 'danger')
            return redirect(request.url)
    
    return render_template('import_customers.html', title='Import Customers')

@main.route('/customer-stock')
@login_required
def customer_stock():
    # Get all customer stock with low stock alerts
    stock_items = CustomerStock.query.join(Customer).order_by(Customer.name, CustomerStock.product_name).all()
    low_stock_items = [item for item in stock_items if item.current_stock <= item.reorder_level]
    
    return render_template(
        'customer_stock.html',
        title='Customer Stock Management',
        stock_items=stock_items,
        low_stock_count=len(low_stock_items)
    )

@main.route('/api/customer-stock', methods=['POST'])
@login_required
def create_customer_stock():
    data = request.json
    
    try:
        # Product name is required, but product_code is optional
        if not data.get('product_name'):
            return jsonify({'success': False, 'message': 'Product name is required'}), 400
            
        # Check if this customer already has this product (by product code if provided, otherwise by name)
        if data.get('product_code'):
            existing = CustomerStock.query.filter_by(
                customer_id=data['customer_id'],
                product_code=data['product_code']
            ).first()
        else:
            existing = CustomerStock.query.filter_by(
                customer_id=data['customer_id'],
                product_name=data['product_name']
            ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'This customer already has this product in stock'}), 400
        
        stock_item = CustomerStock(
            customer_id=data['customer_id'],
            product_code=data.get('product_code'),  # Optional
            product_name=data['product_name'],
            current_stock=data.get('initial_stock', 0),
            reorder_level=data.get('reorder_level', 5)
        )
        
        db.session.add(stock_item)
        db.session.flush()
        
        # Create initial stock transaction if there's initial stock
        if data.get('initial_stock', 0) > 0:
            transaction = StockTransaction(
                stock_item_id=stock_item.id,
                transaction_type='stock_in',
                quantity=data['initial_stock'],
                reference=data.get('invoice_number', 'Initial Stock'),  # Changed from 'reference'
                notes=data.get('notes', 'Initial stock setup'),
                created_by=current_user.id
            )
            db.session.add(transaction)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Stock item created successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/customer-stock/<int:stock_id>/transaction', methods=['POST'])
@login_required
def create_stock_transaction(stock_id):
    stock_item = CustomerStock.query.get_or_404(stock_id)
    data = request.json
    
    try:
        transaction_type = data['transaction_type']
        quantity = int(data['quantity'])
        
        # Create the transaction
        transaction = StockTransaction(
            stock_item_id=stock_id,
            transaction_type=transaction_type,
            quantity=quantity,
            reference=data.get('reference', ''),
            notes=data.get('notes', ''),
            created_by=current_user.id
        )
        
        # Update stock levels
        if transaction_type == 'stock_in':
            stock_item.current_stock += quantity
        elif transaction_type == 'stock_out':
            if stock_item.current_stock < quantity:
                return jsonify({'success': False, 'message': 'Insufficient stock available'}), 400
            stock_item.current_stock -= quantity
        elif transaction_type == 'adjustment':
            # For adjustments, quantity can be positive or negative
            new_stock = stock_item.current_stock + quantity
            if new_stock < 0:
                return jsonify({'success': False, 'message': 'Cannot adjust to negative stock'}), 400
            stock_item.current_stock = new_stock
        
        stock_item.updated_at = datetime.now()
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Stock {transaction_type.replace("_", " ")} recorded successfully',
            'new_stock_level': stock_item.current_stock
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/customer-stock/<int:stock_id>/history')
@login_required
def get_stock_history(stock_id):
    stock_item = CustomerStock.query.get_or_404(stock_id)
    transactions = StockTransaction.query.filter_by(stock_item_id=stock_id)\
        .order_by(StockTransaction.transaction_date.desc()).all()
    
    return jsonify([transaction.to_dict() for transaction in transactions])

@main.route('/api/customer-stock/search')
@login_required
def search_customer_stock():
    customer_id = request.args.get('customer_id')
    query = request.args.get('q', '').strip()
    
    stock_query = CustomerStock.query.join(Customer)
    
    if customer_id:
        stock_query = stock_query.filter(CustomerStock.customer_id == customer_id)
    
    if query:
        stock_query = stock_query.filter(
            db.or_(
                CustomerStock.product_code.ilike(f'%{query}%'),
                CustomerStock.product_name.ilike(f'%{query}%'),
                Customer.name.ilike(f'%{query}%')
            )
        )
    
    stock_items = stock_query.limit(20).all()
    return jsonify([item.to_dict() for item in stock_items])



@main.route('/standing-orders')
@login_required
def standing_orders():
    # Get all standing orders
    orders = StandingOrder.query.join(Customer).filter(
        StandingOrder.status != 'ended'
    ).order_by(Customer.name).all()
    
    # Get today's standing orders
    today = date.today()
    today_day = today.weekday()  # 0 = Monday, 6 = Sunday
    
    todays_orders = []
    for order in orders:
        if order.status == 'active' and str(today_day) in order.delivery_days.split(','):
            # Check if there's a schedule for today
            schedule = StandingOrderSchedule.query.filter_by(
                standing_order_id=order.id,
                scheduled_date=today
            ).first()
            
            todays_orders.append({
                'order': order,
                'schedule': schedule,
                'status': schedule.status if schedule else 'pending'
            })
    
    # Get statistics
    active_count = len([o for o in orders if o.status == 'active'])
    paused_count = len([o for o in orders if o.status == 'paused'])
    
    # Get this week's pending schedules
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    pending_this_week = StandingOrderSchedule.query.filter(
        StandingOrderSchedule.scheduled_date.between(week_start, week_end),
        StandingOrderSchedule.status == 'pending'
    ).count()
    
    return render_template('standing_orders.html',
                         orders=orders,
                         todays_orders=todays_orders,
                         today=today,
                         active_count=active_count,
                         paused_count=paused_count,
                         pending_this_week=pending_this_week)

# Update your standing order creation route in routes.py
@main.route('/standing-orders/new', methods=['GET', 'POST'])
@login_required
def new_standing_order():
    if request.method == 'POST':
        data = request.json
        
        try:
            # Validate delivery days (no weekends)
            delivery_days = data.get('delivery_days', [])
            weekend_days = [day for day in delivery_days if int(day) >= 5]
            if weekend_days:
                return jsonify({
                    'success': False, 
                    'message': 'Weekend deliveries are not supported. Please select Monday through Friday only.'
                }), 400
            
            # Create standing order
            standing_order = StandingOrder(
    customer_id=data['customer_id'],
    delivery_days=','.join([day for day in data['delivery_days'] if int(day) < 5]),
    # ADD THIS LINE:
    start_date=date.today(),  # Use today as the start date
    end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
    special_instructions=data.get('special_instructions', ''),
    created_by=current_user.id
)
            
            db.session.add(standing_order)
            db.session.flush()
            
            # Add items
            for item in data['items']:
                order_item = StandingOrderItem(
                    standing_order_id=standing_order.id,
                    product_code=item['product_code'],
                    product_name=item['product_name'],
                    quantity=item['quantity'],
                    unit_type=item.get('unit_type', 'units'),
                    special_notes=item.get('notes', '')
                )
                db.session.add(order_item)
            
            # Log creation
            log = StandingOrderLog(
                standing_order_id=standing_order.id,
                action_type='created',
                action_details=json.dumps({'customer': data.get('customer_name', ''), 'items_count': len(data['items'])}),
                performed_by=current_user.id
            )
            db.session.add(log)
            
            # Generate initial schedules for the first month (weekdays only)
            generate_schedules_for_order(standing_order.id)
            
            db.session.commit()
            
            return jsonify({'success': True, 'id': standing_order.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    
    # GET request - show form
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('standing_order_form.html', customers=customers)


@main.route('/standing-orders/<int:order_id>')
@login_required
def view_standing_order(order_id):
    order = StandingOrder.query.get_or_404(order_id)
    
    # Get schedules for current month
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    
    schedules = StandingOrderSchedule.query.filter(
        StandingOrderSchedule.standing_order_id == order_id,
        StandingOrderSchedule.scheduled_date.between(month_start, month_end)
    ).order_by(StandingOrderSchedule.scheduled_date).all()
    
    # Get logs
    logs = StandingOrderLog.query.filter_by(
        standing_order_id=order_id
    ).order_by(StandingOrderLog.performed_at.desc()).limit(20).all()
    
    return render_template('standing_order_detail.html',
                         order=order,
                         schedules=schedules,
                         logs=logs,
                         today=today)

@main.route('/standing-orders/<int:order_id>/pause', methods=['POST'])
@login_required
def pause_standing_order(order_id):
    order = StandingOrder.query.get_or_404(order_id)
    
    try:
        order.status = 'paused'
        order.updated_at = datetime.now()
        
        # Log the action
        log = StandingOrderLog(
            standing_order_id=order_id,
            action_type='paused',
            action_details=json.dumps({'reason': request.json.get('reason', '')}),
            performed_by=current_user.id
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Standing order paused'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/<int:order_id>/resume', methods=['POST'])
@login_required
def resume_standing_order(order_id):
    order = StandingOrder.query.get_or_404(order_id)
    
    try:
        order.status = 'active'
        order.updated_at = datetime.now()
        
        # Log the action
        log = StandingOrderLog(
            standing_order_id=order_id,
            action_type='resumed',
            action_details='{}',
            performed_by=current_user.id
        )
        db.session.add(log)
        
        # Generate schedules for the next month
        generate_schedules_for_order(order_id)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Standing order resumed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/<int:order_id>/end', methods=['POST'])
@login_required
def end_standing_order(order_id):
    order = StandingOrder.query.get_or_404(order_id)
    
    try:
        order.status = 'ended'
        order.end_date = date.today()
        order.updated_at = datetime.now()
        
        # Cancel all future schedules
        future_schedules = StandingOrderSchedule.query.filter(
            StandingOrderSchedule.standing_order_id == order_id,
            StandingOrderSchedule.scheduled_date > date.today(),
            StandingOrderSchedule.status == 'pending'
        ).all()
        
        for schedule in future_schedules:
            schedule.status = 'skipped'
            schedule.notes = 'Standing order ended'
        
        # Log the action
        log = StandingOrderLog(
            standing_order_id=order_id,
            action_type='ended',
            action_details=json.dumps({'end_date': str(date.today())}),
            performed_by=current_user.id
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Standing order ended'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/schedule/<int:schedule_id>/complete', methods=['POST'])
@login_required
def complete_schedule(schedule_id):
    schedule = StandingOrderSchedule.query.get_or_404(schedule_id)
    
    try:
        schedule.status = 'created'
        schedule.order_created_date = datetime.now()
        schedule.order_created_by = current_user.id
        schedule.order_reference = request.json.get('reference', '')
        schedule.notes = request.json.get('notes', '')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order marked as created'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/schedule/<int:schedule_id>/skip', methods=['POST'])
@login_required
def skip_schedule(schedule_id):
    schedule = StandingOrderSchedule.query.get_or_404(schedule_id)
    
    try:
        schedule.status = 'skipped'
        schedule.notes = request.json.get('reason', 'Manually skipped')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order skipped'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/generate-schedules', methods=['POST'])
@login_required
def generate_all_schedules():
    """Generate schedules for all active standing orders for the next month"""
    try:
        active_orders = StandingOrder.query.filter_by(status='active').all()
        count = 0
        
        for order in active_orders:
            count += generate_schedules_for_order(order.id)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Generated {count} new schedules'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/standing-orders/schedule-view')
@login_required
def schedule_view():
    """Monthly/weekly/daily schedule view"""
    view_type = request.args.get('view', 'month')  # month, week, or day
    target_date = request.args.get('date', str(date.today()))
    
    try:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    except:
        target_date = date.today()
    
    if view_type == 'day':
        start_date = target_date
        end_date = target_date
    elif view_type == 'week':
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:  # month
        start_date = date(target_date.year, target_date.month, 1)
        end_date = date(target_date.year, target_date.month, calendar.monthrange(target_date.year, target_date.month)[1])
    
    # Get schedules in date range
    schedules = StandingOrderSchedule.query.join(StandingOrder).join(Customer).filter(
        StandingOrderSchedule.scheduled_date.between(start_date, end_date)
    ).order_by(StandingOrderSchedule.scheduled_date, Customer.name).all()
    
    # Group by date
    schedules_by_date = {}
    for schedule in schedules:
        date_key = schedule.scheduled_date
        if date_key not in schedules_by_date:
            schedules_by_date[date_key] = []
        schedules_by_date[date_key].append(schedule)
    
    # Calculate completion stats
    total = len(schedules)
    completed = len([s for s in schedules if s.status == 'created'])
    pending = len([s for s in schedules if s.status == 'pending'])
    skipped = len([s for s in schedules if s.status == 'skipped'])
    
    return render_template('standing_order_schedule.html',
                         view_type=view_type,
                         target_date=target_date,
                         start_date=start_date,
                         end_date=end_date,
                         schedules_by_date=schedules_by_date,
                         total=total,
                         completed=completed,
                         pending=pending,
                         skipped=skipped)

def generate_schedules_for_order(order_id, months_ahead=1):
    """Generate schedule entries for a standing order (Monday-Friday only)"""
    order = StandingOrder.query.get(order_id)
    if not order or order.status != 'active':
        return 0
    
    count = 0
    today = date.today()
    end_date = today + timedelta(days=30 * months_ahead)
    
    if order.end_date and order.end_date < end_date:
        end_date = order.end_date
    
    current_date = max(order.start_date, today)
    delivery_days = order.get_delivery_days_list()
    
    # Filter out weekends (5=Saturday, 6=Sunday)
    weekday_delivery_days = [day for day in delivery_days if day < 5]
    
    while current_date <= end_date:
        # Only check weekdays (0=Monday through 4=Friday)
        if current_date.weekday() in weekday_delivery_days:
            # Check if schedule already exists
            existing = StandingOrderSchedule.query.filter_by(
                standing_order_id=order_id,
                scheduled_date=current_date
            ).first()
            
            if not existing:
                schedule = StandingOrderSchedule(
                    standing_order_id=order_id,
                    scheduled_date=current_date,
                    status='pending'
                )
                db.session.add(schedule)
                count += 1
        
        current_date += timedelta(days=1)
    
    return count

@main.route('/standing-orders/<int:order_id>/print')
@login_required
def print_standing_order(order_id):
    """Print standing order details"""
    order = StandingOrder.query.get_or_404(order_id)
    
    # Get current month schedules
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    
    schedules = StandingOrderSchedule.query.filter(
        StandingOrderSchedule.standing_order_id == order_id,
        StandingOrderSchedule.scheduled_date.between(month_start, month_end)
    ).order_by(StandingOrderSchedule.scheduled_date).all()
    
    return render_template(
        'print_standing_order.html',
        order=order,
        schedules=schedules,
        today=today
    )

@main.route('/standing-orders/schedule-view/print')
@login_required
def print_schedule_view():
    """Print schedule view"""
    view_type = request.args.get('view', 'month')
    target_date = request.args.get('date', str(date.today()))
    
    try:
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    except:
        target_date = date.today()
    
    if view_type == 'day':
        start_date = target_date
        end_date = target_date
    elif view_type == 'week':
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:  # month
        start_date = date(target_date.year, target_date.month, 1)
        end_date = date(target_date.year, target_date.month, calendar.monthrange(target_date.year, target_date.month)[1])
    
    # Get schedules in date range
    schedules = StandingOrderSchedule.query.join(StandingOrder).join(Customer).filter(
        StandingOrderSchedule.scheduled_date.between(start_date, end_date)
    ).order_by(StandingOrderSchedule.scheduled_date, Customer.name).all()
    
    # Group by date
    schedules_by_date = {}
    for schedule in schedules:
        date_key = schedule.scheduled_date
        if date_key not in schedules_by_date:
            schedules_by_date[date_key] = []
        schedules_by_date[date_key].append(schedule)
    
    # Calculate completion stats
    total = len(schedules)
    completed = len([s for s in schedules if s.status == 'created'])
    pending = len([s for s in schedules if s.status == 'pending'])
    skipped = len([s for s in schedules if s.status == 'skipped'])
    
    return render_template(
        'print_schedule_view.html',
        view_type=view_type,
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        schedules_by_date=schedules_by_date,
        total=total,
        completed=completed,
        pending=pending,
        skipped=skipped
    )

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
                'link': url_for('main.callsheets'),
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
                    'link': url_for('main.callsheets'),
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
                'link': url_for('main.callsheets'),
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
                'link': url_for('main.view_standing_order', order_id=order.id),
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
                'link': url_for('main.view_standing_order', order_id=log.standing_order_id),
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
                'link': url_for('main.customer_stock'),
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


