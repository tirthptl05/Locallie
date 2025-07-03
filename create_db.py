from app import app, db
import models  # ensure this imports your models

with app.app_context():
    db.create_all()
