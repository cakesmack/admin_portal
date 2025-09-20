from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    
    # Create sample users
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='admin123', role='administrator')
        db.session.add(admin_user)
    
    if not User.query.filter_by(username='sales1').first():
        sales_user = User(username='sales1', password='sales123', role='sales_admin')
        db.session.add(sales_user)
    
    if not User.query.filter_by(username='sales2').first():
        sales_user2 = User(username='sales2', password='sales123', role='sales_admin')
        db.session.add(sales_user2)
    
    db.session.commit()
    print("Database initialized with sample users!")
    print("Username: admin, Password: admin123")
    print("Username: sales1, Password: sales123")
    print("Username: sales2, Password: sales123")