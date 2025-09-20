from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ReturnsForm(FlaskForm):
    customer_account = StringField('Customer Account Number', validators=[DataRequired()])
    customer_name = StringField('Customer Name')
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
    product_code = StringField('Product Code')
    product_description = StringField('Product Description', validators=[DataRequired()])
    quantity = StringField('Quantity', validators=[DataRequired()])
    notes = TextAreaField('Special Instructions')
    submit = SubmitField('Submit Order Request')