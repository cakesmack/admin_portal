from app import create_app, db
from app.models import User, Customer, Product, TodoItem, CompanyUpdate
from datetime import datetime

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
        ),
        Customer(
            account_number='CUST004',
            name='Inverness Sports Club',
            contact_name='Sarah Wilson',
            phone='01463 456789',
            email='sarah@invernesssports.com'
        ),
        Customer(
            account_number='CUST005',
            name='Highland University',
            contact_name='David Campbell',
            phone='01463 987654',
            email='david@highland-uni.ac.uk'
        )
    ]
    
    # Add sample products
    products = [
        Product(code='HYG001', name='Toilet Rolls (12 pack)', description='Premium quality toilet rolls'),
        Product(code='HYG002', name='Hand Soap Refill', description='Antibacterial hand soap refill 5L'),
        Product(code='CAT001', name='Disposable Plates', description='Biodegradable disposable plates (pack of 50)'),
        Product(code='CAT002', name='Plastic Cutlery Pack', description='Disposable cutlery set (100 pieces)')
    ]
    
    # Add to session and commit users first
    db.session.add(admin_user)
    db.session.add(test_user)
    db.session.commit()
    
    # Add sample todo items for admin user
    admin_todos = [
        TodoItem(text='Review monthly sales report', user_id=admin_user.id),
        TodoItem(text='Update customer database', user_id=admin_user.id),
        TodoItem(text='Schedule team meeting', user_id=admin_user.id, completed=True)
    ]
    
    # Add sample company updates
    sample_updates = [
        CompanyUpdate(
            title='System Maintenance Scheduled',
            message='The admin portal will be under maintenance this Saturday from 2-4 PM for system updates.',
            priority='important',
            sticky=True,
            user_id=admin_user.id
        ),
        CompanyUpdate(
            title='New Product Line Available',
            message='We now have a new eco-friendly product line available for all customers. Contact sales for more information.',
            priority='normal',
            user_id=admin_user.id
        ),
        CompanyUpdate(
            title='Monthly Team Meeting',
            message='Monthly team meeting to discuss Q4 targets and customer feedback.',
            priority='normal',
            is_event=True,
            event_date=datetime(2024, 12, 15, 10, 0),  # Sample meeting date
            user_id=admin_user.id
        )
    ]
    
    # Add customers, products, todos, and updates
    for customer in customers:
        db.session.add(customer)
    
    for product in products:
        db.session.add(product)
        
    for todo in admin_todos:
        db.session.add(todo)
        
    for update in sample_updates:
        db.session.add(update)
    
    db.session.commit()
    
    print("Database initialized successfully!")
    print("\nTest credentials:")
    print("Username: admin, Password: admin123")
    print("Username: user, Password: user123")
    print("\nSample data created:")
    print(f"- {len(customers)} customers")
    print(f"- {len(products)} products") 
    print(f"- {len(admin_todos)} todo items for admin")
    print(f"- {len(sample_updates)} company updates")