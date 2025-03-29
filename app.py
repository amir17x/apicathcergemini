import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import threading
# Temporarily disable bot import to make web interface work
# import bot

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Use PostgreSQL database
database_url = os.environ.get("DATABASE_URL")
# If DATABASE_URL starts with postgres://, replace it with postgresql:// as required by SQLAlchemy
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///bot.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Define models
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gmail = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    api_key = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'gmail': self.gmail,
            'api_key': self.api_key,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Create database tables
with app.app_context():
    db.create_all()

# Start the Telegram bot in a separate thread
def start_bot():
    # Temporarily disabled
    # bot.start_polling()
    logger.info("Bot start_polling is disabled temporarily")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status_page():
    return render_template('status.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accounts = Account.query.order_by(Account.created_at.desc()).all()
    return jsonify([account.to_dict() for account in accounts])

# Start the bot in a separate thread when the application starts
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("Telegram bot started in background thread")
