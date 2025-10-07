from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (StandingOrder, StandingOrderItem, StandingOrderLog, 
                       StandingOrderSchedule, Customer, User)
from datetime import datetime, date, timedelta
import json
import calendar

standing_orders_bp = Blueprint('standing_orders', __name__, url_prefix='/standing-orders')

def validate_standing_order_data(data):
    """Validate standing order input data"""
    errors = []
    
    # Required fields
    if not data.get('customer_id'):
        errors.append('Customer is required')
    
    if not data.get('delivery_days') or len(data.get('delivery_days', [])) == 0:
        errors.append('At least one delivery day must be selected')

    is_valid, error_msg = StandingOrder.validate_delivery_days(data.get('delivery_days', []))
    if not is_valid:
        errors.append(error_msg)
    
    # Validate delivery days are weekdays only
    try:
        delivery_days = [int(d) for d in data.get('delivery_days', [])]
        if any(d >= 5 or d < 0 for d in delivery_days):
            errors.append('Invalid delivery days - only Monday-Friday allowed')
    except (ValueError, TypeError):
        errors.append('Invalid delivery days format')
    
    # Validate items
    items = data.get('items', [])
    if not items or len(items) == 0:
        errors.append('At least one product must be added')
    
    for i, item in enumerate(items):
        if not item.get('product_code'):
            errors.append(f'Product {i+1}: Product code is required')
        if not item.get('product_name'):
            errors.append(f'Product {i+1}: Product name is required')
        
        # Validate quantity
        try:
            qty = int(item.get('quantity', 0))
            if qty <= 0:
                errors.append(f'Product {i+1}: Quantity must be greater than 0')
            if qty > 10000:
                errors.append(f'Product {i+1}: Quantity seems unreasonably high (max 10,000)')
        except (ValueError, TypeError):
            errors.append(f'Product {i+1}: Invalid quantity')
        
        # Validate string lengths
        if len(str(item.get('product_code', ''))) > 50:
            errors.append(f'Product {i+1}: Product code too long (max 50 characters)')
        if len(str(item.get('product_name', ''))) > 100:
            errors.append(f'Product {i+1}: Product name too long (max 100 characters)')
    
    # Validate special instructions length
    if data.get('special_instructions') and len(str(data['special_instructions'])) > 500:
        errors.append('Special instructions too long (max 500 characters)')
    
    # Validate end date if provided
    if data.get('end_date'):
        try:
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            if end_date < date.today():
                errors.append('End date cannot be in the past')
        except ValueError:
            errors.append('Invalid end date format')
    
    return errors



@standing_orders_bp.route('/standing-orders')
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

@standing_orders_bp.route('/standing-orders/new', methods=['GET', 'POST'])
@login_required
def new_standing_order():
    if request.method == 'POST':
        data = request.json
        
        # VALIDATE INPUT FIRST
        validation_errors = validate_standing_order_data(data)
        if validation_errors:
            return jsonify({
                'success': False, 
                'message': 'Validation errors: ' + '; '.join(validation_errors)
            }), 400
        
        try:
            # USE MODEL'S CLEAN METHOD - No more manual filtering!
            clean_days = StandingOrder.clean_delivery_days(data['delivery_days'])
            
            # Create standing order
            standing_order = StandingOrder(
                customer_id=data['customer_id'],
                delivery_days=','.join([str(d) for d in clean_days]),  # Use cleaned days
                start_date=date.today(),
                end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None,
                special_instructions=data.get('special_instructions', '')[:500],
                created_by=current_user.id
            )
            
            db.session.add(standing_order)
            db.session.flush()
            
            # Add items
            for item in data['items']:
                order_item = StandingOrderItem(
                    standing_order_id=standing_order.id,
                    product_code=item['product_code'][:50],  # Truncate to max length
                    product_name=item['product_name'][:100],  # Truncate to max length
                    quantity=int(item['quantity']),
                    unit_type=item.get('unit_type', 'units'),
                    special_notes=item.get('notes', '')[:500]  # Truncate to max length
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
            
            # Generate initial schedules
            generate_schedules_for_order(standing_order.id)
            
            db.session.commit()
            
            return jsonify({'success': True, 'id': standing_order.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    
    # GET request
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('standing_order_form.html', customers=customers)

@standing_orders_bp.route('/standing-orders/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_standing_order(order_id):
    order = StandingOrder.query.get_or_404(order_id)
    
    if request.method == 'POST':
        data = request.json
        
        # VALIDATE INPUT FIRST
        validation_errors = validate_standing_order_data(data)
        if validation_errors:
            return jsonify({
                'success': False, 
                'message': 'Validation errors: ' + '; '.join(validation_errors)
            }), 400
        
        try:
            changes = {}
            
            # USE MODEL'S CLEAN METHOD - No more manual filtering!
            clean_days = StandingOrder.clean_delivery_days(data['delivery_days'])
            new_delivery_days = ','.join([str(d) for d in clean_days])
            
            if order.delivery_days != new_delivery_days:
                changes['delivery_days'] = {
                    'old': order.delivery_days,
                    'new': new_delivery_days
                }
                order.delivery_days = new_delivery_days
            
            # Update end date if changed
            new_end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date() if data.get('end_date') else None
            if order.end_date != new_end_date:
                changes['end_date'] = {
                    'old': str(order.end_date) if order.end_date else None,
                    'new': str(new_end_date) if new_end_date else None
                }
                order.end_date = new_end_date
            
            # Update special instructions if changed
            new_instructions = data.get('special_instructions', '')
            if order.special_instructions != new_instructions:
                changes['special_instructions'] = {
                    'old': order.special_instructions,
                    'new': new_instructions
                }
                order.special_instructions = new_instructions
            
            # Handle items - delete existing and add new ones
            existing_items_data = {item.id: {
                'product_code': item.product_code,
                'product_name': item.product_name,
                'quantity': item.quantity,
                'unit_type': item.unit_type,
                'special_notes': item.special_notes
            } for item in order.items}
            
            # Delete all existing items
            for item in order.items:
                db.session.delete(item)
            
            # Add new items
            new_items_data = []
            for item in data['items']:
                order_item = StandingOrderItem(
                    standing_order_id=order.id,
                    product_code=item['product_code'],
                    product_name=item['product_name'],
                    quantity=item['quantity'],
                    unit_type=item.get('unit_type', 'units'),
                    special_notes=item.get('notes', '')
                )
                db.session.add(order_item)
                new_items_data.append({
                    'product_code': item['product_code'],
                    'product_name': item['product_name'],
                    'quantity': item['quantity']
                })
            
            if existing_items_data or new_items_data:
                changes['items'] = {
                    'old': list(existing_items_data.values()),
                    'new': new_items_data
                }
            
            # Update timestamp
            order.updated_at = datetime.now()
            
            # Log the modification
            log = StandingOrderLog(
                standing_order_id=order.id,
                action_type='modified',
                action_details=json.dumps(changes),
                performed_by=current_user.id
            )
            db.session.add(log)
            
            # Regenerate schedules if delivery days changed and order is active
            if 'delivery_days' in changes and order.status == 'active':
                # Delete future pending schedules
                future_schedules = StandingOrderSchedule.query.filter(
                    StandingOrderSchedule.standing_order_id == order.id,
                    StandingOrderSchedule.scheduled_date > date.today(),
                    StandingOrderSchedule.status == 'pending'
                ).all()
                
                for schedule in future_schedules:
                    db.session.delete(schedule)
                
                # Generate new schedules
                generate_schedules_for_order(order.id)
            
            db.session.commit()
            
            return jsonify({'success': True, 'id': order.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    
    # GET request - show form
    customers = Customer.query.order_by(Customer.name).all()
    return render_template('standing_order_edit.html', order=order, customers=customers)

@standing_orders_bp.route('/standing-orders/<int:order_id>')
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

@standing_orders_bp.route('/standing-orders/<int:order_id>/pause', methods=['POST'])
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

@standing_orders_bp.route('/standing-orders/<int:order_id>/resume', methods=['POST'])
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

@standing_orders_bp.route('/standing-orders/<int:order_id>/end', methods=['POST'])
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
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@standing_orders_bp.route('/standing-orders/schedule/<int:schedule_id>/complete', methods=['POST'])
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
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@standing_orders_bp.route('/standing-orders/schedule/<int:schedule_id>/skip', methods=['POST'])
@login_required
def skip_schedule(schedule_id):
    schedule = StandingOrderSchedule.query.get_or_404(schedule_id)
    
    try:
        schedule.status = 'skipped'
        schedule.notes = request.json.get('reason', 'Manually skipped')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order skipped'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@standing_orders_bp.route('/standing-orders/generate-schedules', methods=['POST'])
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

@standing_orders_bp.route('/standing-orders/schedule-view')
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
    
    # Get schedules in date range - exclude paused orders
    schedules = StandingOrderSchedule.query.join(StandingOrder).join(Customer).filter(
        StandingOrderSchedule.scheduled_date.between(start_date, end_date),
        StandingOrder.status != 'paused'
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
    
    # USE MODEL'S METHOD - Already filters weekends!
    delivery_days = order.get_delivery_days_list()
    
    while current_date <= end_date:
        # USE MODEL'S is_weekday METHOD
        if StandingOrder.is_weekday(current_date) and current_date.weekday() in delivery_days:
            # Check if schedule already exists with locking
            existing = StandingOrderSchedule.query.filter_by(
                standing_order_id=order_id,
                scheduled_date=current_date
            ).with_for_update().first()
            
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

@standing_orders_bp.route('/standing-orders/<int:order_id>/print')
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

@standing_orders_bp.route('/standing-orders/schedule-view/print')
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
    
    # Get schedules in date range - exclude paused orders
    schedules = StandingOrderSchedule.query.join(StandingOrder).join(Customer).filter(
        StandingOrderSchedule.scheduled_date.between(start_date, end_date),
        StandingOrder.status != 'paused'
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
