from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Customer, CallsheetEntry, Form, Callsheet, CallsheetArchive
from app.forms import LoginForm, ReturnsForm, BrandedStockForm, InvoiceCorrectionForm, SpecialOrderForm
import json
from datetime import datetime, date
import calendar

main = Blueprint('main', __name__)

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

@main.route('/')
def index():
    return redirect(url_for('main.login'))

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        # For MVP, using simple authentication
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:  # Simple check for MVP
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    
    return render_template('login.html', title='Login', form=form)

@main.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='Dashboard')

@main.route('/callsheets')
@login_required
def callsheets():
    # Get current month and year
    now = datetime.now()
    current_month = request.args.get('month', default=now.month, type=int)
    current_year = request.args.get('year', default=now.year, type=int)
    
    # Get all callsheets for current month
    callsheets = Callsheet.query.filter_by(
        month=current_month,
        year=current_year,
        is_active=True
    ).order_by(
        Callsheet.day_of_week,
        Callsheet.name
    ).all()
    
    # Organize callsheets by day (Monday to Friday only)
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    callsheets_by_day = {day: [] for day in days_of_week}
    
    for callsheet in callsheets:
        if callsheet.day_of_week in callsheets_by_day:
            # Load entries for each callsheet
            entries = CallsheetEntry.query.filter_by(
                callsheet_id=callsheet.id
            ).join(Customer).order_by(CallsheetEntry.position).all()
            
            callsheet_data = {
                'id': callsheet.id,
                'name': callsheet.name,
                'entries': entries
            }
            callsheets_by_day[callsheet.day_of_week].append(callsheet_data)
    
    # Get all customers for the add customer modal
    all_customers = Customer.query.order_by(Customer.name).all()
    
    return render_template(
        'callsheets.html',
        title='Call Sheets',
        callsheets_by_day=callsheets_by_day,
        days_of_week=days_of_week,
        current_month=current_month,
        current_year=current_year,
        month_name=calendar.month_name[current_month],
        all_customers=all_customers,
        current_user=current_user
    )

@main.route('/api/callsheet/create', methods=['POST'])
@login_required
def create_callsheet():
    data = request.json
    
    try:
        callsheet = Callsheet(
            name=data['name'],
            day_of_week=data['day_of_week'],
            month=data['month'],
            year=data['year'],
            created_by=current_user.id
        )
        db.session.add(callsheet)
        db.session.commit()
        
        return jsonify({'success': True, 'id': callsheet.id, 'message': 'Callsheet created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet-entry/<int:entry_id>/update', methods=['POST'])
@login_required
def update_callsheet(callsheet_id):
    callsheet = Callsheet.query.get_or_404(callsheet_id)
    data = request.json
    
    try:
        if 'name' in data:
            callsheet.name = data['name']
        if 'day_of_week' in data:
            callsheet.day_of_week = data['day_of_week']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Callsheet updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet/<int:callsheet_id>/delete', methods=['POST'])
@login_required
def delete_callsheet(callsheet_id):
    callsheet = Callsheet.query.get_or_404(callsheet_id)
    
    try:
        db.session.delete(callsheet)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Callsheet deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@main.route('/api/callsheet/<int:callsheet_id>/add-customer', methods=['POST'])
@login_required
def add_customer_to_callsheet(callsheet_id):
    data = request.json
    
    try:
        # Check if customer already exists in this callsheet
        existing = CallsheetEntry.query.filter_by(
            callsheet_id=callsheet_id,
            customer_id=data['customer_id']
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Customer already in this callsheet'}), 400
        
        # Get the highest position in this callsheet
        max_position = db.session.query(db.func.max(CallsheetEntry.position))\
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
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/callsheet-entry/<int:entry_id>/update-status', methods=['POST'])
@login_required
def update_callsheet_entry_status(entry_id):
    entry = CallsheetEntry.query.get_or_404(entry_id)
    data = request.json
    
    try:
        # Update call status
        if 'call_status' in data:
            entry.call_status = data['call_status']
            
            # If status is changing from 'not_called' to something else, record the call
            if data['call_status'] != 'not_called':
                entry.called_by = current_user.username
                entry.call_date = datetime.now()
            
            # Handle status-specific data
            if data['call_status'] == 'ordered':
                entry.person_spoken_to = data.get('person_spoken_to', '')
            elif data['call_status'] == 'callback':
                entry.callback_time = data.get('callback_time', '')
        
        # Update notes if provided
        if 'call_notes' in data:
            entry.call_notes = data['call_notes']
        
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
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/callsheet-entry/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_callsheet_entry(entry_id):
    entry = CallsheetEntry.query.get_or_404(entry_id)
    
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Customer removed from callsheet'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

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

@main.route('/api/callsheets/archive', methods=['POST'])
@login_required
def archive_callsheets():
    """Archive current month's callsheets and create new ones"""
    data = request.json
    month = data.get('month')
    year = data.get('year')
    
    try:
        # Get all callsheets for the month
        callsheets = Callsheet.query.filter_by(month=month, year=year, is_active=True).all()
        
        # Create archive data
        archive_data = []
        for cs in callsheets:
            entries = CallsheetEntry.query.filter_by(callsheet_id=cs.id).all()
            cs_data = {
                'name': cs.name,
                'day_of_week': cs.day_of_week,
                'entries': [
                    {
                        'customer_name': entry.customer.name,
                        'customer_account': entry.customer.account_number,
                        'call_status': entry.call_status,
                        'called_by': entry.called_by,
                        'order_details': entry.order_details,
                        'order_value': entry.order_value,
                        'call_notes': entry.call_notes
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
        
        return jsonify({'success': True, 'message': f'Callsheets for {month}/{year} archived successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/api/callsheets/reset', methods=['POST'])
@login_required
def reset_callsheets():
    """Reset callsheets for new month - keeps structure but clears call data"""
    data = request.json
    old_month = data.get('old_month')
    old_year = data.get('old_year')
    new_month = data.get('new_month')
    new_year = data.get('new_year')
    
    try:
        # Archive old month first
        archive_response = archive_callsheets()
        
        # Get old callsheets structure
        old_callsheets = Callsheet.query.filter_by(
            month=old_month, 
            year=old_year
        ).all()
        
        # Create new callsheets with same structure
        for old_cs in old_callsheets:
            # Create new callsheet
            new_cs = Callsheet(
                name=old_cs.name,
                day_of_week=old_cs.day_of_week,
                month=new_month,
                year=new_year,
                created_by=current_user.id
            )
            db.session.add(new_cs)
            db.session.flush()  # Get the ID
            
            # Copy customer list but reset call data
            old_entries = CallsheetEntry.query.filter_by(callsheet_id=old_cs.id).all()
            for old_entry in old_entries:
                new_entry = CallsheetEntry(
                    callsheet_id=new_cs.id,
                    customer_id=old_entry.customer_id,
                    position=old_entry.position,
                    user_id=current_user.id,
                    called=False,
                    order_placed=False
                )
                db.session.add(new_entry)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Callsheets reset for {new_month}/{new_year}'})
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

@main.route('/returns', methods=['GET', 'POST'])
@login_required
def returns():
    form = ReturnsForm()
    if form.validate_on_submit():
        form_data = {
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'product_code': form.product_code.data,
            'product_name': form.product_name.data,
            'quantity': form.quantity.data,
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
        return redirect(url_for('main.dashboard'))
    
    return render_template('returns_form.html', title='Returns Form', form=form)

@main.route('/branded-stock', methods=['GET', 'POST'])
@login_required
def branded_stock():
    form = BrandedStockForm()
    if form.validate_on_submit():
        form_data = {
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'product_code': form.product_code.data,
            'product_name': form.product_name.data,
            'quantity_delivered': form.quantity_delivered.data,
            'current_stock': form.current_stock.data
        }
        
        new_form = Form(
            type='branded_stock',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash(f'Branded stock delivery #{new_form.id} has been recorded successfully!', 'success')
        return redirect(url_for('main.forms'))
    
    # Get recent branded stock deliveries for the table
    recent_forms = Form.query.filter_by(type='branded_stock').order_by(Form.date_created.desc()).limit(5).all()
    recent_branded_stock = []
    
    for form_entry in recent_forms:
        form_dict = {
            'id': form_entry.id,
            'date_created': form_entry.date_created,
            'data': json.loads(form_entry.data)
        }
        recent_branded_stock.append(form_dict)
    
    return render_template('branded_stock.html', title='Branded Stock', form=form, recent_branded_stock=recent_branded_stock)

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
            type='invoice_correction',
            data=json.dumps(form_data),
            user_id=current_user.id
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash('Invoice correction recorded successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('invoice_correction.html', title='Invoice Correction', form=form)

@main.route('/special-order', methods=['GET', 'POST'])
@login_required
def special_order():
    form = SpecialOrderForm()
    if form.validate_on_submit():
        form_data = {
            'supplier': form.supplier.data,
            'customer_account': form.customer_account.data,
            'product_code': form.product_code.data,
            'product_description': form.product_description.data,
            'quantity': form.quantity.data,
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
    all_forms = Form.query.order_by(Form.date_created.desc()).all()
    
    forms_with_data = []
    for form in all_forms:
        form_dict = {
            'id': form.id,
            'type': form.type.replace('_', ' ').title(),
            'date_created': form.date_created,
            'author': User.query.get(form.user_id).username if User.query.get(form.user_id) else 'Unknown',
            'data': json.loads(form.data)
        }
        forms_with_data.append(form_dict)
    
    return render_template('forms.html', title='All Forms', forms=forms_with_data)

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

@main.route('/form/print/<int:form_id>')
@login_required
def print_form(form_id):
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    user = User.query.get(form.user_id)
    author = user.username if user else 'Unknown'
    
    return render_template(
        'print_form.html', 
        title=f'{form.type.replace("_", " ").title()} - #{form_id}',
        form_type=form.type,
        form_data=form_data,
        author=author,
        date_created=form.date_created,
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
            'phone': customer.phone
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