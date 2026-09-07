import os

basedir = os.path.abspath(os.path.dirname(__file__))
db_url = os.environ.get('DATABASE_URL')

if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'smart-expensive-tracker-secret-key-2026'
    SQLALCHEMY_DATABASE_URI = db_url or f"sqlite:///{os.path.join(basedir, 'instance', 'expenses.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    SERPAPI_API_KEY = os.environ.get('SERPAPI_API_KEY')

    # API Timeouts (seconds)
    SERPAPI_TIMEOUT = int(os.environ.get('SERPAPI_TIMEOUT', 12))
    GEMINI_TIMEOUT = int(os.environ.get('GEMINI_TIMEOUT', 15))

    # Rate Limiting (requests per minute per user/IP)
    RATE_LIMIT_SHOPPING = int(os.environ.get('RATE_LIMIT_SHOPPING', 15))
    RATE_LIMIT_CHATBOT = int(os.environ.get('RATE_LIMIT_CHATBOT', 20))
    RATE_LIMIT_OCR = int(os.environ.get('RATE_LIMIT_OCR', 10))
    RATE_LIMIT_VOICE = int(os.environ.get('RATE_LIMIT_VOICE', 10))