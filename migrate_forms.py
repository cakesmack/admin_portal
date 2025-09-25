# migrate_forms.py
# Run this script to add the new columns to your existing database

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Add new columns to Form table
    try:
        # Check if columns already exist
        result = db.session.execute(text("PRAGMA table_info(form)"))
        columns = [row[1] for row in result]
        
        if 'is_completed' not in columns:
            db.session.execute(text('ALTER TABLE form ADD COLUMN is_completed BOOLEAN DEFAULT 0'))
            print("Added is_completed column")
        
        if 'completed_date' not in columns:
            db.session.execute(text('ALTER TABLE form ADD COLUMN completed_date DATETIME'))
            print("Added completed_date column")
        
        if 'completed_by' not in columns:
            db.session.execute(text('ALTER TABLE form ADD COLUMN completed_by INTEGER'))
            print("Added completed_by column")
        
        if 'is_archived' not in columns:
            db.session.execute(text('ALTER TABLE form ADD COLUMN is_archived BOOLEAN DEFAULT 0'))
            print("Added is_archived column")
        
        db.session.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db.session.rollback()

print("\nMigration complete! You may need to restart your Flask application.")