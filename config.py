import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///admin_portal.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False