"""
Company Updates Blueprint - Handles company-wide announcements and updates
Includes: CRUD operations, image uploads, categories
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import User, CompanyUpdate
from app.utils import validate_company_update, sanitize_html_content, get_category_config, allowed_file
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import uuid
import logging

logger = logging.getLogger(__name__)

company_updates_bp = Blueprint('company_updates', __name__, url_prefix='/company-updates')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB


def ensure_upload_dir():
    """Create upload directory if it doesn't exist"""
    now = datetime.now()
    upload_dir = os.path.join('static', 'uploads', 'company_updates', str(now.year), f"{now.month:02d}")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    return upload_dir


def resize_image(image_path, max_width=800, max_height=600):
    """Resize image while maintaining aspect ratio"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG saving)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')

            # Calculate new dimensions
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save optimized image
            img.save(image_path, 'JPEG', quality=85, optimize=True)
    except Exception as e:
        logger.error(f"Error resizing image: {e}", exc_info=True)


# API Routes
@company_updates_bp.route('/api', methods=['GET'])
@login_required
def get_company_updates():
    """Get all company updates"""
    try:
        updates = CompanyUpdate.query.join(User).order_by(
            CompanyUpdate.sticky.desc(),
            CompanyUpdate.created_at.desc()
        ).limit(20).all()

        return jsonify([{
            'id': update.id,
            'title': update.title,
            'message': update.message,
            'category': getattr(update, 'category', 'general'),
            'priority': update.priority,
            'sticky': update.sticky,
            'is_event': update.is_event,
            'event_date': update.event_date.isoformat() if update.event_date else None,
            'created_at': update.created_at.isoformat(),
            'author_name': update.author.username,
            'can_delete': update.user_id == current_user.id
        } for update in updates])
    except Exception as e:
        logger.error(f"Error fetching company updates: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@company_updates_bp.route('/api/<int:update_id>', methods=['GET'])
@login_required
def get_company_update(update_id):
    """Get a specific company update for editing"""
    try:
        update = CompanyUpdate.query.get_or_404(update_id)

        # Only allow the author to view for editing (or admins)
        if update.user_id != current_user.id and current_user.role != 'admin':
            return jsonify({'error': 'Permission denied'}), 403

        return jsonify({
            'id': update.id,
            'title': update.title,
            'message': update.message,
            'category': getattr(update, 'category', 'general'),
            'priority': update.priority,
            'sticky': update.sticky,
            'is_event': update.is_event,
            'event_date': update.event_date.isoformat() if update.event_date else None,
            'created_at': update.created_at.isoformat(),
            'author_name': update.author.username,
            'can_delete': True
        })
    except Exception as e:
        logger.error(f"Error fetching update {update_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch update'}), 500


@company_updates_bp.route('/api/categories')
@login_required
def get_categories():
    """Get available categories for company updates"""
    return jsonify(get_category_config())


@company_updates_bp.route('/api', methods=['POST'])
@login_required
def create_company_update():
    """Create a new company update"""
    data = request.json

    validation_errors = validate_company_update(data)
    if validation_errors:
        return jsonify({
            'success': False,
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400

    try:
        # Validate required fields
        if not data.get('title') or not data.get('message'):
            return jsonify({'success': False, 'message': 'Title and message are required'}), 400

        # Sanitize the message content
        message = sanitize_html_content(data['message'])
        if not message:
            return jsonify({'success': False, 'message': 'Message content is required'}), 400

        # Create new update
        update = CompanyUpdate(
            title=data['title'].strip(),
            message=message,
            category=data.get('category', 'general'),
            priority=data.get('priority', 'normal'),
            sticky=bool(data.get('sticky', False)),
            is_event=bool(data.get('is_event', False)),
            user_id=current_user.id
        )

        # Handle event date
        if update.is_event and data.get('event_date'):
            try:
                update.event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
            except ValueError:
                update.event_date = None

        db.session.add(update)
        db.session.commit()

        return jsonify({'success': True, 'id': update.id})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating company update: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@company_updates_bp.route('/api/<int:update_id>', methods=['PUT'])
@login_required
def update_company_update(update_id):
    """Update an existing company update"""
    update = CompanyUpdate.query.get_or_404(update_id)

    # Only allow the author to edit
    if update.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.json

    validation_errors = validate_company_update(data)
    if validation_errors:
        return jsonify({
            'success': False,
            'message': 'Validation errors: ' + '; '.join(validation_errors)
        }), 400

    try:
        # Validate required fields
        if not data.get('title') or not data.get('message'):
            return jsonify({'success': False, 'message': 'Title and message are required'}), 400

        # Sanitize the message content
        message = sanitize_html_content(data['message'])
        if not message:
            return jsonify({'success': False, 'message': 'Message content is required'}), 400

        # Update the fields
        update.title = data['title'].strip()
        update.message = message
        update.category = data.get('category', 'general')
        update.priority = data.get('priority', 'normal')
        update.sticky = bool(data.get('sticky', False))
        update.is_event = bool(data.get('is_event', False))

        # Handle event date
        if update.is_event and data.get('event_date'):
            try:
                update.event_date = datetime.fromisoformat(data['event_date'].replace('Z', '+00:00'))
            except ValueError:
                update.event_date = None
        else:
            update.event_date = None

        db.session.commit()

        return jsonify({'success': True, 'id': update.id})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating company update {update_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@company_updates_bp.route('/api/<int:update_id>', methods=['DELETE'])
@login_required
def delete_company_update(update_id):
    """Delete a company update"""
    try:
        update = CompanyUpdate.query.filter_by(id=update_id, user_id=current_user.id).first_or_404()
        db.session.delete(update)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting company update {update_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400


@company_updates_bp.route('/api/upload-image', methods=['POST'])
@login_required
def upload_image():
    """Handle image uploads for company updates"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No image file provided'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WebP files.'}), 400

    # Check file size
    if len(file.read()) > MAX_IMAGE_SIZE:
        return jsonify({'success': False, 'message': 'File too large. Maximum size is 2MB.'}), 400

    file.seek(0)  # Reset file pointer after reading

    try:
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{uuid.uuid4().hex[:8]}_{name}{ext}"

        # Create upload directory
        upload_dir = ensure_upload_dir()
        file_path = os.path.join(upload_dir, unique_filename)

        # Save file
        file.save(file_path)

        # Resize image
        resize_image(file_path)

        # Return URL for frontend
        from flask import url_for
        image_url = url_for('static', filename=file_path.replace('static/', ''))

        return jsonify({
            'success': True,
            'image_url': image_url,
            'message': 'Image uploaded successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading image: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500
