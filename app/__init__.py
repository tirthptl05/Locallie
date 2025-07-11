from flask import Flask
from .extensions import db, mail
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os

load_dotenv()  # ✅ Load environment variables from .env

socketio = SocketIO(cors_allowed_origins="*")  # ✅ Define only ONCE

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
    app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')

    db.init_app(app)
    mail.init_app(app)
    socketio.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    return app
