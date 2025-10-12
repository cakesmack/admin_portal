"""
Utility functions for the Highland Admin Portal application.

This module contains reusable validation, sanitization, and helper functions
used across multiple blueprints and routes.
"""

import logging
from app.models import Customer, CustomerAddress
from app import db
import bleach

logger = logging.getLogger(__name__)


# ==================== VALIDATION FUNCTIONS ====================

def validate_company_update(data):
    """
    Validate company update input data.

    Args:
        data (dict): Company update data to validate

    Returns:
        list: List of validation error messages (empty if valid)
    """
    errors = []

    # Required fields
    if not data.get('title') or not data.get('title').strip():
        errors.append('Title is required')

    if not data.get('message') or not data.get('message').strip():
        errors.append('Message is required')

    # Length validation
    if len(str(data.get('title', ''))) > 100:
        errors.append('Title too long (max 100 characters)')

    if len(str(data.get('message', ''))) > 5000:
        errors.append('Message too long (max 5000 characters)')

    # Validate priority
    if data.get('priority') and data['priority'] not in ['normal', 'important', 'urgent']:
        errors.append('Invalid priority level')

    return errors


def validate_customer_data(data):
    """
    Validate customer input data.

    Args:
        data (dict): Customer data to validate

    Returns:
        list: List of validation error messages (empty if valid)
    """
    errors = []

    # Required fields
    if not data.get('account_number') or not data.get('account_number').strip():
        errors.append('Account number is required')

    if not data.get('name') or not data.get('name').strip():
        errors.append('Customer name is required')

    # Length validation
    if len(str(data.get('account_number', ''))) > 50:
        errors.append('Account number too long (max 50 characters)')

    if len(str(data.get('name', ''))) > 100:
        errors.append('Customer name too long (max 100 characters)')

    if data.get('contact_name') and len(str(data['contact_name'])) > 100:
        errors.append('Contact name too long (max 100 characters)')

    if data.get('phone') and len(str(data['phone'])) > 20:
        errors.append('Phone number too long (max 20 characters)')

    if data.get('email') and len(str(data['email'])) > 100:
        errors.append('Email too long (max 100 characters)')

    # Email format validation (basic)
    if data.get('email'):
        email = str(data['email']).strip()
        if email and '@' not in email:
            errors.append('Invalid email format')

    return errors


# ==================== SANITIZATION FUNCTIONS ====================

def sanitize_html_content(html_content):
    """
    Sanitize HTML content to prevent XSS attacks.

    Args:
        html_content (str): Raw HTML content to sanitize

    Returns:
        str: Sanitized HTML content, or None if input is None

    Raises:
        None: Logs errors and returns original content on failure
    """
    if html_content is None:
        logger.warning("sanitize_html_content received None input")
        return None

    if not isinstance(html_content, str):
        logger.warning(f"sanitize_html_content received non-string input: {type(html_content)}")
        return str(html_content)  # Try to convert

    allowed_tags = [
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'a', 'img', 'ol', 'ul', 'li'
    ]
    allowed_attributes = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height', 'style']
    }
    allowed_protocols = ['http', 'https', 'mailto']

    try:
        result = bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        return result

    except Exception as e:
        logger.error(f"Error sanitizing HTML content: {e}", exc_info=True)
        return html_content  # Return original if sanitization fails


# ==================== ADDRESS HANDLING ====================

def handle_new_address_from_form(form_data, customer_account):
    """
    Handle creating a new address if the form submitted one.

    This function checks if a new address is being submitted via the form
    and creates it in the database if needed. It handles duplicate detection
    and returns the address label to use.

    Args:
        form_data (dict): Form data containing address information
        customer_account (str): Customer account number

    Returns:
        str: Address label to use, or None if no address specified

    Raises:
        None: Logs errors and returns None on failure
    """
    try:
        address_label = form_data.get('address_label', '')

        # Check if this is a new address
        if address_label == '__NEW__':
            logger.info(f"Creating new address for customer: {customer_account}")

            # Get customer
            customer = Customer.query.filter_by(account_number=customer_account).first()
            if not customer:
                logger.error(f"Customer not found: {customer_account}")
                return None

            # Get new address data from form
            new_label = form_data.get('new_address_label', '').strip()
            new_street = form_data.get('new_address_street', '').strip()
            new_city = form_data.get('new_address_city', '').strip()
            new_zip = form_data.get('new_address_zip', '').strip()
            new_phone = form_data.get('new_address_phone', '').strip()

            if not new_label:
                logger.error("No label provided for new address")
                return None

            # Check if this label already exists for this customer
            duplicate = CustomerAddress.query.filter_by(
                customer_id=customer.id,
                label=new_label
            ).first()

            if duplicate:
                logger.warning(f"Address with label '{new_label}' already exists for customer {customer.name}")
                return new_label

            # Create new address
            new_address = CustomerAddress(
                customer_id=customer.id,
                label=new_label,
                street=new_street,
                city=new_city,
                zip=new_zip,
                phone=new_phone,
                is_primary=False  # New addresses are not primary by default
            )

            db.session.add(new_address)
            db.session.flush()  # Get the ID but don't commit yet

            logger.info(f"Created new address '{new_label}' for customer {customer.name} (ID: {new_address.id})")

            return new_label

        # Return existing address label
        return address_label if address_label else None

    except Exception as e:
        logger.error(f"Error handling new address from form: {e}", exc_info=True)
        return None


# ==================== CATEGORY CONFIGURATION ====================

def get_category_config():
    """
    Get category configuration with colors for company updates.

    Returns:
        dict: Category configuration mapping category names to colors and display names
    """
    return {
        'general': {'color': '#6c757d', 'name': 'General'},
        'safety': {'color': '#dc3545', 'name': 'Safety'},
        'training': {'color': '#28a745', 'name': 'Training'},
        'product': {'color': '#007bff', 'name': 'Product Updates'},
        'events': {'color': '#6f42c1', 'name': 'Events'},
        'policy': {'color': '#fd7e14', 'name': 'Policy Changes'},
        'maintenance': {'color': '#20c997', 'name': 'Maintenance'},
        'announcement': {'color': '#e83e8c', 'name': 'Announcements'}
    }


# ==================== FILE VALIDATION ====================

def allowed_file(filename, allowed_extensions=None):
    """
    Check if a filename has an allowed extension.

    Args:
        filename (str): The filename to check
        allowed_extensions (set): Set of allowed extensions (default: common image types)

    Returns:
        bool: True if the file extension is allowed, False otherwise
    """
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions
