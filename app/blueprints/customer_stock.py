from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import CustomerStock, StockTransaction, Customer, Form
from app.forms import BrandedStockForm
from datetime import datetime
import json

customer_stock_bp = Blueprint('customer_stock', __name__, url_prefix='/customer-stock')

def validate_stock_transaction(data, stock_item):
    """Validate stock transaction input"""
    errors = []
    
    # Required fields
    if not data.get('transaction_type'):
        errors.append('Transaction type is required')
    
    if data.get('transaction_type') not in ['stock_in', 'stock_out', 'adjustment']:
        errors.append('Invalid transaction type')
    
    # Validate quantity
    try:
        quantity = int(data.get('quantity', 0))
        if quantity == 0:
            errors.append('Quantity cannot be zero')
        if abs(quantity) > 10000:
            errors.append('Quantity seems unreasonably high (max 10,000)')
        
        # Check stock availability for stock_out
        if data.get('transaction_type') == 'stock_out' and quantity > stock_item.current_stock:
            errors.append(f'Insufficient stock (available: {stock_item.current_stock})')
        
    except (ValueError, TypeError):
        errors.append('Invalid quantity - must be a number')
    
    # Validate reference length
    if data.get('reference') and len(str(data['reference'])) > 100:
        errors.append('Reference too long (max 100 characters)')
    
    # Validate notes length
    if data.get('notes') and len(str(data['notes'])) > 500:
        errors.append('Notes too long (max 500 characters)')
    
    return errors


@customer_stock_bp.route('/customer-stock')
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



@customer_stock_bp.route('/branded-stock', methods=['GET', 'POST'])
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
                'address_label': request.form.get('address_label', ''),
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



@customer_stock_bp.route('/api/customer-stock', methods=['POST'])
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

@customer_stock_bp.route('/api/customer-stock/<int:stock_id>/transaction', methods=['POST'])
@login_required
def create_stock_transaction(stock_id):
    stock_item = CustomerStock.query.get_or_404(stock_id)
    data = request.json
    
    validation_errors = validate_stock_transaction(data, stock_item)
    if validation_errors:
        return jsonify({
            'success': False, 
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400
    
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


@customer_stock_bp.route('/api/customer-stock/search')
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


@customer_stock_bp.route('/api/customer-stock/<int:stock_id>/history')
@login_required
def get_stock_history(stock_id):
    stock_item = CustomerStock.query.get_or_404(stock_id)
    transactions = StockTransaction.query.filter_by(stock_item_id=stock_id)\
        .order_by(StockTransaction.transaction_date.desc()).all()
    
    return jsonify([transaction.to_dict() for transaction in transactions])
