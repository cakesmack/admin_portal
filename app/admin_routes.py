"""
Admin routes for reports and analytics
Separated for easier maintenance and updates
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import (User, Customer, Form, CallsheetEntry, StandingOrder, 
                       StandingOrderLog, StockTransaction, CustomerStock, CompanyUpdate)
from datetime import datetime, timedelta
from sqlalchemy import func, cast, Date, extract, case

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
    
    # Date range from request or default to current month
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        # Default to current month
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    
    # Total forms created
    total_forms = Form.query.filter(
        Form.date_created >= start_date,
        Form.date_created < end_date
    ).count()
    
    completed_forms = Form.query.filter(
        Form.date_created >= start_date,
        Form.date_created < end_date,
        Form.is_completed == True
    ).count()
    
    # Forms by type
    forms_by_type = db.session.query(
        Form.type,
        func.count(Form.id)
    ).filter(
        Form.date_created >= start_date,
        Form.date_created < end_date
    ).group_by(Form.type).all()
    
    # Standing orders
    active_standing_orders = StandingOrder.query.filter_by(status='active').count()
    paused_standing_orders = StandingOrder.query.filter_by(status='paused').count()
    
    standing_orders_created = StandingOrder.query.filter(
        StandingOrder.created_at >= start_date,
        StandingOrder.created_at < end_date
    ).count()
    
    # Stock transactions
    stock_transactions = StockTransaction.query.filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date < end_date.date()
    ).count()
    
    stock_by_type = db.session.query(
        StockTransaction.transaction_type,
        func.count(StockTransaction.id)
    ).filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date < end_date.date()
    ).group_by(StockTransaction.transaction_type).all()
    
    # Callsheet statistics - Use updated_at
    callsheet_entries_total = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).count()
    
    callsheet_by_status = db.session.query(
        CallsheetEntry.call_status,
        func.count(CallsheetEntry.id)
    ).filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(CallsheetEntry.call_status).all()
    
    print(f"DEBUG Summary: Total callsheet entries in date range: {callsheet_entries_total}")  # Debug
    print(f"DEBUG Summary: By status: {[(status, count) for status, count in callsheet_by_status]}")  # Debug
    
    # Company updates
    company_updates = CompanyUpdate.query.filter(
        CompanyUpdate.created_at >= start_date,
        CompanyUpdate.created_at < end_date
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
        # Add one day to end_date to include the full end day
        end_date = end_date + timedelta(days=1)
    else:
        # Default to last 30 days
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
    
    # Callsheet updates by day
    callsheet_by_day = db.session.query(
        func.date(CallsheetEntry.updated_at).label('date'),
        func.count(CallsheetEntry.id).label('count')
    ).filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date
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
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    
    users = User.query.filter_by(is_active=True).all()
    user_stats = []
    
    for user in users:
        forms_created = Form.query.filter(
            Form.user_id == user.id,
            Form.date_created >= start_date,
            Form.date_created < end_date
        ).count()
        
        forms_completed = Form.query.filter(
            Form.completed_by == user.id,
            Form.completed_date >= start_date,
            Form.completed_date < end_date
        ).count()
        
        standing_orders_created = StandingOrder.query.filter(
            StandingOrder.created_by == user.id,
            StandingOrder.created_at >= start_date,
            StandingOrder.created_at < end_date
        ).count()
        
        stock_transactions = StockTransaction.query.filter(
            StockTransaction.created_by == user.id,
            StockTransaction.transaction_date >= start_date.date(),
            StockTransaction.transaction_date < end_date.date()
        ).count()
        
        callsheet_updates = CallsheetEntry.query.filter(
            CallsheetEntry.user_id == user.id,
            CallsheetEntry.updated_at >= start_date,
            CallsheetEntry.updated_at < end_date
        ).count()
        
        company_updates = CompanyUpdate.query.filter(
            CompanyUpdate.user_id == user.id,
            CompanyUpdate.created_at >= start_date,
            CompanyUpdate.created_at < end_date
        ).count()
        
        total_activity = (forms_created + forms_completed + standing_orders_created + 
                         stock_transactions + callsheet_updates + company_updates)
        
        if total_activity > 0:  # Only include users with activity
            user_stats.append({
                'user_id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'role': user.role,
                'forms_created': forms_created,
                'forms_completed': forms_completed,
                'standing_orders': standing_orders_created,
                'stock_transactions': stock_transactions,
                'callsheet_updates': callsheet_updates,
                'company_updates': company_updates,
                'total_activity': total_activity,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
    
    # Sort by total activity
    user_stats.sort(key=lambda x: x['total_activity'], reverse=True)
    
    return jsonify(user_stats)

@admin_bp.route('/api/reports/customer-analysis')
@login_required
@admin_required
def get_customer_analysis():
    """Get customer engagement analysis"""
    
    # Customers with best ordering rate (highest % of calls that result in orders)
    best_ordering = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('orders_placed')
    ).join(CallsheetEntry).group_by(
        Customer.id
    ).having(func.count(CallsheetEntry.id) >= 3).all()  # At least 3 calls to be meaningful
    
    best_ordering_list = []
    for c in best_ordering:
        if c.total_calls > 0:
            order_rate = (c.orders_placed / c.total_calls) * 100
            best_ordering_list.append({
                'id': c.id,
                'name': c.name,
                'account_number': c.account_number,
                'total_calls': c.total_calls,
                'orders_placed': c.orders_placed,
                'order_rate': order_rate
            })
    
    # Sort by order rate
    best_ordering_list.sort(key=lambda x: x['order_rate'], reverse=True)
    
    # Customers with standing orders
    customers_with_standing_orders = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(StandingOrder.id).label('order_count')
    ).join(StandingOrder).filter(
        StandingOrder.status == 'active'
    ).group_by(Customer.id).order_by(
        func.count(StandingOrder.id).desc()
    ).limit(10).all()
    
    # Customers with most stock tracked
    customers_with_stock = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CustomerStock.id).label('stock_items'),
        func.sum(CustomerStock.current_stock).label('total_stock')
    ).join(CustomerStock).group_by(
        Customer.id
    ).order_by(func.sum(CustomerStock.current_stock).desc()).limit(10).all()
    
    return jsonify({
        'best_ordering_customers': best_ordering_list[:10],
        'customers_with_standing_orders': [{
            'id': c.id,
            'name': c.name,
            'account_number': c.account_number,
            'order_count': c.order_count
        } for c in customers_with_standing_orders],
        'customers_with_stock': [{
            'id': c.id,
            'name': c.name,
            'account_number': c.account_number,
            'stock_items': c.stock_items,
            'total_stock': int(c.total_stock) if c.total_stock else 0
        } for c in customers_with_stock]
    })

@admin_bp.route('/api/reports/inactive-customers')
@login_required
@admin_required
def get_inactive_customers():
    """Get customers who haven't been contacted recently"""
    
    days = request.args.get('days', default=30, type=int)
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Get all customers
    all_customers = Customer.query.all()
    inactive_customers = []
    
    for customer in all_customers:
        # Get most recent callsheet entry for this customer
        last_entry = CallsheetEntry.query.filter_by(
            customer_id=customer.id
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
    
    # Sort by days since contact (most inactive first)
    inactive_customers.sort(key=lambda x: x['days_since_contact'], reverse=True)
    
    return jsonify(inactive_customers)

@admin_bp.route('/api/reports/callsheet-analytics')
@login_required
@admin_required
def get_callsheet_analytics():
    """Get detailed callsheet analytics"""
    
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
    
    print(f"DEBUG: Start date type: {type(start_date)}, value: {start_date}")
    print(f"DEBUG: End date type: {type(end_date)}, value: {end_date}")
    
    # Add 1 day to end_date to make it inclusive
    end_date_inclusive = end_date + timedelta(days=1)
    
    print(f"DEBUG: Using end_date_inclusive: {end_date_inclusive}")
    
    # Overall call status rates - Use updated_at for real-time data
    total_calls = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date_inclusive,
        CallsheetEntry.call_status != 'not_called'
    ).count()
    
    print(f"DEBUG: Total calls between {start_date} and {end_date_inclusive}: {total_calls}")
    
    # Also check what entries exist regardless of date
    all_non_not_called = CallsheetEntry.query.filter(
        CallsheetEntry.call_status != 'not_called'
    ).count()
    print(f"DEBUG: Total non-'not_called' entries in database: {all_non_not_called}")
    
    # Check entries updated today
    today_entries = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date
    ).all()
    print(f"DEBUG: Entries updated after start_date: {len(today_entries)}")
    for entry in today_entries[:5]:  # Show first 5
        print(f"  - ID: {entry.id}, Status: {entry.call_status}, Updated: {entry.updated_at}, Call Date: {entry.call_date}")
    
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
    
    # All filtered by updated_at
    ordered = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date_inclusive,
        CallsheetEntry.call_status == 'ordered'
    ).count()
    
    no_answer = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date_inclusive,
        CallsheetEntry.call_status == 'no_answer'
    ).count()
    
    declined = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date_inclusive,
        CallsheetEntry.call_status == 'declined'
    ).count()
    
    callback = CallsheetEntry.query.filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date_inclusive,
        CallsheetEntry.call_status == 'callback'
    ).count()
    
    print(f"DEBUG: Ordered={ordered}, No Answer={no_answer}, Declined={declined}, Callback={callback}")  # Debug
    
    order_success_rate = round((ordered / total_calls * 100) if total_calls > 0 else 0, 1)
    no_answer_rate = round((no_answer / total_calls * 100) if total_calls > 0 else 0, 1)
    decline_rate = round((declined / total_calls * 100) if total_calls > 0 else 0, 1)
    callback_rate = round((callback / total_calls * 100) if total_calls > 0 else 0, 1)
    
    print(f"DEBUG: Rates - Order={order_success_rate}%, NoAnswer={no_answer_rate}%, Decline={decline_rate}%, Callback={callback_rate}%")  # Debug
    
    # Daily success rate trend - FILTERED by call_date
    daily_data = db.session.query(
        func.date(CallsheetEntry.call_date).label('date'),
        func.count(CallsheetEntry.id).label('total'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('ordered')
    ).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(func.date(CallsheetEntry.call_date)).order_by(func.date(CallsheetEntry.call_date)).all()
    
    daily_success_rate = []
    for row in daily_data:
        success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
        date_str = str(row.date) if row.date else None
        if date_str:
            daily_success_rate.append({
                'date': date_str,
                'success_rate': success_rate
            })
    
    # Performance by day of week - FILTERED by call_date
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_data = db.session.query(
        extract('dow', CallsheetEntry.call_date).label('day_of_week'),
        func.count(CallsheetEntry.id).label('total'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('ordered')
    ).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(extract('dow', CallsheetEntry.call_date)).all()
    
    day_performance = {}
    for row in day_data:
        day_index = int(row.day_of_week)
        if day_index == 0:
            day_name = 'Sunday'
        else:
            day_name = day_names[day_index - 1]
        success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
        day_performance[day_name] = success_rate
    
    # Staff performance - FILTERED by call_date
    staff_data = db.session.query(
        User.id,
        User.username,
        User.full_name,
        func.count(CallsheetEntry.id).label('total'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('ordered')
    ).join(CallsheetEntry, CallsheetEntry.user_id == User.id).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(User.id).all()
    
    staff_performance = []
    for row in staff_data:
        if row.total >= 3:  # Lowered threshold for filtered data
            success_rate = round((row.ordered / row.total * 100) if row.total > 0 else 0, 1)
            staff_performance.append({
                'user_id': row.id,
                'username': row.username,
                'full_name': row.full_name,
                'total_calls': row.total,
                'orders': row.ordered,
                'success_rate': success_rate
            })
    
    staff_performance.sort(key=lambda x: x['success_rate'], reverse=True)
    
    # Most responsive customers - FILTERED by call_date
    responsive_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'ordered', 1), else_=0)).label('orders_placed')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    most_responsive = []
    for row in responsive_data:
        success_rate = round((row.orders_placed / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if success_rate >= 50:
            most_responsive.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'orders_placed': row.orders_placed,
                'success_rate': success_rate
            })
    
    most_responsive.sort(key=lambda x: x['success_rate'], reverse=True)
    
    # Hard to reach customers - FILTERED by call_date
    hard_to_reach_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'no_answer', 1), else_=0)).label('no_answer')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    hard_to_reach = []
    for row in hard_to_reach_data:
        no_answer_rate = round((row.no_answer / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if no_answer_rate >= 50:
            hard_to_reach.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'no_answer': row.no_answer,
                'no_answer_rate': no_answer_rate
            })
    
    hard_to_reach.sort(key=lambda x: x['no_answer_rate'], reverse=True)
    
    # Frequent decliners - FILTERED by call_date
    decliner_data = db.session.query(
        Customer.id,
        Customer.name,
        Customer.account_number,
        func.count(CallsheetEntry.id).label('total_calls'),
        func.sum(case((CallsheetEntry.call_status == 'declined', 1), else_=0)).label('declined')
    ).join(CallsheetEntry).filter(
        CallsheetEntry.call_date >= start_date,
        CallsheetEntry.call_date < end_date,
        CallsheetEntry.call_status != 'not_called'
    ).group_by(Customer.id).having(func.count(CallsheetEntry.id) >= 2).all()
    
    frequent_decliners = []
    for row in decliner_data:
        decline_rate = round((row.declined / row.total_calls * 100) if row.total_calls > 0 else 0, 1)
        if row.declined >= 1:  # At least 1 decline
            frequent_decliners.append({
                'id': row.id,
                'name': row.name,
                'account_number': row.account_number,
                'total_calls': row.total_calls,
                'declined': row.declined,
                'decline_rate': decline_rate
            })
    
    frequent_decliners.sort(key=lambda x: x['decline_rate'], reverse=True)
    
    # Pending callbacks
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
            'callback_time': entry.callback_time if hasattr(entry, 'callback_time') else None,
            'notes': entry.call_notes if hasattr(entry, 'call_notes') else None
        })
    
    return jsonify({
        'order_success_rate': order_success_rate,
        'no_answer_rate': no_answer_rate,
        'decline_rate': decline_rate,
        'callback_rate': callback_rate,
        'daily_success_rate': daily_success_rate,
        'day_performance': day_performance,
        'staff_performance': staff_performance[:10],  # Top 10
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
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    
    # Activity by day of week
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    activity_by_day = {day: 0 for day in day_names}
    
    # Count forms by day of week
    forms_by_day = db.session.query(
        extract('dow', Form.date_created).label('day_of_week'),
        func.count(Form.id).label('count')
    ).filter(
        Form.date_created >= start_date,
        Form.date_created < end_date
    ).group_by(extract('dow', Form.date_created)).all()
    
    for day_num, count in forms_by_day:
        day_index = int(day_num)
        if day_index == 0:
            day_name = 'Sunday'
        else:
            day_name = day_names[day_index - 1]
        activity_by_day[day_name] = count
    
    # Count callsheet entries by day of week
    callsheet_by_day = db.session.query(
        extract('dow', CallsheetEntry.updated_at).label('day_of_week'),
        func.count(CallsheetEntry.id).label('count')
    ).filter(
        CallsheetEntry.updated_at >= start_date,
        CallsheetEntry.updated_at < end_date
    ).group_by(extract('dow', CallsheetEntry.updated_at)).all()
    
    for day_num, count in callsheet_by_day:
        day_index = int(day_num)
        if day_index == 0:
            day_name = 'Sunday'
        else:
            day_name = day_names[day_index - 1]
        activity_by_day[day_name] += count
    
    # Count stock transactions by day of week
    stock_by_day = db.session.query(
        extract('dow', StockTransaction.transaction_date).label('day_of_week'),
        func.count(StockTransaction.id).label('count')
    ).filter(
        StockTransaction.transaction_date >= start_date.date(),
        StockTransaction.transaction_date < end_date.date()
    ).group_by(extract('dow', StockTransaction.transaction_date)).all()
    
    for day_num, count in stock_by_day:
        day_index = int(day_num)
        if day_index == 0:
            day_name = 'Sunday'
        else:
            day_name = day_names[day_index - 1]
        activity_by_day[day_name] += count
    
    return jsonify({
        'activity_by_day_of_week': activity_by_day
    })