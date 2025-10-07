from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User
from app.forms import LoginForm, ForcePasswordChangeForm, ChangePasswordForm
from datetime import datetime


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        # Try login by email first, then username
        user = User.query.filter_by(email=form.username.data).first() or \
               User.query.filter_by(username=form.username.data).first()
        
        # Updated to use password hashing
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user)
            user.last_login = datetime.now()
            db.session.commit()
            
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            
            # Check if password change is required
            if user.must_change_password:
                return redirect(url_for('auth.force_password_change'))
            
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login unsuccessful. Please check your credentials.', 'danger')
    
    return render_template('login.html', title='Login', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/force-password-change', methods=['GET', 'POST'])
@login_required
def force_password_change():
    if not current_user.must_change_password:
        return redirect(url_for('main.dashboard'))
    
    form = ForcePasswordChangeForm()
    if form.validate_on_submit():
        # Use the new password hashing method
        current_user.set_password(form.new_password.data)
        current_user.must_change_password = False
        current_user.last_login = datetime.now()
        
        try:
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating password: {str(e)}', 'danger')
    
    return render_template('force_password_change.html', form=form)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Check current password using hash verification
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)
        
        # Set new password with hashing
        current_user.set_password(form.new_password.data)
        
        try:
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('main.user_profile', user_id=current_user.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
    
    return render_template('change_password.html', form=form)


