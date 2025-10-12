from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import (User, Customer, Form, CallsheetEntry, Callsheet, StandingOrder,
                       StandingOrderLog, StockTransaction, CustomerStock, CompanyUpdate, Product, CallHistory)
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, extract, case, and_, desc
import pandas as pd
import logging

logger = logging.getLogger(__name__)

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
        StockTransaction.transaction_date < end_date.date()
    ).count()

    # Callsheet entries count and by_status using CallHistory
    callsheet_entries = CallHistory.query.filter(
        CallHistory.call_date >= start_date,
        CallHistory.call_date < end_date_inclusive
    ).count()

    # Callsheet by status
    callsheet_by_status = db.session.query(
        CallHistory.call_status,
        func.count(CallHistory.id)
    ).filter(
        CallHistory.call_date >= start_date,
        CallHistory.call_date < end_date_inclusive
    ).group_by(CallHistory.call_status).all()

    return jsonify({
        'forms': {
            'total': total_forms,
            'completed': completed_forms,
            'by_type': [{'type': t, 'count': c} for t, c in forms_by_type]
        },
        'standing_orders': {
            'active': active_standing_orders,
            'paused': paused_standing_orders,
            'created_this_period': standing_orders_created
        },
        'stock': {
            'total_transactions': stock_transactions
        },
        'callsheets': {
            'total_entries': callsheet_entries,
            'by_status': [{'status': s, 'count': c} for s, c in callsheet_by_status]
        }
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

@admin_bp.route('/api/reports/call-history-analytics')
@login_required
@admin_required
def get_call_history_analytics():
    """Get comprehensive call history analytics using CallHistory model"""

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        end_date_inclusive = end_date + timedelta(days=1)
    else:
        # Default to last 30 days
        end_date_inclusive = datetime.now()
        start_date = end_date_inclusive - timedelta(days=30)

    try:
        # Overall call statistics from CallHistory
        total_calls = CallHistory.query.filter(
            CallHistory.call_date >= start_date,
            CallHistory.call_date < end_date_inclusive
        ).count()

        if total_calls == 0:
            return jsonify({
                'total_calls': 0,
                'success_rate': 0,
                'decline_rate': 0,
                'no_answer_rate': 0,
                'callback_rate': 0,
                'calls_by_week': [],
                'status_breakdown': [],
                'top_callers': [],
                'daily_trends': []
            })

        # Status breakdown
        status_counts = db.session.query(
            CallHistory.call_status,
            func.count(CallHistory.id).label('count')
        ).filter(
            CallHistory.call_date >= start_date,
            CallHistory.call_date < end_date_inclusive
        ).group_by(CallHistory.call_status).all()

        status_breakdown = [{'status': s, 'count': c} for s, c in status_counts]

        # Calculate rates
        ordered_count = next((c for s, c in status_counts if s == 'ordered'), 0)
        declined_count = next((c for s, c in status_counts if s == 'declined'), 0)
        no_answer_count = next((c for s, c in status_counts if s == 'no_answer'), 0)
        callback_count = next((c for s, c in status_counts if s == 'callback'), 0)

        success_rate = round((ordered_count / total_calls * 100) if total_calls > 0 else 0, 1)
        decline_rate = round((declined_count / total_calls * 100) if total_calls > 0 else 0, 1)
        no_answer_rate = round((no_answer_count / total_calls * 100) if total_calls > 0 else 0, 1)
        callback_rate = round((callback_count / total_calls * 100) if total_calls > 0 else 0, 1)

        # Weekly trends
        weekly_data = db.session.query(
            CallHistory.year,
            CallHistory.week_number,
            func.count(CallHistory.id).label('total'),
            func.sum(case((CallHistory.call_status == 'ordered', 1), else_=0)).label('ordered'),
            func.sum(case((CallHistory.call_status == 'declined', 1), else_=0)).label('declined'),
            func.sum(case((CallHistory.call_status == 'no_answer', 1), else_=0)).label('no_answer')
        ).filter(
            CallHistory.call_date >= start_date,
            CallHistory.call_date < end_date_inclusive
        ).group_by(CallHistory.year, CallHistory.week_number).order_by(
            CallHistory.year, CallHistory.week_number
        ).all()

        calls_by_week = []
        for row in weekly_data:
            week_success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
            calls_by_week.append({
                'year': row.year,
                'week': row.week_number,
                'total': row.total,
                'ordered': row.ordered,
                'declined': row.declined,
                'no_answer': row.no_answer,
                'success_rate': week_success_rate
            })

        # Top callers performance
        top_callers_data = db.session.query(
            User.id,
            User.username,
            User.full_name,
            func.count(CallHistory.id).label('total'),
            func.sum(case((CallHistory.call_status == 'ordered', 1), else_=0)).label('ordered')
        ).join(CallHistory, CallHistory.called_by == User.id).filter(
            CallHistory.call_date >= start_date,
            CallHistory.call_date < end_date_inclusive
        ).group_by(User.id).all()

        top_callers = []
        for row in top_callers_data:
            caller_success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
            top_callers.append({
                'id': row.id,
                'username': row.username,
                'full_name': row.full_name,
                'total_calls': row.total,
                'orders': row.ordered,
                'success_rate': caller_success_rate
            })

        top_callers.sort(key=lambda x: x['total_calls'], reverse=True)

        # Daily trends (last 14 days for chart)
        daily_start = end_date_inclusive - timedelta(days=14)
        daily_data = db.session.query(
            func.date(CallHistory.call_date).label('date'),
            func.count(CallHistory.id).label('total'),
            func.sum(case((CallHistory.call_status == 'ordered', 1), else_=0)).label('ordered')
        ).filter(
            CallHistory.call_date >= daily_start,
            CallHistory.call_date < end_date_inclusive
        ).group_by(func.date(CallHistory.call_date)).order_by(func.date(CallHistory.call_date)).all()

        daily_trends = []
        for row in daily_data:
            daily_success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
            daily_trends.append({
                'date': str(row.date),
                'total': row.total,
                'ordered': row.ordered,
                'success_rate': daily_success_rate
            })

        return jsonify({
            'total_calls': total_calls,
            'success_rate': success_rate,
            'decline_rate': decline_rate,
            'no_answer_rate': no_answer_rate,
            'callback_rate': callback_rate,
            'calls_by_week': calls_by_week,
            'status_breakdown': status_breakdown,
            'top_callers': top_callers[:10],
            'daily_trends': daily_trends
        })

    except Exception as e:
        logger.error(f"Error in call_history_analytics: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/reports/problem-customers')
@login_required
@admin_required
def get_problem_customers():
    """Identify customers with high decline/no-answer rates that need attention"""

    # Get parameters
    min_calls = request.args.get('min_calls', default=3, type=int)  # Minimum calls to be considered
    days_lookback = request.args.get('days', default=60, type=int)  # How far back to look
    decline_threshold = request.args.get('decline_threshold', default=50, type=int)  # % decline rate
    no_answer_threshold = request.args.get('no_answer_threshold', default=60, type=int)  # % no answer rate

    cutoff_date = datetime.now() - timedelta(days=days_lookback)

    try:
        # Get customer call patterns from CallHistory
        customer_patterns = db.session.query(
            Customer.id,
            Customer.name,
            Customer.account_number,
            Customer.phone,
            Customer.email,
            Customer.contact_name,
            func.count(CallHistory.id).label('total_calls'),
            func.sum(case((CallHistory.call_status == 'ordered', 1), else_=0)).label('ordered'),
            func.sum(case((CallHistory.call_status == 'declined', 1), else_=0)).label('declined'),
            func.sum(case((CallHistory.call_status == 'no_answer', 1), else_=0)).label('no_answer'),
            func.max(CallHistory.call_date).label('last_call_date')
        ).join(CallHistory).filter(
            CallHistory.call_date >= cutoff_date
        ).group_by(Customer.id).having(
            func.count(CallHistory.id) >= min_calls
        ).all()

        problem_customers = []
        for row in customer_patterns:
            decline_rate = round((row.declined / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
            no_answer_rate = round((row.no_answer / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
            order_rate = round((row.ordered / row.total_calls * 100) if row.total_calls > 0 else 0, 1)

            # Determine problem type and recommendation
            problem_type = None
            recommendation = None
            priority = 0

            if decline_rate >= decline_threshold:
                problem_type = 'High Decline Rate'
                recommendation = 'Sales rep visit recommended - customer consistently declines phone orders'
                priority = 3  # High priority
            elif no_answer_rate >= no_answer_threshold:
                problem_type = 'Hard to Reach'
                recommendation = 'Update contact information or try different call times'
                priority = 2  # Medium priority
            elif row.ordered == 0 and row.total_calls >= 5:
                problem_type = 'Never Ordered'
                recommendation = 'Sales rep visit needed - no phone success after multiple attempts'
                priority = 3  # High priority

            if problem_type:
                problem_customers.append({
                    'id': row.id,
                    'name': row.name,
                    'account_number': row.account_number,
                    'phone': row.phone,
                    'email': row.email,
                    'contact_name': row.contact_name,
                    'total_calls': row.total_calls,
                    'ordered': row.ordered,
                    'declined': row.declined,
                    'no_answer': row.no_answer,
                    'decline_rate': decline_rate,
                    'no_answer_rate': no_answer_rate,
                    'order_rate': order_rate,
                    'last_call_date': row.last_call_date.isoformat() if row.last_call_date else None,
                    'problem_type': problem_type,
                    'recommendation': recommendation,
                    'priority': priority
                })

        # Sort by priority (high to low) then by decline rate
        problem_customers.sort(key=lambda x: (x['priority'], x['decline_rate']), reverse=True)

        return jsonify({
            'total_problem_customers': len(problem_customers),
            'high_priority': len([c for c in problem_customers if c['priority'] == 3]),
            'medium_priority': len([c for c in problem_customers if c['priority'] == 2]),
            'customers': problem_customers
        })

    except Exception as e:
        logger.error(f"Error in problem_customers: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/reports/sales-rep-needed')
@login_required
@admin_required
def get_sales_rep_needed():
    """Get list of customers who need a sales rep visit with detailed reasoning"""

    days_lookback = request.args.get('days', default=90, type=int)
    cutoff_date = datetime.now() - timedelta(days=days_lookback)

    try:
        # Get all customers with their call history
        customer_data = db.session.query(
            Customer.id,
            Customer.name,
            Customer.account_number,
            Customer.phone,
            Customer.email,
            Customer.contact_name,
            Customer.address,
            func.count(CallHistory.id).label('total_calls'),
            func.sum(case((CallHistory.call_status == 'ordered', 1), else_=0)).label('ordered'),
            func.sum(case((CallHistory.call_status == 'declined', 1), else_=0)).label('declined'),
            func.sum(case((CallHistory.call_status == 'no_answer', 1), else_=0)).label('no_answer'),
            func.max(CallHistory.call_date).label('last_call_date')
        ).join(CallHistory).filter(
            CallHistory.call_date >= cutoff_date
        ).group_by(Customer.id).all()

        sales_rep_needed = []
        for row in customer_data:
            if row.total_calls < 2:
                continue  # Need at least 2 calls to make a determination

            decline_rate = round((row.declined / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
            order_rate = round((row.ordered / row.total_calls * 100) if row.total_calls > 0 else 0, 1)

            reasons = []
            score = 0  # Priority score (higher = more urgent)

            # Criteria for needing sales rep visit

            # 1. High decline rate (50%+)
            if decline_rate >= 50 and row.total_calls >= 3:
                reasons.append(f'{decline_rate}% decline rate - customer prefers not to order by phone')
                score += 10

            # 2. Never ordered despite multiple calls
            if row.ordered == 0 and row.total_calls >= 5:
                reasons.append(f'{row.total_calls} calls with no orders - phone approach ineffective')
                score += 15

            # 3. Very high decline rate (75%+)
            if decline_rate >= 75:
                reasons.append(f'{decline_rate}% decline rate - strong resistance to phone orders')
                score += 5

            # 4. Mix of declines and no answers (difficult customer)
            if row.declined >= 2 and row.no_answer >= 2:
                reasons.append('Mixed decline and no-answer pattern - inconsistent engagement')
                score += 3

            # 5. Low order rate with many attempts
            if order_rate < 20 and row.total_calls >= 4:
                reasons.append(f'Only {order_rate}% order rate after {row.total_calls} attempts')
                score += 8

            # If there are reasons, add to the list
            if reasons:
                days_since_last_call = (datetime.now() - row.last_call_date).days if row.last_call_date else 0

                sales_rep_needed.append({
                    'id': row.id,
                    'name': row.name,
                    'account_number': row.account_number,
                    'phone': row.phone,
                    'email': row.email,
                    'contact_name': row.contact_name,
                    'address': row.address,
                    'total_calls': row.total_calls,
                    'ordered': row.ordered,
                    'declined': row.declined,
                    'no_answer': row.no_answer,
                    'decline_rate': decline_rate,
                    'order_rate': order_rate,
                    'last_call_date': row.last_call_date.isoformat() if row.last_call_date else None,
                    'days_since_last_call': days_since_last_call,
                    'reasons': reasons,
                    'priority_score': score
                })

        # Sort by priority score (highest first)
        sales_rep_needed.sort(key=lambda x: x['priority_score'], reverse=True)

        return jsonify({
            'total_customers': len(sales_rep_needed),
            'high_priority': len([c for c in sales_rep_needed if c['priority_score'] >= 15]),
            'medium_priority': len([c for c in sales_rep_needed if 8 <= c['priority_score'] < 15]),
            'low_priority': len([c for c in sales_rep_needed if c['priority_score'] < 8]),
            'customers': sales_rep_needed
        })

    except Exception as e:
        logger.error(f"Error in sales_rep_needed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/reports/returns-analytics')
@login_required
@admin_required
def get_returns_analytics():
    """Get returns form analytics - most used reasons and credit/uplift breakdown"""

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

    try:
        import json

        # Get all returns forms in the date range
        returns_forms = Form.query.filter(
            Form.type == 'returns',
            Form.date_created >= start_date,
            Form.date_created < end_date_inclusive
        ).all()

        if len(returns_forms) == 0:
            return jsonify({
                'total_returns': 0,
                'reasons': [],
                'credit_vs_uplift': {'credit': 0, 'uplift': 0},
                'returns_by_day': [],
                'top_customers': []
            })

        # Parse form data and collect statistics
        reason_counts = {}
        credit_uplift_counts = {'credit': 0, 'uplift': 0, 'unknown': 0}
        customer_return_counts = {}

        for form in returns_forms:
            try:
                form_data = json.loads(form.data)

                # Count reasons
                reason = form_data.get('reason', 'unknown')
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

                # Check for credit/uplift indicator (if exists in form data)
                # Note: Based on the form structure, credit/uplift might be implied by the form type
                # or could be a separate field. For now, we'll mark them as 'unknown' unless specified
                form_type = form_data.get('form_type', 'unknown')
                if 'credit' in form_type.lower():
                    credit_uplift_counts['credit'] += 1
                elif 'uplift' in form_type.lower():
                    credit_uplift_counts['uplift'] += 1
                else:
                    credit_uplift_counts['unknown'] += 1

                # Count returns by customer
                customer_name = form_data.get('customer_name', 'Unknown')
                customer_account = form_data.get('customer_account', '')
                customer_key = f"{customer_account} - {customer_name}"
                customer_return_counts[customer_key] = customer_return_counts.get(customer_key, 0) + 1

            except json.JSONDecodeError:
                logger.warning(f"Could not parse form data for form {form.id}")
                continue

        # Format reason counts with readable names
        reason_display_names = {
            'damaged': 'Damaged Product',
            'wrong': 'Wrong Product Sent',
            'overstock': 'Overstocked',
            'other': 'Other',
            'unknown': 'Unknown'
        }

        reasons = [
            {
                'reason': reason_display_names.get(reason, reason.title()),
                'count': count,
                'percentage': round((count / len(returns_forms) * 100), 1)
            }
            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Returns by day for trend chart
        returns_by_day_data = db.session.query(
            func.date(Form.date_created).label('date'),
            func.count(Form.id).label('count')
        ).filter(
            Form.type == 'returns',
            Form.date_created >= start_date,
            Form.date_created < end_date_inclusive
        ).group_by(func.date(Form.date_created)).order_by(func.date(Form.date_created)).all()

        returns_by_day = [
            {'date': str(row.date), 'count': row.count}
            for row in returns_by_day_data
        ]

        # Top customers with most returns
        top_customers = [
            {
                'customer': customer,
                'return_count': count
            }
            for customer, count in sorted(customer_return_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return jsonify({
            'total_returns': len(returns_forms),
            'reasons': reasons,
            'credit_vs_uplift': credit_uplift_counts,
            'returns_by_day': returns_by_day,
            'top_customers': top_customers
        })

    except Exception as e:
        logger.error(f"Error in returns_analytics: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/import-customers', methods=['GET', 'POST'])
@login_required
@admin_required
def import_customers():
    """Import customers from CSV/Excel file (Admin only)"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            try:
                # Read the file
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
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
                updated = 0
                
                for _, row in df.iterrows():
                    account_number = str(row['account_number']).strip()
                    name = str(row['name']).strip()
                    
                    if not account_number or not name or account_number == 'nan' or name == 'nan':
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
                        updated += 1
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
                flash(f'Successfully imported {imported} new customers and updated {updated} existing customers ({skipped} skipped)', 'success')
                return redirect(url_for('admin.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error importing file: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            flash('Please upload a CSV or Excel file', 'danger')
            return redirect(request.url)
    
    return render_template('admin/import_customers.html', title='Import Customers')

@admin_bp.route('/import-products', methods=['GET', 'POST'])
@login_required
@admin_required
def import_products():
    """Import products from CSV/Excel file (Admin only)"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            try:
                # Read the file
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                
                # Normalize column names
                df.columns = df.columns.str.lower().str.replace(' ', '_')
                
                # Check for required columns
                if 'code' not in df.columns and 'product_code' not in df.columns:
                    flash('File must contain a "code" or "product_code" column', 'danger')
                    return redirect(request.url)
                
                if 'name' not in df.columns and 'product_name' not in df.columns:
                    flash('File must contain a "name" or "product_name" column', 'danger')
                    return redirect(request.url)
                
                # Rename columns if needed
                if 'product_code' in df.columns:
                    df.rename(columns={'product_code': 'code'}, inplace=True)
                if 'product_name' in df.columns:
                    df.rename(columns={'product_name': 'name'}, inplace=True)
                
                # Import products
                imported = 0
                skipped = 0
                updated = 0
                
                for _, row in df.iterrows():
                    code = str(row['code']).strip()
                    name = str(row['name']).strip()
                    
                    if not code or not name or code == 'nan' or name == 'nan':
                        skipped += 1
                        continue
                    
                    # Check if product already exists
                    existing = Product.query.filter_by(code=code).first()
                    if existing:
                        # Update existing product
                        existing.name = name
                        if 'description' in row and pd.notna(row['description']):
                            existing.description = str(row['description']).strip()
                        updated += 1
                    else:
                        # Create new product
                        product = Product(
                            code=code,
                            name=name,
                            description=str(row.get('description', '')).strip() if 'description' in row and pd.notna(row.get('description')) else None
                        )
                        db.session.add(product)
                        imported += 1
                
                db.session.commit()
                flash(f'Successfully imported {imported} new products and updated {updated} existing products ({skipped} skipped)', 'success')
                return redirect(url_for('admin.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error importing file: {str(e)}', 'danger')
                return redirect(request.url)
        else:
            flash('Please upload a CSV or Excel file', 'danger')
            return redirect(request.url)
    
    return render_template('admin/import_products.html', title='Import Products')
