from run import app, db
from app.models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    users = User.query.all()
    for user in users:
        user.password = generate_password_hash("1234", method='pbkdf2:sha256')
    db.session.commit()
    print("✅ All passwords reset to '1234' using pbkdf2:sha256")
