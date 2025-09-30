from app import create_app
from dotenv import load_dotenv

# *** ADD/MOVE THIS HERE: Load .env before importing application code ***
load_dotenv() 

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)