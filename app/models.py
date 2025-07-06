from app.extensions import db

# ---------------------- User Table ----------------------
class User(db.Model):
    __tablename__ = 'users'  # must match the DB table

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))  # 'traveler' or 'local'
    gender = db.Column(db.String(10))
    city = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)

    # 🔗 Link to HelpRequests created by this user
    requests = db.relationship(
        'HelpRequest',
        backref='user',
        lazy=True,
        foreign_keys='HelpRequest.user_id'
    )

    # 🔗 Link to HelpRequests accepted by this local (optional)
    accepted_requests = db.relationship(
        'HelpRequest',
        backref='accepted_by_user',
        lazy=True,
        foreign_keys='HelpRequest.accepted_by'
    )


# ---------------------- HelpRequest Table ----------------------
class HelpRequest(db.Model):
    __tablename__ = 'help_request'

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    query_text = db.Column(db.Text)  # ✅ rename from `query` to `query_text`
    email_alert = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=db.func.now())

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    accepted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    # local who accepted


# ---------------------- Reply Table ----------------------
class Reply(db.Model):
    __tablename__ = 'help_replies'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())

    help_request_id = db.Column(db.Integer, db.ForeignKey('help_request.id'))
    local_id = db.Column(db.Integer, db.ForeignKey('users.id'))


# ---------------------- Feedback Table ----------------------
class Feedback(db.Model):
    __tablename__ = 'platform_feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    user_role = db.Column(db.String(20))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')
    timestamp = db.Column(db.DateTime, default=db.func.now())
