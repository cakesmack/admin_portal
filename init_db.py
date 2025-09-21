from app import create_app, db
from app.models import User, Customer, Product

app = create_app()

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()
    
    # Create test users
    admin_user = User(
        username='admin',
        password='admin123',  # In production, use proper hashing!
        role='admin'
    )
    
    test_user = User(
        username='user',
        password='user123',
        role='user'
    )
    
    # Add sample customers
    customers = [
        Customer(
            account_number='CUST001',
            name='Highland Hotel',
            contact_name='John Smith',
            phone='01463 123456',
            email='john@highlandhotel.com'
        ),
        Customer(
            account_number='CUST002',
            name='Lochside Restaurant',
            contact_name='Emma Brown',
            phone='01463 654321',
            email='emma@lochside.com'
        ),
        Customer(
            account_number='CUST003',
            name='Cafe Ness',
            contact_name='Robert Johnson',
            phone='01463 789123',
            email='robert@cafeness.com'
        )
    ]
    
    # Add sample products
    products = [
        Product(code='HYG001', name='Toilet Rolls (12 pack)', description='Premium quality toilet rolls'),
        Product(code='HYG002', name='Hand Soap Refill', description='Antibacterial hand soap refill 5L'),
        Product(code='CAT001', name='Disposable Plates', description='Biodegradable disposable plates (pack of 50)'),
        Product(code='CAT002', name='Plastic Cutlery Pack', description='Disposable cutlery set (100 pieces)')
    ]
    
    # Add to session and commit
    db.session.add(admin_user)
    db.session.add(test_user)
    
    for customer in customers:
        db.session.add(customer)
    
    for product in products:
        db.session.add(product)
    
    db.session.commit()
    
    print("Database initialized successfully!")
    print("\nTest credentials:")
    print("Username: admin, Password: admin123")
    print("Username: user, Password: user123")