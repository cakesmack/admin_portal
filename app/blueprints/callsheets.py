from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Callsheet, CallsheetEntry, CallsheetArchive, Customer, User
from datetime import datetime, date, timedelta
from sqlalchemy.orm import joinedload  # ← ADD THIS
import json
import calendar

callsheets_bp = Blueprint('callsheets', __name__, url_prefix='/callsheets')

@callsheets_bp.route('/callsheets')
@login_required
def callsheets():
    """Main callsheets page - shows all permanent callsheets"""
    
    # Get ALL active callsheets (no month/year filtering)
    callsheets = Callsheet.query.filter_by(
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
        all_customers=all_customers,
        current_user=current_user
    )

@callsheets_bp.route('/api/callsheet/create', methods=['POST'])
@login_required
def create_callsheet():
    """Create new permanent callsheet"""
    data = request.json
    
    try:
        # Check for duplicate name on same day
        existing = Callsheet.query.filter_by(
            name=data['name'],
            day_of_week=data['day_of_week'],
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
            month=1,  # Dummy value
            year=2025,  # Dummy value
            is_active=True,
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

@callsheets_bp.route('/api/callsheet/<int:callsheet_id>/update', methods=['POST'])
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

@callsheets_bp.route('/api/callsheet/<int:callsheet_id>/delete', methods=['POST'])
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

@callsheets_bp.route('/api/callsheet/<int:callsheet_id>/add-customer', methods=['POST'])
@login_required
def add_customer_to_callsheet(callsheet_id):
    """Add a customer to a callsheet with optional address selection"""
    data = request.json
    customer_id = data.get('customer_id')
    address_id = data.get('address_id')
    address_label = data.get('address_label')
    
    if not customer_id:
        return jsonify({'success': False, 'message': 'Customer ID required'}), 400
    
    try:
        callsheet = Callsheet.query.get_or_404(callsheet_id)
        customer = Customer.query.get_or_404(customer_id)
        
        # Check if this customer+address combo already exists on this callsheet
        existing = CallsheetEntry.query.filter_by(
            callsheet_id=callsheet_id,
            customer_id=customer_id,
            address_label=address_label
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': f'{customer.name} - {address_label or "Primary"} is already on this callsheet'
            }), 400
        
        # Get the highest position
        max_position = db.session.query(db.func.max(CallsheetEntry.position))\
            .filter_by(callsheet_id=callsheet_id).scalar() or 0
        
        # Create new entry
        entry = CallsheetEntry(
            callsheet_id=callsheet_id,
            customer_id=customer_id,
            address_id=address_id,
            address_label=address_label,
            user_id=current_user.id,
            position=max_position + 1
        )
        
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer added to callsheet',
            'entry': {
                'id': entry.id,
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'account_number': customer.account_number,
                    'phone': customer.phone,
                    'callsheet_notes': customer.callsheet_notes
                },
                'address_label': address_label
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@callsheets_bp.route('/api/callsheet-entry/<int:entry_id>/update-status', methods=['POST'])
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

@callsheets_bp.route('/api/callsheet-entry/<int:entry_id>/update-notes', methods=['POST'])
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


@callsheets_bp.route('/api/callsheet-entry/<int:entry_id>/delete', methods=['POST'])
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


@callsheets_bp.route('/api/callsheet-entry/<int:entry_id>/toggle-pause', methods=['POST'])
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


@callsheets_bp.route('/api/callsheet-entry/<int:entry_id>/reorder', methods=['POST'])
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

@callsheets_bp.route('/api/callsheets/reset-week', methods=['POST'])
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

@callsheets_bp.route('/api/callsheets/archive', methods=['POST'])
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

@callsheets_bp.route('/api/callsheet/<int:callsheet_id>/complete', methods=['POST'])
@login_required
def complete_callsheet(callsheet_id):
    """Complete a callsheet - save snapshot and reset for next use"""
    callsheet = Callsheet.query.get_or_404(callsheet_id)
    
    try:
        # Get all entries for this callsheet
        entries = CallsheetEntry.query.filter_by(callsheet_id=callsheet_id).all()
        
        # Create snapshot data
        snapshot_data = {
            'callsheet_name': callsheet.name,
            'day_of_week': callsheet.day_of_week,
            'completed_date': datetime.now().isoformat(),
            'completed_by': current_user.username,
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
        
        # Save snapshot
        completion = CallsheetArchive(
            month=datetime.now().month,
            year=datetime.now().year,
            data=json.dumps(snapshot_data),
            archived_by=current_user.id
        )
        db.session.add(completion)
        
        # Reset all entries
        for entry in entries:
            entry.call_status = 'not_called'
            entry.called_by = None
            entry.call_date = None
            entry.person_spoken_to = None
            entry.callback_time = None
            entry.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{callsheet.name} completed and reset successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@callsheets_bp.route('/history')
@login_required
def callsheet_history_page():
    """Callsheet history page"""
    return render_template(
        'callsheet_history.html',
        title='Callsheet History'
    )

@callsheets_bp.route('/api/history')
@login_required
def callsheet_history():
    """Get completion history"""
    completions = CallsheetArchive.query.order_by(
        CallsheetArchive.archived_at.desc()
    ).limit(50).all()
    
    history = []
    for completion in completions:
        data = json.loads(completion.data)
        history.append({
            'id': completion.id,
            'callsheet_name': data.get('callsheet_name', 'Unknown'),
            'day_of_week': data.get('day_of_week', 'Unknown'),
            'completed_date': data.get('completed_date'),
            'completed_by': data.get('completed_by'),
            'archived_at': completion.archived_at.isoformat()
        })
    
    return jsonify(history)

@callsheets_bp.route('/api/callsheets/history/<int:completion_id>')
@login_required
def view_callsheet_completion(completion_id):
    """View a specific completion"""
    completion = CallsheetArchive.query.get_or_404(completion_id)
    data = json.loads(completion.data)
    
    return jsonify({
        'success': True,
        'data': data
    })

@callsheets_bp.route('/callsheets/archive/<int:month>/<int:year>')
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

