# generate_secret_key.py
# Generate a secure SECRET_KEY for production

import secrets
import os
from pathlib import Path

def generate_secret_key():
    """Generate a cryptographically secure secret key"""
    return secrets.token_hex(32)  # 64 character hex string

def setup_env_file():
    """Create or update .env file with SECRET_KEY"""
    
    # Generate new secret key
    secret_key = generate_secret_key()
    
    print("🔐 SECRET_KEY SETUP")
    print("=" * 30)
    print(f"Generated SECRET_KEY: {secret_key}")
    print(f"Length: {len(secret_key)} characters")
    
    # Check if .env file exists
    env_file = Path('.env')
    
    if env_file.exists():
        print(f"\n⚠️  .env file already exists!")
        
        # Read existing content
        with open('.env', 'r') as f:
            content = f.read()
        
        if 'SECRET_KEY=' in content:
            print("Found existing SECRET_KEY in .env file")
            choice = input("Replace existing SECRET_KEY? (y/N): ").lower().strip()
            if choice != 'y':
                print("Keeping existing SECRET_KEY")
                return
        
        # Update existing file
        lines = content.split('\n')
        updated_lines = []
        secret_key_found = False
        
        for line in lines:
            if line.startswith('SECRET_KEY='):
                updated_lines.append(f'SECRET_KEY={secret_key}')
                secret_key_found = True
                print("✓ Updated existing SECRET_KEY")
            else:
                updated_lines.append(line)
        
        # Add SECRET_KEY if it wasn't found
        if not secret_key_found:
            updated_lines.append(f'SECRET_KEY={secret_key}')
            print("✓ Added SECRET_KEY to existing .env file")
        
        # Write updated content
        with open('.env', 'w') as f:
            f.write('\n'.join(updated_lines))
    
    else:
        # Create new .env file
        print("\n📝 Creating new .env file...")
        
        env_content = f"""# Environment variables for Hygiene & Catering Admin Portal
# Generated on {secrets.token_hex(4)}

# CRITICAL: Flask Secret Key - Keep this secret!
SECRET_KEY={secret_key}

# Environment setting
FLASK_ENV=production

# Database configuration
DATABASE_URL=sqlite:///admin_portal.db

# Upload settings (if needed later)
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# Security settings
SESSION_COOKIE_SECURE=true
"""
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✓ Created .env file with all necessary variables")
    
    # Check .gitignore
    gitignore_file = Path('.gitignore')
    
    if gitignore_file.exists():
        with open('.gitignore', 'r') as f:
            gitignore_content = f.read()
        
        if '.env' not in gitignore_content:
            print("\n⚠️  Adding .env to .gitignore...")
            with open('.gitignore', 'a') as f:
                f.write('\n# Environment variables\n.env\n')
            print("✓ Added .env to .gitignore")
        else:
            print("✓ .env already in .gitignore")
    else:
        print("\n📝 Creating .gitignore file...")
        gitignore_content = """# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.env

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Flask
instance/
.flaskenv

# Uploads
uploads/
"""
        with open('.gitignore', 'w') as f:
            f.write(gitignore_content)
        print("✓ Created .gitignore file")
    
    print("\n" + "=" * 50)
    print("🎉 SECRET_KEY SETUP COMPLETE!")
    print("=" * 50)
    print("✅ Cryptographically secure SECRET_KEY generated")
    print("✅ .env file created/updated")
    print("✅ .gitignore configured")
    
    print("\n🔒 SECURITY REMINDERS:")
    print("• Never commit .env file to version control")
    print("• Keep your SECRET_KEY private")
    print("• Use a different SECRET_KEY for each environment")
    print("• Backup your .env file securely")
    
    print("\n📝 NEXT STEPS:")
    print("1. Verify .env file is in .gitignore")
    print("2. Test that Flask can load the SECRET_KEY")
    print("3. Proceed with production setup")

def test_secret_key():
    """Test that the SECRET_KEY loads correctly"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        secret_key = os.environ.get('SECRET_KEY')
        
        if secret_key:
            print(f"\n✅ SECRET_KEY loaded successfully!")
            print(f"   Length: {len(secret_key)} characters")
            print(f"   Preview: {secret_key[:8]}...{secret_key[-8:]}")
            return True
        else:
            print("\n❌ SECRET_KEY not found in environment!")
            return False
            
    except ImportError:
        print("\n⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
        return False
    except Exception as e:
        print(f"\n❌ Error loading SECRET_KEY: {e}")
        return False

if __name__ == "__main__":
    try:
        print("🔐 Setting up SECRET_KEY for production...")
        setup_env_file()
        
        print("\n🧪 Testing SECRET_KEY loading...")
        test_secret_key()
        
    except KeyboardInterrupt:
        print("\n⚠️  Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()