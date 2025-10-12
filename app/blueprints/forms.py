"""
Forms Blueprint - Handles all form-related operations
Includes: Returns, Invoice Corrections, Branded Stock, Form management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import current_user, login_required
from app import db
from app.models import User, Customer, Form
from app.forms import ReturnsForm, BrandedStockForm, InvoiceCorrectionForm
from app.utils import handle_new_address_from_form
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

forms_bp = Blueprint('forms', __name__, url_prefix='/forms')


@forms_bp.route('/returns', methods=['GET', 'POST'])
@login_required
def returns():
    """Handle returns form submission"""
    logger.debug(f"Returns route accessed - Method: {request.method}")
    logger.debug(f"Form data keys: {list(request.form.keys())}")

    form = ReturnsForm()

    if not form.validate_on_submit() and request.method == 'POST':
        logger.warning(f"Form validation errors: {form.errors}")

    if form.validate_on_submit():
        logger.info("Processing returns form submission")

        # Handle new address creation
        address_label = handle_new_address_from_form(
            request.form,
            form.customer_account.data
        )

        # Update customer address if provided
        if form.customer_account.data and form.customer_address.data:
            customer = Customer.query.filter_by(account_number=form.customer_account.data).first()
            if customer and form.customer_address.data != customer.address:
                customer.address = form.customer_address.data

        # Get products from the form
        products_data = []

        # Check for additional products submitted via JavaScript
        additional_products = request.form.getlist('additional_products')
        if additional_products:
            try:
                products_data = json.loads(additional_products[0])
            except:
                products_data = []

        # Add the main product
        if form.product_code.data:
            products_data.insert(0, {
                'product_code': form.product_code.data,
                'product_name': form.product_name.data,
                'quantity': form.quantity.data
            })

        # Create form data
        form_data = {
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'customer_address': form.customer_address.data,
            'address_label': address_label,
            'products': products_data,
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

        flash(f'Return form #{new_form.id} has been created successfully!', 'success')

        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({
                'success': True,
                'form_id': new_form.id,
                'message': f'Return form #{new_form.id} has been created successfully!'
            })
        else:
            # Return JavaScript for regular form submission
            return f'''
            <script>
                window.open('{url_for('forms.print_form', form_id=new_form.id)}', '_blank');
                window.location.href = '{url_for('main.dashboard')}';
            </script>
            '''

    return render_template('returns_form.html', title='Returns Form', form=form)


@forms_bp.route('/invoice-correction', methods=['GET', 'POST'])
@login_required
def invoice_correction():
    """Handle invoice correction form submission"""
    form = InvoiceCorrectionForm()

    if form.validate_on_submit():
        # Handle new address creation
        address_label = handle_new_address_from_form(
            request.form,
            form.customer_account.data
        )

        # Build main product data
        main_product = {
            'product_code': form.product_code.data,
            'product_name': form.product_name.data,
            'ordered_quantity': int(form.ordered_quantity.data or 0),
            'delivered_quantity': int(form.delivered_quantity.data or 0),
            'outstanding_quantity': int(form.ordered_quantity.data or 0) - int(form.delivered_quantity.data or 0)
        }

        # Get additional products from hidden field
        additional_products_json = request.form.get('additional_products', '[]')
        try:
            additional_products = json.loads(additional_products_json)
        except json.JSONDecodeError:
            additional_products = []

        # Combine main product with additional products
        products_data = [main_product] + additional_products

        # Build form data dict
        form_data = {
            'invoice_number': form.invoice_number.data,
            'customer_account': form.customer_account.data,
            'customer_name': form.customer_name.data,
            'customer_address': form.customer_address.data,
            'address_label': address_label,
            'products': products_data,
            'notes': form.notes.data
        }

        # Create new form record
        new_form = Form(
            type='invoice_correction',
            data=json.dumps(form_data),
            user_id=current_user.id
        )

        db.session.add(new_form)
        db.session.commit()

        flash(f'Invoice correction form #{new_form.id} created successfully!', 'success')

        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({
                'success': True,
                'form_id': new_form.id,
                'message': f'Invoice correction form #{new_form.id} has been created successfully!'
            })
        else:
            # Return JavaScript for regular form submission
            return f'''
            <script>
                window.open('{url_for('forms.print_form', form_id=new_form.id)}', '_blank');
                window.location.href = '{url_for('main.dashboard')}';
            </script>
            '''

    return render_template('invoice_correction.html', title='Invoice Correction', form=form)


@forms_bp.route('/')
@login_required
def list_forms():
    """List all forms with filtering and pagination"""
    # Get filter parameters
    form_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    submitted_by = request.args.get('submitted_by', '')
    customer_search = request.args.get('customer', '')
    show_archived = request.args.get('show_archived', 'false') == 'true'

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = min(per_page, 100)  # Cap at 100 items per page

    # Base query
    query = Form.query

    # Apply archived filter
    if not show_archived:
        query = query.filter_by(is_archived=False)

    # Apply filters
    if form_type:
        query = query.filter(Form.type == form_type)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Form.date_created >= date_from_obj)
        except:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(Form.date_created <= date_to_obj)
        except:
            pass

    if submitted_by:
        query = query.join(User, Form.user_id == User.id).filter(User.username.ilike(f'%{submitted_by}%'))

    # Order by date (most recent first)
    query = query.order_by(Form.date_created.desc())

    # Handle customer search (needs special handling due to JSON field)
    if customer_search:
        # For customer search, we need to load all forms and filter in Python
        # This is less efficient but necessary due to JSON field
        all_forms = query.all()
        filtered_forms = []
        for form in all_forms:
            form_data = json.loads(form.data)
            customer_account = form_data.get('customer_account', '')
            customer_name = form_data.get('customer_name', '')
            if customer_search.lower() in customer_account.lower() or customer_search.lower() in customer_name.lower():
                filtered_forms.append(form)

        # Manual pagination for filtered results
        total = len(filtered_forms)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_forms = filtered_forms[start:end]

        # Calculate pagination info
        total_pages = (total + per_page - 1) // per_page
    else:
        # Use database pagination for better performance
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        paginated_forms = pagination.items
        total = pagination.total
        total_pages = pagination.pages

    # Prepare forms with data
    forms_with_data = []
    for form in paginated_forms:
        form_data = json.loads(form.data)
        form_dict = {
            'id': form.id,
            'type': form.type.replace('_', ' ').title(),
            'type_raw': form.type,
            'date_created': form.date_created,
            'author': User.query.get(form.user_id).username if User.query.get(form.user_id) else 'Unknown',
            'data': form_data,
            'customer_account': form_data.get('customer_account', 'N/A'),
            'customer_name': form_data.get('customer_name', 'N/A'),
            'is_completed': form.is_completed,
            'completed_date': form.completed_date,
            'completed_by': User.query.get(form.completed_by).username if form.completed_by else None,
            'is_archived': form.is_archived
        }
        forms_with_data.append(form_dict)

    # Get unique form types for filter dropdown
    unique_types = db.session.query(Form.type).distinct().all()
    form_types = [t[0] for t in unique_types]

    # Get all users for filter dropdown
    all_users = User.query.all()

    # Calculate pagination info
    has_prev = page > 1
    has_next = page < total_pages

    logger.info(f"Forms list - Page {page}/{total_pages}, Total forms: {total}")

    return render_template('forms.html',
                         title='All Forms',
                         forms=forms_with_data,
                         form_types=form_types,
                         all_users=all_users,
                         current_filters={
                             'type': form_type,
                             'date_from': date_from,
                             'date_to': date_to,
                             'submitted_by': submitted_by,
                             'customer': customer_search,
                             'show_archived': show_archived
                         },
                         pagination={
                             'page': page,
                             'per_page': per_page,
                             'total': total,
                             'total_pages': total_pages,
                             'has_prev': has_prev,
                             'has_next': has_next
                         })


@forms_bp.route('/<int:form_id>')
@login_required
def view_form(form_id):
    """View a specific form"""
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


@forms_bp.route('/<int:form_id>/complete', methods=['POST'])
@login_required
def complete_form(form_id):
    """Mark a form as completed"""
    form = Form.query.get_or_404(form_id)

    try:
        form.is_completed = True
        form.completed_date = datetime.now()
        form.completed_by = current_user.id

        db.session.commit()
        return jsonify({'success': True, 'message': 'Form marked as completed'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@forms_bp.route('/<int:form_id>/archive', methods=['POST'])
@login_required
def archive_form(form_id):
    """Archive a form"""
    form = Form.query.get_or_404(form_id)

    try:
        form.is_archived = True
        if not form.is_completed:
            form.is_completed = True
            form.completed_date = datetime.now()
            form.completed_by = current_user.id

        db.session.commit()
        return jsonify({'success': True, 'message': 'Form archived successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@forms_bp.route('/<int:form_id>/unarchive', methods=['POST'])
@login_required
def unarchive_form(form_id):
    """Restore a form from archive"""
    form = Form.query.get_or_404(form_id)

    try:
        form.is_archived = False
        db.session.commit()
        return jsonify({'success': True, 'message': 'Form restored from archive'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400


@forms_bp.route('/print/<int:form_id>')
@login_required
def print_form(form_id):
    """Print a form"""
    form = Form.query.get_or_404(form_id)
    form_data = json.loads(form.data)
    user = User.query.get(form.user_id)
    author = user.username if user else 'Unknown'

    # Determine which template to use based on form type
    if form.type == 'branded_stock':
        return render_template(
            'print_branded_stock.html',
            title=f'Stock Order - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )
    elif form.type == 'invoice_correction':
        return render_template(
            'print_invoice_correction.html',
            title=f'Invoice Correction - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )
    else:
        # Default to returns/credit uplift template
        return render_template(
            'print_form.html',
            title=f'{form.type.replace("_", " ").title()} - #{form_id}',
            form_type=form.type,
            form_data=form_data,
            author=author,
            date_created=form.date_created,
            form_id=form_id,
            company_name='Highland Industrial Supplies'
        )


# API Routes
@forms_bp.route('/api/recent', methods=['GET'])
@login_required
def get_recent_forms():
    """Get recent forms for dashboard"""
    try:
        forms = Form.query.filter_by(is_archived=False).join(
            User, Form.user_id == User.id
        ).order_by(Form.date_created.desc()).limit(5).all()

        result = []
        for form in forms:
            form_data = json.loads(form.data)
            result.append({
                'id': form.id,
                'type': form.type.replace('_', ' ').title(),
                'date_created': form.date_created.isoformat(),
                'author': form.author.username,
                'customer_account': form_data.get('customer_account', 'N/A'),
                'customer_name': form_data.get('customer_name', 'N/A'),
                'is_completed': form.is_completed
            })

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching recent forms: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
