from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import ClearanceStock
from datetime import datetime
from sqlalchemy import or_
from werkzeug.utils import secure_filename
import openpyxl
from io import BytesIO

clearance_stock_bp = Blueprint('clearance_stock', __name__, url_prefix='/clearance')

@clearance_stock_bp.route('/')
@login_required
def clearance_stock():
    return render_template('clearance_stock.html', title='Clearance Stock')

@clearance_stock_bp.route('/api/clearance-stock')
@login_required
def get_clearance_stock():
    search = request.args.get('search', '').strip()
    pallet_filter = request.args.get('pallet', '').strip()
    
    query = ClearanceStock.query
    
    if search:
        query = query.filter(
            or_(
                ClearanceStock.supplier_code.ilike(f'%{search}%'),
                ClearanceStock.his_code.ilike(f'%{search}%'),
                ClearanceStock.description.ilike(f'%{search}%'),
                ClearanceStock.pallet.ilike(f'%{search}%')
            )
        )
    
    if pallet_filter:
        query = query.filter(ClearanceStock.pallet == pallet_filter)
    
    items = query.order_by(ClearanceStock.pallet, ClearanceStock.description).all()
    
    return jsonify({
        'success': True,
        'items': [item.to_dict() for item in items]
    })

@clearance_stock_bp.route('/api/clearance-stock/pallets')
@login_required
def get_pallets():
    pallets = db.session.query(ClearanceStock.pallet).distinct().filter(ClearanceStock.pallet.isnot(None)).all()
    return jsonify({
        'success': True,
        'pallets': [p[0] for p in pallets if p[0]]
    })

@clearance_stock_bp.route('/api/clearance-stock', methods=['POST'])
@login_required
def add_clearance_item():
    try:
        data = request.json
        
        total_price = float(data['qty']) * float(data['cost_price']) if data.get('cost_price') else 0
        
        item = ClearanceStock(
            qty=int(data['qty']),
            qty_sold=0,
            supplier_code=data['supplier_code'],
            his_code=data.get('his_code', ''),
            description=data['description'],
            cost_price=float(data['cost_price']),
            total_price=total_price,
            supplier_link=data.get('supplier_link', ''),
            pallet=data.get('pallet', ''),
            created_by=current_user.id
        )
        
        db.session.add(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item added successfully',
            'item': item.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@clearance_stock_bp.route('/api/clearance-stock/<int:item_id>', methods=['PUT'])
@login_required
def update_clearance_item(item_id):
    try:
        item = ClearanceStock.query.get_or_404(item_id)
        data = request.json
        
        item.qty = int(data['qty'])
        item.supplier_code = data['supplier_code']
        item.his_code = data.get('his_code', '')
        item.description = data['description']
        item.cost_price = float(data['cost_price'])
        item.total_price = item.qty * item.cost_price
        item.supplier_link = data.get('supplier_link', '')
        item.pallet = data.get('pallet', '')
        item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item updated successfully',
            'item': item.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@clearance_stock_bp.route('/api/clearance-stock/<int:item_id>/sell', methods=['POST'])
@login_required
def sell_clearance_item(item_id):
    try:
        item = ClearanceStock.query.get_or_404(item_id)
        data = request.json
        
        qty_to_sell = int(data.get('qty_sold', 0))
        
        if qty_to_sell <= 0:
            return jsonify({'success': False, 'message': 'Quantity must be greater than 0'}), 400
        
        if qty_to_sell > item.qty:
            return jsonify({'success': False, 'message': f'Cannot sell {qty_to_sell}. Only {item.qty} available.'}), 400
        
        # Update quantities
        item.qty -= qty_to_sell
        item.qty_sold += qty_to_sell
        item.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Marked {qty_to_sell} units as sold',
            'item': item.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

    try:
        item = ClearanceStock.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@clearance_stock_bp.route('/api/clearance-stock/upload', methods=['POST'])
@login_required
def upload_clearance_file():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xlsm')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xlsm)'}), 400
    
    try:
        # Read file into memory
        file_content = BytesIO(file.read())
        wb = openpyxl.load_workbook(file_content, data_only=True)  # This evaluates formulas
        sheet = wb['Sheet1']
        
        current_pallet = ''
        items_added = 0
        errors = []
        row_num = 0
        
        for row_num, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), 1):
            try:
                # Pallet header
                if row[0] and 'Pallet' in str(row[0]):
                    current_pallet = str(row[0])
                    continue
                
                # Title row or header row
                if row[0] == 'Qty' or row[0] == '2024 Stock Clearance':
                    continue
                
                # Empty row
                if not row[0]:
                    continue
                
                # Skip non-numeric qty
                try:
                    test_qty = float(str(row[0]))
                    if test_qty <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # DATA ROW - just fucking add it
                qty = int(float(str(row[0])))
                cost_price = float(row[4] or 0)
                
                # Handle total_price - might be a formula or None
                if row[5] and not isinstance(row[5], str):
                    total_price = float(row[5])
                else:
                    total_price = qty * cost_price
                
                item = ClearanceStock(
                    qty=qty,
                    qty_sold=0,
                    supplier_code=str(row[1] or ''),
                    his_code=str(row[2] or ''),
                    description=str(row[3] or ''),
                    cost_price=cost_price,
                    total_price=total_price,
                    supplier_link=str(row[7] or '') if len(row) > 7 else '',
                    pallet=current_pallet,
                    created_by=current_user.id
                )
                db.session.add(item)
                items_added += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue
        
        db.session.commit()
        
        print(f"Import complete! Added {items_added} items. Errors: {len(errors)}")
        
        message = f"Import complete! Added {items_added} items from {row_num} total rows."
        if errors:
            message += f" {len(errors)} errors occurred."
        
        return jsonify({
            'success': True,
            'message': message,
            'items_added': items_added,
            'total_rows': row_num,
            'errors': errors  # Return ALL errors, not just first 10
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'}), 400