from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, BooleanField, TextAreaField, IntegerField, PasswordField, TelField, FormField, FieldList
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo, optional
from wtforms.widgets import TextArea

class CreateUserForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('staff', 'Staff'), ('admin', 'Admin')], validators=[DataRequired()])
    job_title = StringField('Job Title', validators=[Optional(), Length(max=100)])
    direct_phone = TelField('Direct Phone', validators=[Optional()])
    mobile_phone = TelField('Mobile Phone', validators=[Optional()])
    
class EditUserForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('staff', 'Staff'), ('admin', 'Admin')], validators=[DataRequired()])
    job_title = StringField('Job Title', validators=[Optional(), Length(max=100)])
    direct_phone = TelField('Direct Phone', validators=[Optional()])
    mobile_phone = TelField('Mobile Phone', validators=[Optional()])
    is_active = BooleanField('Account Active')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])

class ForcePasswordChangeForm(FlaskForm):
    new_password = PasswordField('Set Your Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class ProductReturnForm(FlaskForm):
    """Subform for individual product returns"""
    product_code = StringField('Product Code', validators=[DataRequired()])
    product_name = StringField('Product Name', validators=[DataRequired()])
    quantity = StringField('Quantity', validators=[DataRequired()])

class ReturnsForm(FlaskForm):
    customer_account = StringField('Customer Account Number', validators=[DataRequired()])
    customer_name = StringField('Customer Name')
    customer_address = StringField('Customer Address')
    
    # Keep the original single product fields for now, but we'll handle multiple via JavaScript
    product_code = StringField('Product Code', validators=[DataRequired()])
    product_name = StringField('Product Name')
    quantity = StringField('Quantity', validators=[DataRequired()])
    
    reason = SelectField('Reason for Return', choices=[
        ('damaged', 'Damaged Product'),
        ('wrong', 'Wrong Product Sent'),
        ('overstock', 'Overstocked'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    notes = TextAreaField('Additional Notes')
    submit = SubmitField('Generate Return Form')

class BrandedStockForm(FlaskForm):
    customer_account = StringField('Customer Account Number', validators=[DataRequired()])
    customer_name = StringField('Customer Name')
    product_code = StringField('Product Code', validators=[DataRequired()])
    product_name = StringField('Product Name')
    quantity_delivered = StringField('Quantity Delivered', validators=[DataRequired()])
    current_stock = StringField('Current Stock Level', validators=[DataRequired()])
    submit = SubmitField('Record Delivery')

class InvoiceCorrectionForm(FlaskForm):
    invoice_number = StringField('Invoice Number', validators=[DataRequired()])
    customer_account = StringField('Customer Account Number', validators=[DataRequired()])
    product_code = StringField('Product Code', validators=[DataRequired()])
    ordered_quantity = StringField('Ordered Quantity', validators=[DataRequired()])
    delivered_quantity = StringField('Delivered Quantity', validators=[DataRequired()])
    notes = TextAreaField('Correction Notes')
    submit = SubmitField('Record Correction')

class SpecialOrderForm(FlaskForm):
    supplier = StringField('Supplier Name', validators=[DataRequired()])
    customer_account = StringField('Customer Account Number', validators=[DataRequired()])
    customer_name = StringField('Customer Account Name', validators=[DataRequired()])
    product_code = StringField('Product Code')
    product_description = StringField('Product Description', validators=[DataRequired()])
    quantity = StringField('Quantity', validators=[DataRequired()])
    cost_price = IntegerField('Cost Price', validators=[DataRequired()])
    sell_price = IntegerField('Sell Price', validators=[DataRequired()])
    notes = TextAreaField('Special Instructions')
    submit = SubmitField('Submit Order Request')

