import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'aapki-secret-key-yahan-dalo'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///expenses.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False