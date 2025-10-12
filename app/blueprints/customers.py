"""
Customers Blueprint - Handles all customer-related operations
Includes: Customer CRUD, addresses, search, directory
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import Customer, CustomerAddress
from app.utils import validate_customer_data
import logging

logger = logging.getLogger(__name__)

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')


# API Routes
@customers_bp.route('/api/search')
@login_required
def search_customers():
    """Search customers by account number or name"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify([])

    customers = Customer.query.filter(
        db.or_(
            Customer.account_number.ilike(f'%{query}%'),
            Customer.name.ilike(f'%{query}%')
        )
    ).limit(20).all()

    # Use to_dict() - includes addresses array
    results = [customer.to_dict() for customer in customers]

    # Add display field
    for result in results:
        result['display'] = f"{result['account_number']} - {result['name']}"

    return jsonify(results)


@customers_bp.route('/api/directory')
@login_required
def get_customers_directory():
    """Get paginated customers for directory with optional search"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)  # Load 50 at a time
        search = request.args.get('search', '').strip()

        # Build query
        query = Customer.query

        # Apply search filter if provided
        if search:
            query = query.filter(
                db.or_(
                    Customer.account_number.ilike(f'%{search}%'),
                    Customer.name.ilike(f'%{search}%'),
                    Customer.contact_name.ilike(f'%{search}%')
                )
            )

        # Order and paginate
        query = query.order_by(Customer.name)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'customers': [{
                'id': customer.id,
                'account_number': customer.account_number,
                'name': customer.name,
                'contact_name': customer.contact_name,
                'phone': customer.phone,
                'email': customer.email
            } for customer in pagination.items],
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        })
    except Exception as e:
        logger.error(f"Error fetching customer directory: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@customers_bp.route('/api/<int:customer_id>')
@login_required
def get_customer(customer_id):
    """Get a specific customer"""
    customer = Customer.query.get_or_404(customer_id)
    return jsonify(customer.to_dict())


@customers_bp.route('/api', methods=['POST'])
@login_required
def create_customer():
    """Create a new customer"""
    data = request.json

    validation_errors = validate_customer_data(data)
    if validation_errors:
        return jsonify({
            'success': False,
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400

    try:
        # Check if account number already exists
        existing = Customer.query.filter_by(account_number=data['account_number']).first()
        if existing:
            return jsonify({'success': False, 'message': 'Account number already exists'}), 400

        # Validate addresses
        if 'addresses' not in data or len(data['addresses']) == 0:
            return jsonify({'success': False, 'message': 'At least one address is required'}), 400

        # Create customer
        customer = Customer(
            account_number=data['account_number'],
            name=data['name'],
            contact_name=data.get('contact_name', ''),
            phone=data.get('phone', ''),  # Main phone number
            email=data.get('email', ''),
            notes=data.get('notes', '')
        )

        db.session.add(customer)
        db.session.flush()  # Get the customer ID

        # Add addresses
        for idx, addr_data in enumerate(data['addresses']):
            if not addr_data.get('label'):
                return jsonify({'success': False, 'message': 'Each address must have a label'}), 400

            address = CustomerAddress(
                customer_id=customer.id,
                label=addr_data['label'],
                phone=addr_data.get('phone', ''),
                street=addr_data.get('street', ''),
                city=addr_data.get('city', ''),
                zip=addr_data.get('zip', ''),
                is_primary=(idx == 0)  # First address is primary
            )
            db.session.add(address)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Customer created successfully',
            'customer': customer.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating customer: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@customers_bp.route('/api/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    """Update customer details"""
    customer = Customer.query.get_or_404(customer_id)
    data = request.json

    try:
        # Update basic customer fields
        if 'account_number' in data:
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
        if 'notes' in data:
            customer.notes = data['notes']

        # Handle addresses
        if 'addresses' in data:
            # Remove old addresses
            CustomerAddress.query.filter_by(customer_id=customer_id).delete()

            # Add new addresses
            for idx, addr_data in enumerate(data['addresses']):
                if not addr_data.get('label'):
                    return jsonify({'success': False, 'message': 'Each address must have a label'}), 400

                address = CustomerAddress(
                    customer_id=customer_id,
                    label=addr_data['label'],
                    phone=addr_data.get('phone', ''),
                    street=addr_data.get('street', ''),
                    city=addr_data.get('city', ''),
                    zip=addr_data.get('zip', ''),
                    is_primary=(idx == 0)  # First address is primary
                )
                db.session.add(address)

        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Customer updated successfully',
            'customer': customer.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating customer {customer_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@customers_bp.route('/api/<int:customer_id>/addresses')
@login_required
def get_customer_addresses(customer_id):
    """Get all addresses for a customer"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        addresses = [addr.to_dict() for addr in customer.addresses]

        # Fallback to old single address field if no addresses exist
        if not addresses and customer.address:
            addresses = [{
                'id': None,
                'label': 'Primary',
                'phone': '',
                'street': customer.address,
                'city': '',
                'zip': '',
                'is_primary': True
            }]

        return jsonify(addresses)
    except Exception as e:
        logger.error(f"Error fetching addresses for customer {customer_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
