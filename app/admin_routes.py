# Add these routes to app/routes.py

@main.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    """Admin reports page"""
    # Get available date range for filtering
    oldest_entry = CallsheetEntry.query.order_by(CallsheetEntry.updated_at.asc()).first()
    
    start_date = oldest_entry.updated_at.date() if oldest_entry else date.today()
    end_date = date.today()
    
    return render_template(
        'admin_reports.html',
        title='Admin Reports',
        min_date=start_date.isoformat(),
        max_date=end_date.isoformat()
    )


@main.route('/api/admin/callsheet-report', methods=['POST'])
@login_required
@admin_required
def get_callsheet_report():
    """Get callsheet statistics filtered by date range"""
    data = request.json
    date_from = data.get('date_from')
    date_to = data.get('date_to')
    
    try:
        # Parse dates
        if date_from:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        else:
            date_from_obj = datetime.now() - timedelta(days=30)
            
        if date_to:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
        else:
            date_to_obj = datetime.now()
        
        # Query entries that were updated within the date range
        # Join with Callsheet to get day_of_week
        entries = db.session.query(
            CallsheetEntry, 
            Callsheet.day_of_week,
            Callsheet.name.label('callsheet_name'),
            Customer.name.label('customer_name')
        ).join(
            Callsheet, CallsheetEntry.callsheet_id == Callsheet.id
        ).join(
            Customer, CallsheetEntry.customer_id == Customer.id
        ).filter(
            CallsheetEntry.updated_at >= date_from_obj,
            CallsheetEntry.updated_at <= date_to_obj
        ).all()
        
        # Group data by the callsheet's day_of_week
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        stats_by_day = {day: {
            'total_entries': 0,
            'not_called': 0,
            'no_answer': 0,
            'declined': 0,
            'ordered': 0,
            'callback': 0,
            'entries': []
        } for day in days_of_week}
        
        # Overall KPIs
        total_entries = 0
        total_not_called = 0
        total_no_answer = 0
        total_declined = 0
        total_ordered = 0
        total_callback = 0
        
        for entry, day_of_week, callsheet_name, customer_name in entries:
            # Only count weekdays
            if day_of_week not in days_of_week:
                continue
                
            # Add to day-specific stats
            stats_by_day[day_of_week]['total_entries'] += 1
            stats_by_day[day_of_week][entry.call_status] += 1
            
            # Add to overall stats
            total_entries += 1
            if entry.call_status == 'not_called':
                total_not_called += 1
            elif entry.call_status == 'no_answer':
                total_no_answer += 1
            elif entry.call_status == 'declined':
                total_declined += 1
            elif entry.call_status == 'ordered':
                total_ordered += 1
            elif entry.call_status == 'callback':
                total_callback += 1
            
            # Add entry details for table
            stats_by_day[day_of_week]['entries'].append({
                'id': entry.id,
                'customer_name': customer_name,
                'callsheet_name': callsheet_name,
                'call_status': entry.call_status,
                'called_by': entry.called_by or '-',
                'person_spoken_to': entry.person_spoken_to or '-',
                'updated_at': entry.updated_at.strftime('%Y-%m-%d %H:%M'),
                'call_notes': entry.call_notes or ''
            })
        
        # Calculate success rate (ordered / total called attempts)
        total_called_attempts = total_entries - total_not_called
        success_rate = (total_ordered / total_called_attempts * 100) if total_called_attempts > 0 else 0
        
        # Calculate conversion rate by day
        for day in days_of_week:
            day_called = (stats_by_day[day]['total_entries'] - 
                         stats_by_day[day]['not_called'])
            if day_called > 0:
                stats_by_day[day]['conversion_rate'] = (
                    stats_by_day[day]['ordered'] / day_called * 100
                )
            else:
                stats_by_day[day]['conversion_rate'] = 0
        
        return jsonify({
            'success': True,
            'date_range': {
                'from': date_from_obj.strftime('%Y-%m-%d'),
                'to': date_to_obj.strftime('%Y-%m-%d')
            },
            'kpis': {
                'total_entries': total_entries,
                'not_called': total_not_called,
                'no_answer': total_no_answer,
                'declined': total_declined,
                'ordered': total_ordered,
                'callback': total_callback,
                'success_rate': round(success_rate, 1),
                'call_attempt_rate': round((total_called_attempts / total_entries * 100) if total_entries > 0 else 0, 1)
            },
            'stats_by_day': stats_by_day
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400