from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User, Customer, CallsheetEntry, Form
from app.forms import LoginForm, ReturnsForm, BrandedStockForm, InvoiceCorrectionForm, SpecialOrderForm
import json
from datetime import datetime

main = Blueprint('main', __name__)

# Sample data for demonstration - you would replace this with your actual data
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
@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # For MVP, using simple authentication
        # In production, you should use proper password hashing
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:  # Simple check for MVP
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
    
    return render_template('login.html', title='Login', form=form)

@main.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='Dashboard')

@main.route('/callsheets')
@login_required
def callsheets():
    # For MVP, using sample data
    # In a real application, you would fetch from database
    callsheet_data = []
    for customer in SAMPLE_CUSTOMERS:
        entry = {
            'account_number': customer['account_number'],
            'name': customer['name'],
            'contact_name': customer['contact_name'],
            'phone': customer['phone'],
            'week_1': False,
            'week_2': False,
            'week_3': False,
            'week_4': False,
            'order_placed_by': ''
        }
        callsheet_data.append(entry)
    
    return render_template('callsheets.html', title='Call Sheets', callsheet_data=callsheet_data)

@main.route('/returns', methods=['GET', 'POST'])
@login_required
def returns():
    form = ReturnsForm()
    if form.validate_on_submit():
        # Save form data
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
    if request.method == 'POST':
        form_data = {
            'customer_account': request.form.get('customer_account'),
            'customer_name': request.form.get('customer_name'),
            'product_code': request.form.get('product_code'),
            'product_name': request.form.get('product_name'),
            'quantity_delivered': request.form.get('quantity_delivered'),
            'current_stock': request.form.get('current_stock')
        }
        
        new_form = Form(
            type='branded_stock',
            data=json.dumps(form_data),
            user_id=session['user_id']
        )
        db.session.add(new_form)
        db.session.commit()
        
        flash(f'Branded stock delivery #{new_form.id} has been recorded successfully!', 'success')
        return redirect(url_for('main.forms'))
    
    # Get recent branded stock deliveries for the table
    recent_forms = Form.query.filter_by(type='branded_stock').order_by(Form.date_created.desc()).limit(5).all()
    recent_branded_stock = []
    
    for form in recent_forms:
        form_dict = {
            'id': form.id,
            'date_created': form.date_created,
            'data': json.loads(form.data)
        }
        recent_branded_stock.append(form_dict)
    
    return render_template('branded_stock.html', title='Branded Stock', recent_branded_stock=recent_branded_stock)

@main.route('/invoice-correction', methods=['GET', 'POST'])
@login_required
def invoice_correction():
    form = InvoiceCorrectionForm()
    if form.validate_on_submit():
        # Save form data
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
        # Save form data
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
    # For MVP, returning sample data
    # In a real application, you would query the database
    return jsonify(SAMPLE_CUSTOMERS)

@main.route('/api/products')
@login_required
def api_products():
    # For MVP, returning sample data
    # In a real application, you would query the database
    return jsonify(SAMPLE_PRODUCTS)


@main.route('/forms')
@login_required
def forms():
    # Get all forms from the database
    all_forms = Form.query.order_by(Form.date_created.desc()).all()
    
    # Convert form data from JSON string to Python dict for display
    forms_with_data = []
    for form in all_forms:
        form_dict = {
            'id': form.id,
            'type': form.type.replace('_', ' ').title(),
            'date_created': form.date_created,
            'author': User.query.get(form.user_id).username,
            'data': json.loads(form.data)
        }
        forms_with_data.append(form_dict)
    
    return render_template('forms.html', title='All Forms', forms=forms_with_data)

@main.route('/form/<int:form_id>')
@login_required
def view_form(form_id):
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    author = User.query.get(form.user_id).username
    
    return render_template(
        'view_form.html', 
        title=f'{form.type.replace("_", " ").title()} - #{form_id}',
        form_type=form.type,
        form_data=form_data,
        author=author,
        date_created=form.date_created,
        form_id=form_id ,
        datetime=datetime
    )

@main.route('/form/print/<int:form_id>')
@login_required
def print_form(form_id):
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    author = User.query.get(form.user_id).username
    
    return render_template(
        'print_form.html', 
        title=f'{form.type.replace("_", " ").title()} - #{form_id}',
        form_type=form.type,
        form_data=form_data,
        author=author,
        date_created=form.date_created,
        company_name='Highland Industrial Supplies'
    )

