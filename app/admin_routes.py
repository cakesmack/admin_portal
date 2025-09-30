"""
Admin routes for reports and analytics
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import (User, Customer, Form, CallsheetEntry, Callsheet, StandingOrder, 
                       StandingOrderLog, StockTransaction, CustomerStock, CompanyUpdate)
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, extract, case, and_

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            from flask import flash, redirect, url_for
            flash('Admin access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with overview stats"""
    return render_template('admin/dashboard.html', title='Admin Dashboard')

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    """Main reports page"""
    return render_template('admin/reports.html', title='Admin Reports')

@admin_bp.route('/api/reports/summary')
@login_required
@admin_required
def get_report_summary():
    """Get overall summary statistics"""
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    
    # Add 1 day to end_date to make it inclusive for datetime comparisons
    end_date_inclusive = end_date + timedelta(days=1)
    
    # Total forms created
    total_forms = Form.query.filter(
        Form.date_created >= start_date,
        Form.date_created < end_date_inclusive
    ).count()
    
    completed_forms = Form.query.filter(
        Form.date_created >= start_date,
        Form.date_created < end_date_inclusive,
        Form.is_completed == True
    ).count()
    
    # Forms by type
    forms_by_type = db.session.query(
        Form.type,
        func.count(Form.id)
    ).filter(
        Form.date_created >= start_date,
        Form.date_created < end_date_inclusive
    ).group_by(Form.type).all()
    
    # Standing orders
    active_standing_orders = StandingOrder.query.filter_by(status='active').count()
    paused_standing_orders = StandingOrder.query.filter_by(status='paused').count()
    
    standing_orders_created = StandingOrder.query.filter(
        StandingOrder.created_at >= start_date,
        StandingOrder.created_at < end_date_inclusive
    ).count()
    
    # Stock transactions
    stock_transactions = StockTransaction.query.filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date <= end_date.date()
    ).count()
    
    stock_by_type = db.session.query(
        StockTransaction.transaction_type,
        func.count(StockTransaction.id)
    ).filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date <= end_date.date()
    ).group_by(StockTransaction.transaction_type).all()
    
    # Callsheet statistics - Get entries from callsheets in the date range
    # Build list of all month/year combinations in the date range
    months_in_range = []
    current = start_date
    while current < end_date_inclusive:
        if (current.month, current.year) not in months_in_range:
            months_in_range.append((current.month, current.year))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)
    
    # Get all callsheet IDs for months in range
    callsheet_ids = []
    for month, year in months_in_range:
        month_callsheets = Callsheet.query.filter(
            Callsheet.year == year,
            Callsheet.month == month,
            Callsheet.is_active == True
        ).all()
        callsheet_ids.extend([c.id for c in month_callsheets])
    
    # Get entries from those callsheets
    callsheet_entries_total = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).count() if callsheet_ids else 0
    
    callsheet_by_status = db.session.query(
        CallsheetEntry.call_status,
        func.count(CallsheetEntry.id)
    ).filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).group_by(CallsheetEntry.call_status).all() if callsheet_ids else []
    
    # Company updates
    company_updates = CompanyUpdate.query.filter(
        CompanyUpdate.created_at >= start_date,
        CompanyUpdate.created_at < end_date_inclusive
    ).count()
    
    # User activity
    active_users = db.session.query(User.id).filter(
        User.last_login >= start_date
    ).distinct().count()
    
    return jsonify({
        'period': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        },
        'forms': {
            'total': total_forms,
            'completed': completed_forms,
            'pending': total_forms - completed_forms,
            'completion_rate': round((completed_forms / total_forms * 100) if total_forms > 0 else 0, 1),
            'by_type': [{'type': t[0], 'count': t[1]} for t in forms_by_type]
        },
        'standing_orders': {
            'active': active_standing_orders,
            'paused': paused_standing_orders,
            'created_this_period': standing_orders_created
        },
        'stock': {
            'total_transactions': stock_transactions,
            'by_type': [{'type': t[0], 'count': t[1]} for t in stock_by_type]
        },
        'callsheets': {
            'total_entries': callsheet_entries_total,
            'by_status': [{'status': t[0], 'count': t[1]} for t in callsheet_by_status]
        },
        'company_updates': company_updates,
        'active_users': active_users
    })

@admin_bp.route('/api/reports/daily-activity')
@login_required
@admin_required
def get_daily_activity():
    """Get daily activity breakdown for charts"""
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date = end_date + timedelta(days=1)
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
    
    # Forms created by day
    forms_by_day = db.session.query(
        func.date(Form.date_created).label('date'),
        func.count(Form.id).label('count')
    ).filter(
        Form.date_created >= start_date,
        Form.date_created < end_date
    ).group_by(func.date(Form.date_created)).all()
    
    # Stock transactions by day
    stock_by_day = db.session.query(
        StockTransaction.transaction_date.label('date'),
        func.count(StockTransaction.id).label('count')
    ).filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date < end_date.date()
    ).group_by(StockTransaction.transaction_date).all()
    
    # Callsheet updates by day - use updated_at
    callsheet_by_day = db.session.query(
        func.date(CallsheetEntry.updated_at).label('date'),
        func.count(CallsheetEntry.id).label('count')
    ).filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(func.date(CallsheetEntry.updated_at)).all()
    
    # Create a date range
    date_range = []
    current = start_date.date()
    while current < end_date.date():
        date_range.append(current)
        current += timedelta(days=1)
    
    # Build response with all dates
    daily_data = []
    for date_obj in date_range:
        forms_count = next((d.count for d in forms_by_day if str(d.date) == str(date_obj)), 0)
        stock_count = next((d.count for d in stock_by_day if d.date == date_obj), 0)
        callsheet_count = next((d.count for d in callsheet_by_day if str(d.date) == str(date_obj)), 0)
        
        daily_data.append({
            'date': date_obj.strftime('%Y-%m-%d'),
            'forms': forms_count,
            'stock': stock_count,
            'callsheets': callsheet_count,
            'total': forms_count + stock_count + callsheet_count
        })
    
    return jsonify(daily_data)

@admin_bp.route('/api/reports/user-activity')
@login_required
@admin_required
def get_user_activity():
    """Get activity breakdown by user"""
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date_inclusive = end_date + timedelta(days=1)
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date_inclusive = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date_inclusive = start_date.replace(month=start_date.month + 1)
    
    # Get all users with their activity
    users = User.query.all()
    user_activity = []
    
    for user in users:
        # Forms created by user
        forms_created = Form.query.filter(
            Form.date_created >= start_date,
            Form.date_created < end_date_inclusive,
            Form.user_id == user.id
        ).count()
        
        # Callsheet calls made by user
        calls_made = CallsheetEntry.query.filter(
            CallsheetEntry.updated_at >= start_date,
            CallsheetEntry.updated_at < end_date_inclusive,
            CallsheetEntry.user_id == user.id,
            CallsheetEntry.call_status != 'not_called'
        ).count()
        
        # Stock transactions by user
        stock_transactions = StockTransaction.query.filter(
            StockTransaction.transaction_date >= start_date.date(),
            StockTransaction.transaction_date <= end_date.date(),
            StockTransaction.user_id == user.id
        ).count()
        
        total_activity = forms_created + calls_made + stock_transactions
        
        if total_activity > 0:
            user_activity.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'forms_created': forms_created,
                'calls_made': calls_made,
                'stock_transactions': stock_transactions,
                'total_activity': total_activity
            })
    
    user_activity.sort(key=lambda x: x['total_activity'], reverse=True)
    
    return jsonify(user_activity)

@admin_bp.route('/api/reports/inactive-customers')
@login_required
@admin_required
def get_inactive_customers():
    """Get customers who haven't been contacted recently"""
    
    days = request.args.get('days', default=30, type=int)
    cutoff_date = datetime.now() - timedelta(days=days)
    
    all_customers = Customer.query.all()
    inactive_customers = []
    
    for customer in all_customers:
        # Get most recent callsheet entry for this customer
        last_entry = CallsheetEntry.query.filter(
            CallsheetEntry.customer_id == customer.id,
            CallsheetEntry.updated_at.isnot(None)
        ).order_by(CallsheetEntry.updated_at.desc()).first()
        
        # If no entry or entry is older than cutoff, they're inactive
        if not last_entry or last_entry.updated_at < cutoff_date:
            days_since_contact = (datetime.now() - last_entry.updated_at).days if last_entry else 999
            
            inactive_customers.append({
                'id': customer.id,
                'name': customer.name,
                'account_number': customer.account_number,
                'phone': customer.phone,
                'email': customer.email,
                'last_contact': last_entry.updated_at.isoformat() if last_entry else None,
                'days_since_contact': days_since_contact,
                'last_status': last_entry.get_status_display() if last_entry else None
            })
    
    inactive_customers.sort(key=lambda x: x['days_since_contact'], reverse=True)
    
    return jsonify(inactive_customers)

@admin_bp.route('/api/reports/callsheet-analytics')
@login_required
@admin_required
def get_callsheet_analytics():
    """Get detailed callsheet analytics - USES CALLSHEET MONTH/YEAR"""
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    
    # Build list of all month/year combinations in the date range
    months_in_range = []
    current = start_date
    while current <= end_date:
        months_in_range.append((current.month, current.year))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # Get callsheets for all months in the range
    callsheets = []
    for month, year in months_in_range:
        month_callsheets = Callsheet.query.filter(
            Callsheet.year == year,
            Callsheet.month == month,
            Callsheet.is_active == True
        ).all()
        callsheets.extend(month_callsheets)
    
    callsheet_ids = [c.id for c in callsheets]
    
    if not callsheet_ids:
        return jsonify({
            'order_success_rate': 0,
            'no_answer_rate': 0,
            'decline_rate': 0,
            'callback_rate': 0,
            'daily_success_rate': [],
            'day_performance': {},
            'staff_performance': [],
            'most_responsive': [],
            'hard_to_reach': [],
            'frequent_decliners': [],
            'pending_callbacks': []
        })
    
    # Overall call status rates
    total_calls = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).count()
    
    if total_calls == 0:
        return jsonify({
            'order_success_rate': 0,
            'no_answer_rate': 0,
            'decline_rate': 0,
            'callback_rate': 0,
            'daily_success_rate': [],
            'day_performance': {},
            'staff_performance': [],
            'most_responsive': [],
            'hard_to_reach': [],
            'frequent_decliners': [],
            'pending_callbacks': []
        })
    
    ordered = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status == 'ordered'
    ).count()
    
    no_answer = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status == 'no_answer'
    ).count()
    
    declined = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status == 'declined'
    ).count()
    
    callback = CallsheetEntry.query.filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status == 'callback'
    ).count()
    
    order_success_rate = round((ordered / total_calls * 100) if total_calls > 0 else 0, 1)
    no_answer_rate = round((no_answer / total_calls * 100) if total_calls > 0 else 0, 1)
    decline_rate = round((declined / total_calls * 100) if total_calls > 0 else 0, 1)
    callback_rate = round((callback / total_calls * 100) if total_calls > 0 else 0, 1)
    
    # Daily success rate trend - NOT APPLICABLE since callsheets are weekly
    daily_success_rate = []
    
    # Performance by day of week
    day_performance = {}
    for callsheet in callsheets:
        day_calls = CallsheetEntry.query.filter(
            CallsheetEntry.callsheet_id == callsheet.id,
            CallsheetEntry.call_status != 'not_called'
        ).count()
        
        day_orders = CallsheetEntry.query.filter(
            CallsheetEntry.callsheet_id == callsheet.id,
            CallsheetEntry.call_status == 'ordered'
        ).count()
        
        if day_calls > 0:
            success_rate = round((day_orders / day_calls * 100), 1)
            if callsheet.day_of_week in day_performance:
                # Average if multiple callsheets for same day
                day_performance[callsheet.day_of_week] = (day_performance[callsheet.day_of_week] + success_rate) / 2
            else:
                day_performance[callsheet.day_of_week] = success_rate
    
    # Staff performance
    staff_data = db.session.query(
        User.id,
        User.username,
        User.full_name,
        func.count(CallsheetEntry.id).label('total'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('ordered')
    ).join(CallsheetEntry, CallsheetEntry.user_id == User.id).filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).group_by(User.id).all()
    
    staff_performance = []
    for row in staff_data:
        success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
        staff_performance.append({
            'id': row.id,
            'username': row.username,
            'full_name': row.full_name,
            'total_calls': row.total,
            'orders': row.ordered,
            'success_rate': success_rate
        })
    
    staff_performance.sort(key=lambda x: x['success_rate'], reverse=True)
    
    # Most responsive customers
    responsive_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('orders')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    most_responsive = []
    for row in responsive_data:
        order_rate = round((row.orders / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if row.orders >= 1:
            most_responsive.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'orders': row.orders,
                'order_rate': order_rate
            })
    
    most_responsive.sort(key=lambda x: x['order_rate'], reverse=True)
    
    # Hard to reach customers
    hard_to_reach_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'no_answer', 1), else_=0)).label('no_answer')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    hard_to_reach = []
    for row in hard_to_reach_data:
        no_answer_rate = round((row.no_answer / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if row.no_answer >= 2:
            hard_to_reach.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'no_answer': row.no_answer,
                'no_answer_rate': no_answer_rate
            })
    
    hard_to_reach.sort(key=lambda x: x['no_answer_rate'], reverse=True)
    
    # Frequent decliners
    decliner_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'declined', 1), else_=0)).label('declined')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.callsheet_id.in_(callsheet_ids),
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    frequent_decliners = []
    for row in decliner_data:
        decline_rate = round((row.declined / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if row.declined >= 1:
            frequent_decliners.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'declined': row.declined,
                'decline_rate': decline_rate
            })
    
    frequent_decliners.sort(key=lambda x: x['decline_rate'], reverse=True)
    
    # Pending callbacks - all current callbacks
    pending_callbacks_entries = CallsheetEntry.query.filter(
        CallsheetEntry.call_status == 'callback'
    ).join(Customer).all()
    
    pending_callbacks = []
    for entry in pending_callbacks_entries:
        pending_callbacks.append({
            'id': entry.customer.id,
            'name': entry.customer.name,
            'account_number': entry.customer.account_number,
            'phone': entry.customer.phone,
            'callback_time': entry.callback_time,
            'notes': entry.customer.callsheet_notes
        })
    
    return jsonify({
        'order_success_rate': order_success_rate,
        'no_answer_rate': no_answer_rate,
        'decline_rate': decline_rate,
        'callback_rate': callback_rate,
        'daily_success_rate': daily_success_rate,
        'day_performance': day_performance,
        'staff_performance': staff_performance[:10],
        'most_responsive': most_responsive[:10],
        'hard_to_reach': hard_to_reach[:10],
        'frequent_decliners': frequent_decliners[:10],
        'pending_callbacks': pending_callbacks
    })

@admin_bp.route('/api/reports/additional-analytics')
@login_required
@admin_required
def get_additional_analytics():
    """Get additional analytics data"""
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date_inclusive = end_date + timedelta(days=1)
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date_inclusive = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date_inclusive = start_date.replace(month=start_date.month + 1)
    
    # Stock movement analytics
    try:
        stock_in = StockTransaction.query.filter(
            StockTransaction.transaction_date >= start_date.date(),
            StockTransaction.transaction_date <= end_date.date(),
            StockTransaction.transaction_type == 'in'
        ).count()
        
        stock_out = StockTransaction.query.filter(
            StockTransaction.transaction_date >= start_date.date(),
            StockTransaction.transaction_date <= end_date.date(),
            StockTransaction.transaction_type == 'out'
        ).count()
    except:
        stock_in = 0
        stock_out = 0
    
    # Standing order analytics
    try:
        so_paused = StandingOrderLog.query.filter(
            StandingOrderLog.created_at >= start_date,
            StandingOrderLog.created_at < end_date_inclusive,
            StandingOrderLog.action == 'paused'
        ).count()
        
        so_resumed = StandingOrderLog.query.filter(
            StandingOrderLog.created_at >= start_date,
            StandingOrderLog.created_at < end_date_inclusive,
            StandingOrderLog.action == 'resumed'
        ).count()
        
        so_ended = StandingOrderLog.query.filter(
            StandingOrderLog.created_at >= start_date,
            StandingOrderLog.created_at < end_date_inclusive,
            StandingOrderLog.action == 'ended'
        ).count()
    except:
        so_paused = 0
        so_resumed = 0
        so_ended = 0
    
    return jsonify({
        'stock': {
            'in': stock_in,
            'out': stock_out,
            'net': stock_in - stock_out
        },
        'standing_orders': {
            'paused': so_paused,
            'resumed': so_resumed,
            'ended': so_ended
        }
    })