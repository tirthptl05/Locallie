from run import app, db
import app.models as models  # ensure this imports your models

with app.app_context():
    db.create_all()
