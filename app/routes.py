from flask import Blueprint
main = Blueprint('main', __name__)

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_mail import Mail, Message
from flask import jsonify
from app import socketio



import os

# ✅ Load environment variables first
load_dotenv()

# ✅ Create app instance
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ✅ Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ✅ Configure mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')

# ✅ Import and initialize extensions
from app.extensions import db  # this should be: db = SQLAlchemy()

mail = Mail(app)

# ✅ Import models AFTER db is initialized to avoid circular import
from app.models import User, HelpRequest, Feedback, Reply


def send_email(to_email, subject, body):
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")


@main.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response


@main.route("/")
def index():
    return render_template("index.html")


@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role')
        city = request.form.get('city')  # now required for all roles


        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')


        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already exists.")
            return redirect('/signup')

        try:
            new_user = User(name=name, email=email, password=hashed_password, role=role, city=city)
            db.session.add(new_user)
            db.session.commit()

            if role == 'local':
                session['city'] = city

            flash("Signup successful! You can now log in.")
            return redirect('/signin')

        except Exception as e:
            print("DB Error:", e)
            flash("Something went wrong.")
            return redirect('/signup')

    return render_template('signup.html')


@main.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        # Fetch user using SQLAlchemy
        user = User.query.filter_by(email=email).first()

        if user:
            if check_password_hash(user.password, password):
                # Set session
                session['user_id'] = user.id
                session['name'] = user.name
                session['email'] = user.email
                session['role'] = user.role
                session['city'] = user.city

                # Save city in session for locals
                if user.role == 'local' and user.city:
                    session['city'] = user.city

                flash("Login successful!")

                # Redirect by role
                return redirect('/tourist') if user.role == 'traveler' else redirect('/local')
            else:
                flash("Incorrect password.")
                return redirect('/signin')
        else:
            flash("Email not found.")
            return redirect('/signin')

    return render_template("signin.html")


@main.route('/tourist')
def tourist_dashboard():
    # Ensure user is logged in
    if 'user_id' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('main.signin'))

    # Ensure only travelers can access this route
    if session.get('role') != 'traveler':
        flash("Access denied: Only travelers allowed.")
        return redirect(url_for('main.signin'))

    return render_template('tourist_dashboard.html')


@main.route('/local')
def local_dashboard():
    # Ensure user is logged in
    if 'user_id' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('main.signin'))

    # Ensure only locals can access this route
    if session.get('role') != 'local':
        flash("Access denied: Only locals allowed.")
        return redirect(url_for('main.signin'))

    return render_template('local_dashboard.html')


from app.models import HelpRequest, Reply, User
from sqlalchemy import and_

@main.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in first.")
        return redirect(url_for('main.signin'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    if not user:
        flash("User not found.")
        return redirect(url_for('main.signin'))

    user_requests = HelpRequest.query.filter_by(user_id=user_id).order_by(HelpRequest.created_at.desc()).all()

    # Replies grouped by help_request_id, joined with User for local_name
    replies = {}
    for req in user_requests:
        replies[req.id] = db.session.query(
            User.email.label("local_email"),
            Reply.message,
            Reply.created_at
        ).join(User, Reply.local_id == User.id).filter(
            Reply.help_request_id == req.id
        ).all()

    return render_template(
        'profile.html',
        name=user.name,
        email=user.email,
        role=user.role,
        help_requests=user_requests,
        replies=replies
    )


    


from app.models import HelpRequest  # make sure it's defined
from datetime import datetime

@main.route('/help-request', methods=['GET', 'POST'])
def help_request():
    if 'user_id' not in session or session.get('role') != 'traveler':
        flash("Access denied.")
        return redirect(url_for('main.signin'))

    if request.method == 'POST':
        query_text = request.form.get('query')
        city = request.form.get('city')
        email_alert = 'email_alert' in request.form

        try:
            new_request = HelpRequest(
                user_id=session['user_id'],
                query_text=query_text,
                city=city,
                email_alert=email_alert,
                created_at=datetime.utcnow()
            )
            db.session.add(new_request)
            db.session.commit()

            try:
                from app import socketio
                tourist_email = session.get('email')
                socketio.emit('new_reply', {
                    'help_id': new_request.id,
                    'message': query_text,
                    'from': tourist_email
                }, broadcast=True)
            except Exception as socket_error:
                print("❌ WebSocket emit error:", socket_error)

            flash("✅ Help request submitted successfully!")
            return redirect(url_for('main.tourist_dashboard'))

        except Exception as db_error:
            db.session.rollback()
            print("❌ DB Error:", db_error)
            flash("❌ Something went wrong. Please try again.")

    return render_template('help_form.html')



@main.after_request
def add_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response





from sqlalchemy import and_

from sqlalchemy import and_

from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import and_
from app.models import User, HelpRequest, Reply
from app.extensions import db
from flask_mail import Message

@main.route('/local-inbox', methods=['GET', 'POST'])
def local_inbox():
    if 'user_id' not in session or session.get('role') != 'local':
        flash("Access denied.")
        return redirect(url_for('main.signin'))

    from app import socketio

    local_id = session['user_id']
    local_user = db.session.query(User).get(local_id)
    local_city = local_user.city

    # Handle POST reply submission (support both normal form and AJAX)
    if request.method == 'POST':
        request_id = request.form.get('request_id')
        reply_text = request.form.get('reply')
        selected_city = request.form.get('filter_city') or 'my_city'

        if reply_text and request_id:
            new_reply = Reply(help_request_id=request_id, local_id=local_id, message=reply_text)
            db.session.add(new_reply)

            req = db.session.query(HelpRequest).get(request_id)
            if req:
                req.status = 'Replied'
                tourist = db.session.query(User).get(req.user_id)

                if tourist and getattr(tourist, 'is_verified', True) and req.email_alert:
                    try:
                        msg = Message(
                            subject="New reply on your Locallie help request!",
                            recipients=[tourist.email],
                            body=f"Hi there! Your help request has received a reply:\n\n'{reply_text}'\n\nCheck your Locallie dashboard!"
                        )
                        mail.send(msg)
                    except Exception as e:
                        print("Email send error:", e)

            db.session.commit()

            socketio.emit('new_reply', {
                'help_id': new_reply.help_request_id,
                'message': new_reply.message,
                'from': local_user.email
            }, broadcast=True)

            flash("✅ Reply sent and tourist notified!")
        else:
            flash("❌ Reply cannot be empty!")

        return redirect(url_for('main.local_inbox', filter_city=selected_city))

    # GET method — for showing inbox
    selected_city = request.args.get('filter_city') or 'my_city'

    # Filter help requests based on selected city
    if selected_city == 'all':
        filtered_requests = db.session.query(HelpRequest).join(User, HelpRequest.user_id == User.id).add_columns(
            HelpRequest.id,
            HelpRequest.query_text,
            HelpRequest.city,
            HelpRequest.status,
            HelpRequest.created_at,
            User.email.label('tourist_email')
        ).filter(HelpRequest.status.in_(['Pending', 'Replied']))
    elif selected_city == 'my_city':
        filtered_requests = db.session.query(HelpRequest).join(User, HelpRequest.user_id == User.id).add_columns(
            HelpRequest.id,
            HelpRequest.query_text,
            HelpRequest.city,
            HelpRequest.status,
            HelpRequest.created_at,
            User.email.label('tourist_email')
        ).filter(
            HelpRequest.status.in_(['Pending', 'Replied']),
            HelpRequest.city == local_city
        )
    else:
        filtered_requests = db.session.query(HelpRequest).join(User, HelpRequest.user_id == User.id).add_columns(
            HelpRequest.id,
            HelpRequest.query_text,
            HelpRequest.city,
            HelpRequest.status,
            HelpRequest.created_at,
            User.email.label('tourist_email')
        ).filter(
            HelpRequest.status.in_(['Pending', 'Replied']),
            HelpRequest.city == selected_city
        )

    pending_requests = filtered_requests.order_by(HelpRequest.created_at.desc()).all()

    # Replies per help request
    all_request_ids = [r.id for r in pending_requests]
    replies_by_request = {}

    if all_request_ids:
        replies = db.session.query(Reply).filter(
    Reply.help_request_id.in_(all_request_ids)
    ).join(User, Reply.local_id == User.id) \
 .add_columns(User.name.label("local_name"), Reply.message, Reply.created_at, Reply.help_request_id) \
 .all()
        
        replies_by_request = {}
        for r in replies:
         if r.local_name and r.message:
          replies_by_request.setdefault(r.help_request_id, []).append({
            'name': r.local_name,
            'message': r.message,
            'time': r.created_at.strftime("%Y-%m-%d %H:%M")
        })


        for r in replies:
            replies_by_request.setdefault(r.help_request_id, []).append(r.message)

    # Dropdown city options
    all_cities = [c[0] for c in db.session.query(HelpRequest.city).distinct().all() if c[0]]

    return render_template(
        'local_inbox.html',
        pending_requests=pending_requests,
        selected_city=selected_city,
        all_cities=all_cities,
        replies_by_request=replies_by_request
    )





@main.route('/submit_reply', methods=['POST'])
def submit_reply():
    if 'user_id' not in session or session.get('role') != 'local':
        return jsonify({'status': 'error', 'message': 'Unauthorized access'})

    data = request.get_json()
    request_id = data.get('request_id')
    reply_text = data.get('reply')
    local_id = session['user_id']

    if not reply_text:
        return jsonify({'status': 'error', 'message': 'Reply cannot be empty'})

    # Insert the reply
    reply = Reply(
        help_request_id=request_id,
        local_id=local_id,
        message=reply_text
    )
    db.session.add(reply)

    # Update status
    req = HelpRequest.query.get(request_id)
    if req:
        req.status = 'Replied'

        # Optional: Notify tourist
        tourist = User.query.get(req.user_id)
        if tourist and getattr(tourist, 'is_verified', True) and req.email_alert:
            try:
                msg = Message(
                    subject="New reply on your Locallie help request!",
                    recipients=[tourist.email],
                    body=f"Hi there! Your help request has received a reply:\n\n'{reply_text}'\n\nPlease check your Locallie dashboard."
                )
                mail.send(msg)
            except Exception as e:
                print("Email error:", e)

    db.session.commit()
    return jsonify({'status': 'success'})









@main.route('/about')
def about():
    return render_template('about.html')


@main.route('/contact')
def contact():
    return render_template('contact.html')


from app.models import Feedback  # make sure this model exists

@main.route('/send_feedback', methods=['GET', 'POST'])
def send_feedback():
    if 'user_id' not in session:
        return redirect(url_for('main.signin'))  # secure redirect

    if request.method == 'POST':
        user_id = session['user_id']
        user_role = session.get('role')
        subject = request.form['subject']
        message = request.form['message']

        try:
            new_feedback = Feedback(
                user_id=user_id,
                user_role=user_role,
                subject=subject,
                message=message
            )
            db.session.add(new_feedback)
            db.session.commit()
            flash("Feedback sent to admin. Thank you!")
            return redirect(url_for('main.send_feedback'))  # Redirect to avoid resubmission

        except Exception as e:
            db.session.rollback()
            print("Feedback insert error:", e)
            flash("Something went wrong. Please try again.")

    return render_template('send_feedback.html')


from app.models import Feedback

@main.route('/admin/view_feedback')
def admin_view_feedback():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))

    status_filter = request.args.get('status')

    if status_filter in ['Pending', 'Resolved']:
        feedbacks = Feedback.query.filter_by(status=status_filter).order_by(Feedback.timestamp.desc()).all()
    else:
        feedbacks = Feedback.query.order_by(Feedback.timestamp.desc()).all()

    return render_template(
        'admin_view_feedback.html',
        feedbacks=feedbacks,
        current_filter=status_filter
    )


from app.models import Feedback

@main.route('/admin/resolve_feedback/<int:feedback_id>')
def resolve_feedback(feedback_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))

    feedback = Feedback.query.get(feedback_id)
    if feedback:
        feedback.status = 'Resolved'
        try:
            db.session.commit()
            flash("Feedback marked as resolved.")
        except Exception as e:
            db.session.rollback()
            print("DB error:", e)
            flash("Could not resolve feedback. Please try again.")
    else:
        flash("Feedback not found.")

    return redirect(url_for('main.admin_view_feedback'))


from app.models import HelpRequest, User
from sqlalchemy import func

from sqlalchemy.orm import aliased
from sqlalchemy import func

@main.route('/admin/help_requests')
def admin_help_requests():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))

    status_filter = request.args.get('status')

    # Get help requests and join user info (email etc.)
    query = db.session.query(
        HelpRequest,
        User.email.label('tourist_email')
    ).outerjoin(User, HelpRequest.user_id == User.id)

    if status_filter in ['Pending', 'Accepted', 'Replied']:
        query = query.filter(HelpRequest.status == status_filter)

    query = query.order_by(HelpRequest.created_at.desc())
    results = query.all()

    help_data = []
    for hr, tourist_email in results:
        help_data.append({
            'id': hr.id,
            'query': hr.query_text,  # ✅ use correct field name
            'city': hr.city,
            'status': hr.status,
            'created_at': hr.created_at,
            'email_alert': hr.email_alert,
            'tourist_email': tourist_email
            # ❌ remove local_email / accepted_by
        })

    counts_raw = db.session.query(
        HelpRequest.status,
        func.count().label('count')
    ).group_by(HelpRequest.status).all()

    counts = {status: count for status, count in counts_raw}

    return render_template(
        'admin_help_requests.html',
        help_data=help_data,
        current_filter=status_filter,
        counts=counts
    )




from app.models import HelpRequest

@main.route('/accept_request/<int:request_id>', methods=['POST'])
def accept_request(request_id):
    if 'user_id' not in session or session.get('role') != 'local':
        flash("Login required.")
        return redirect(url_for('main.signin'))

    local_id = session['user_id']

    # Fetch and check if request is not already accepted
    help_request = HelpRequest.query.get(request_id)
    if not help_request:
        flash("Help request not found.")
    elif help_request.accepted_by:
        flash("This request is already accepted by another local.")
    else:
        help_request.accepted_by = local_id
        help_request.status = 'Accepted'

        try:
            db.session.commit()
            flash("You have accepted the request.")
        except Exception as e:
            db.session.rollback()
            print("Error accepting request:", e)
            flash("Something went wrong. Try again.")

    return redirect(url_for('main.local_inbox'))


@main.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@main.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('main.signin'))

@main.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 🔐 Simple hardcoded admin login
        if username == 'tirth' and password == '9723':
            session['admin_logged_in'] = True
            flash("Admin login successful.")
            return redirect(url_for('main.admin_dashboard'))
        else:
            flash("Invalid credentials. Try again.")

    return render_template('admin_login.html')


from app.models import Feedback
from sqlalchemy import func

@main.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))

    total_feedback = db.session.query(func.count(Feedback.id)).scalar()

    resolved = db.session.query(func.count(Feedback.id))\
        .filter(Feedback.status == 'Resolved').scalar()

    pending = db.session.query(func.count(Feedback.id))\
        .filter(Feedback.status == 'Pending').scalar()

    return render_template(
        'admin_dashboard.html',
        total=total_feedback,
        resolved=resolved,
        pending=pending
    )


@main.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin_login')


@main.route("/test-mail")
def test_mail():
    if 'user_id' not in session:
        return "❌ Login required to test mail."

    user_email = session.get('email') or "fallback@example.com"
    user_name = session.get('name', 'User')

    msg = Message(
        subject="📧 Test Email from Locallie",
        recipients=[user_email],
        body=f"""
Hi {user_name}! ✅

This is a test email from Locallie.

If you're reading this, your SMTP (Gmail) configuration is working properly!

– Locallie Team
"""
    )

    try:
        mail.send(msg)
        return f"✅ Test email sent to {user_email}! Check your inbox or spam folder."
    except Exception as e:
        print("SMTP Error:", e)
        return "❌ Failed to send test email. Please check SMTP credentials in .env and Gmail app access settings."


from flask import request, session, jsonify
from app.models import db, EmergencyAlert
from app.email_utils import send_emergency_email
from datetime import datetime

@main.route('/emergency', methods=['POST'])
def emergency():
    data = request.get_json()
    lat = data.get('latitude')
    lon = data.get('longitude')

    print("📍 Received emergency alert:", lat, lon)

    email = session.get('email')
    city = session.get('city')
    user_id = session.get('user_id')

    print("🧾 Email:", email)
    print("🌆 City:", city)
    print("🧍 ID:", user_id)

    if not email or not city or not user_id:
        print("❌ Session missing values")
        return jsonify({"status": "error", "message": "Not logged in"}), 403

    try:
        result = send_emergency_email(
            to_email='mahguycrypto@gmail.com',
            from_email=email,
            city=city,
            lat=lat,
            lon=lon
        )
        print("📧 Email send result:", result)
    except Exception as e:
        print("❌ Email failed:", e)
        return jsonify({"status": "error", "message": "Email failed"}), 500

    try:
        alert = EmergencyAlert(
            user_id=user_id,
            email=email,
            city=city,
            lat=lat,
            lon=lon,
            timestamp=datetime.utcnow()
        )
        db.session.add(alert)
        db.session.commit()
    except Exception as e:
        print("❌ DB Error:", e)
        return jsonify({"status": "error", "message": "DB save failed"}), 500

    return jsonify({"status": "success", "message": "Alert sent!"})











if __name__ == "__main__":
    app.run(debug=True)