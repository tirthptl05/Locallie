from app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))  # 'tourist' or 'local'
    gender = db.Column(db.String(10))
    requests = db.relationship('HelpRequest', backref='user', lazy=True)

class HelpRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    query = db.Column(db.Text)
    email_alert = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="Open")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Reply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    message = db.Column(db.Text)
    help_request_id = db.Column(db.Integer, db.ForeignKey('help_request.id'))
    local_id = db.Column(db.Integer, db.ForeignKey('user.id'))
