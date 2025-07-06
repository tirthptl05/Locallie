from app import create_app
from app.extensions import db

app = create_app()

# ✅ This ensures db.create_all() runs within app context
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
