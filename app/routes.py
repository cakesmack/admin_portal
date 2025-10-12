"""
Main Routes - Core application routes
Includes: Dashboard, User Management, Todos, Activity Feed, Products
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import (User, Customer, CallsheetEntry, Form, Callsheet, CallsheetArchive,
                        TodoItem, CompanyUpdate, StandingOrder, StandingOrderLog,
                        StockTransaction, Product)
from app.forms import CreateUserForm, EditUserForm
from functools import wraps
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

# Sample data for demonstration (backwards compatibility)
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


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ====================  CORE ROUTES ====================

@main.route('/')
def index():
    """Root route - redirect to dashboard or login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
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


# ==================== USER MANAGEMENT ====================

@main.route('/users')
@login_required
@admin_required
def users():
    """List all users"""
    users = User.query.order_by(User.full_name).all()
    return render_template('users.html', title='User Management', users=users)


@main.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    """Create a new user"""
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
            logger.error(f"Error creating user: {e}", exc_info=True)
            flash(f'Error creating user: {str(e)}', 'danger')
            return render_template('user_form.html', form=form, title='Create New User')

    return render_template('user_form.html', form=form, title='Create New User')


@main.route('/users/<int:user_id>')
@login_required
def user_profile(user_id):
    """View user profile"""
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
    """Edit user details"""
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
    """Reset user password (admin only)"""
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
        logger.error(f"Error resetting password for user {user_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/staff-contacts')
@login_required
def get_staff_contacts():
    """Get all active staff contacts"""
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
        logger.error(f"Error fetching staff contacts: {e}", exc_info=True)
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


# ==================== TODO MANAGEMENT ====================

@main.route('/api/todos', methods=['GET'])
@login_required
def get_todos():
    """Get user's todo items"""
    try:
        todos = TodoItem.query.filter_by(user_id=current_user.id).order_by(TodoItem.created_at.desc()).all()
        return jsonify([{
            'id': todo.id,
            'text': todo.text,
            'completed': todo.completed,
            'created_at': todo.created_at.isoformat()
        } for todo in todos])
    except Exception as e:
        logger.error(f"Error fetching todos: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@main.route('/api/todos', methods=['POST'])
@login_required
def create_todo():
    """Create a new todo item"""
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
        logger.error(f"Error creating todo: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@login_required
def toggle_todo(todo_id):
    """Toggle todo completed status"""
    try:
        todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
        todo.completed = not todo.completed
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling todo {todo_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@login_required
def delete_todo(todo_id):
    """Delete a todo item"""
    try:
        todo = TodoItem.query.filter_by(id=todo_id, user_id=current_user.id).first_or_404()
        db.session.delete(todo)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting todo {todo_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


# ==================== PRODUCT API (LEGACY) ====================

@main.route('/api/customers')
@login_required
def api_customers():
    """Legacy API for sample customers"""
    return jsonify(SAMPLE_CUSTOMERS)


@main.route('/api/products')
@login_required
def api_products():
    """Legacy API for sample products"""
    return jsonify(SAMPLE_PRODUCTS)


@main.route('/api/products/search')
@login_required
def search_products():
    """Search products by code, name, or description"""
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
        logger.error(f"Error searching products: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== ACTIVITY FEED ====================

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
                'link': url_for('forms.view_form', form_id=form.id),
                'icon': 'bi-file-text'
            })
    except Exception as e:
        logger.error(f"Error loading recent forms: {e}", exc_info=True)

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
                    'link': url_for('forms.view_form', form_id=form.id),
                    'icon': 'bi-check-circle'
                })
    except Exception as e:
        logger.error(f"Error loading completed forms: {e}", exc_info=True)

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
        logger.error(f"Error loading company updates: {e}", exc_info=True)

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
        logger.error(f"Error loading recent callsheets: {e}", exc_info=True)

    try:
        # Recent customers added to callsheets (by any user)
        recent_callsheet_additions = CallsheetEntry.query.join(
            User, CallsheetEntry.user_id == User.id
        ).join(
            Customer, CallsheetEntry.customer_id == Customer.id
        ).join(
            Callsheet, CallsheetEntry.callsheet_id == Callsheet.id
        ).order_by(CallsheetEntry.id.desc()).limit(5).all()

        for entry in recent_callsheet_additions:
            # Only show if this was recently created (within last few days)
            if (datetime.now() - entry.callsheet.created_at).days <= 7:
                activities.append({
                    'type': 'callsheet_customer_added',
                    'description': f'Added {entry.customer.name} to callsheet "{entry.callsheet.name}"',
                    'user': User.query.get(entry.user_id).username,
                    'timestamp': entry.callsheet.created_at,
                    'link': url_for('callsheets.callsheets'),
                    'icon': 'bi-person-plus'
                })
    except Exception as e:
        logger.error(f"Error loading callsheet customer additions: {e}", exc_info=True)

    try:
        # Recent callsheet call activity (status changes)
        recent_callsheet_calls = CallsheetEntry.query.filter(
            CallsheetEntry.call_status != 'not_called',
            CallsheetEntry.updated_at.isnot(None)
        ).join(User, CallsheetEntry.user_id == User.id).join(Customer, CallsheetEntry.customer_id == Customer.id).order_by(CallsheetEntry.updated_at.desc()).limit(5).all()

        for entry in recent_callsheet_calls:
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
        logger.error(f"Error loading callsheet call activity: {e}", exc_info=True)

    try:
        # Recent standing order creation
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
        logger.error(f"Error loading standing orders: {e}", exc_info=True)

    try:
        # Recent standing order actions (pause, resume, end)
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
        logger.error(f"Error loading standing order logs: {e}", exc_info=True)

    try:
        # Recent customer stock transactions
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
        logger.error(f"Error loading stock transactions: {e}", exc_info=True)

    # Sort all activities by timestamp and limit to 15
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    activities = activities[:15]

    # Convert timestamps to ISO format for JavaScript
    for activity in activities:
        if hasattr(activity['timestamp'], 'isoformat'):
            activity['timestamp'] = activity['timestamp'].isoformat()

    return jsonify(activities)
    