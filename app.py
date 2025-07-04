from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from dotenv import load_dotenv
from flask_mail import Mail, Message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


load_dotenv()



app = Flask(__name__)


conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

app.secret_key = os.getenv("SECRET_KEY")

cursor = conn.cursor()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'        # Gmail SMTP server
app.config['MAIL_PORT'] = 587                       # Gmail SMTP port for TLS
app.config['MAIL_USE_TLS'] = True                   # Use TLS encryption
app.config['MAIL_USE_SSL'] = False                  # Don't use SSL here since TLS is used
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')  # Your email address (set in .env)
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')  # Your email password or app password
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER')  # Default sender email

mail = Mail(app)  # Initialize Flask-Mail with app

def send_email(to_email, subject, body):
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    sender_email = os.getenv('EMAIL_USER')  # your gmail or sender email
    sender_password = os.getenv('EMAIL_PASS')  # your app password, no spaces!

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")



@app.route("/")
def index():
    return render_template("index.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role')

        # Only fetch city if role is local
        city = request.form.get('city') if role == 'local' else None

        hashed_password = generate_password_hash(password)

        try:
            cursor.execute("""
                INSERT INTO users (name, email, password, role, city) 
                VALUES (%s, %s, %s, %s, %s)
            """, (name, email, hashed_password, role, city))
            conn.commit()

            # ✅ Set session['city'] only for locals after role is known
            if role == 'local':
                session['city'] = city

            flash("Signup successful! You can now log in.")
            return redirect('/signin')  

        except mysql.connector.IntegrityError as e:
            print("DB Error (Integrity):", e)
            flash("Email already exists.")
            return redirect('/signup')

        except Exception as e:
            print("DB Error (Unknown):", e)
            flash("Something went wrong.")
            return redirect('/signup')

    return render_template('signup.html')





@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            db_password = user[3]  # assuming id, name, email, password, role
            if check_password_hash(db_password, password):
                # Set session
                session['user_id'] = user[0]
                session['name'] = user[1]
                session['email'] = user[2]
                session['role'] = user[4]

                flash("Login successful!")

                if user[4] == 'local':
                  
             # fetch city of the local from DB
                  cursor.execute("SELECT city FROM users WHERE id = %s", (user[0],))
                  city_row = cursor.fetchone()
                  if city_row:
                   session['city'] = city_row[0]


                # Redirect by role
                if user[4] == 'traveler':
                    return redirect('/tourist')
                else:
                    return redirect('/local')
            else:
                flash("Incorrect password.")
                return redirect('/signin')
        else:
            flash("Email not found.")
            return redirect('/signin')

    return render_template("signin.html")

@app.route('/tourist')
def tourist_dashboard():
    if 'user_id' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('signin'))

    if session.get('role') != 'traveler':
        flash("Access denied: Only travelers allowed.")
        return redirect(url_for('signin'))

    return render_template('tourist_dashboard.html')


@app.route('/local')
def local_dashboard():
    if 'user_id' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('signin'))

    if session.get('role') != 'local':
        flash("Access denied: Only locals allowed.")
        return redirect(url_for('signin'))

    return render_template('local_dashboard.html')



@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in first.")
        return redirect('/login')

    user_id = session['user_id']
    user_name = session['name']
    user_email = session['email']
    user_role = session['role']

    # Fetch help requests made by this user
    cursor.execute("""
        SELECT hr.query, hr.city, hr.status, hr.id
        FROM help_request hr
        WHERE hr.user_id = %s
        ORDER BY hr.created_at DESC
    """, (user_id,))
    help_requests = cursor.fetchall()

    # Fetch replies to their help requests (if any)
    replies = {}
    for hr in help_requests:
        request_id = hr[3]  # id is 4th field
        cursor.execute("""
            SELECT u.name, r.reply, r.created_at
            FROM help_replies r
            JOIN users u ON r.local_id = u.id
            WHERE r.request_id = %s
        """, (request_id,))
        replies[request_id] = cursor.fetchall()

    return render_template('profile.html', name=user_name, email=user_email, role=user_role, help_requests=help_requests, replies=replies)




@app.route('/help-request', methods=['GET', 'POST'])
def help_request():
    if 'user_id' not in session or session['role'] != 'traveler':
        flash("Access denied.")
        return redirect('/login')

    if request.method == 'POST':
        query = request.form['query']
        city = request.form['city']
        user_id = session['user_id']

        cursor.execute("INSERT INTO help_request (user_id, query, city) VALUES (%s, %s, %s)", (user_id, query, city))
        conn.commit()
        flash("Help request submitted!")
        return redirect('/tourist')

    return render_template('help_form.html')

@app.route('/local-inbox', methods=['GET', 'POST'])
def local_inbox():
    if 'user_id' not in session or session.get('role') != 'local':
        flash("Access denied.")
        return redirect('/signin')

    local_id = session['user_id']

    cursor = conn.cursor(dictionary=True)
    # Fetch local's city
    cursor.execute("SELECT city FROM users WHERE id = %s", (local_id,))
    local_city = cursor.fetchone()['city']

    # Determine city filter
    selected_city = request.args.get('filter_city')
    if selected_city == 'all':
        city_condition = ""
        city_params = ()
    elif selected_city == 'my_city' or not selected_city:
        city_condition = "AND hr.city = %s"
        city_params = (local_city,)
    else:
        city_condition = "AND hr.city = %s"
        city_params = (selected_city,)

    if request.method == 'POST':
        request_id = request.form['request_id']
        reply_text = request.form.get('reply')

        if reply_text:
            # Insert reply
            cursor.execute("""
                INSERT INTO help_replies (request_id, local_id, reply) 
                VALUES (%s, %s, %s)
            """, (request_id, local_id, reply_text))
            conn.commit()

            # Fetch tourist email and is_verified to send notification if verified
            cursor.execute("""
                SELECT u.email, u.is_verified
                FROM help_request hr
                JOIN users u ON hr.user_id = u.id
                WHERE hr.id = %s
            """, (request_id,))
            tourist = cursor.fetchone()

            if tourist and tourist['is_verified']:  # Send email only if verified
                msg = Message(
                    subject="New reply on your Locallie help request!",
                    recipients=[tourist['email']],
                    body=f"Hi there! Your help request has received a reply:\n\n'{reply_text}'\n\nPlease check your Locallie dashboard."
                )
                mail.send(msg)

            flash("Reply sent and tourist notified (if verified)!")
        else:
            flash("Reply cannot be empty!")

        return redirect('/local-inbox')

    # Fetch pending requests with replies (so they don’t disappear)
    query = f"""
        SELECT hr.id, hr.query, hr.city, u.email AS tourist_email
        FROM help_request hr
        JOIN users u ON hr.user_id = u.id
        WHERE hr.status = 'Pending' {city_condition}
        ORDER BY hr.created_at DESC
    """
    cursor.execute(query, city_params)
    pending_requests = cursor.fetchall()

    # Fetch local’s replies for each pending request
    all_request_ids = [r['id'] for r in pending_requests]
    replies_by_request = {}

    if all_request_ids:
        format_strings = ','.join(['%s'] * len(all_request_ids))
        cursor.execute(f"""
            SELECT request_id, reply
            FROM help_replies
            WHERE local_id = %s AND request_id IN ({format_strings})
        """, (local_id, *all_request_ids))

        for row in cursor.fetchall():
            rid = row['request_id']
            if rid not in replies_by_request:
                replies_by_request[rid] = []
            replies_by_request[rid].append(row['reply'])

    # Get city list for dropdown
    cursor.execute("SELECT DISTINCT city FROM help_request")
    all_cities = [row['city'] for row in cursor.fetchall()]

    cursor.close()
    return render_template(
        'local_inbox.html',
        pending_requests=pending_requests,
        selected_city=selected_city or 'my_city',
        all_cities=all_cities,
        replies_by_request=replies_by_request
    )








@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

from flask import request, redirect, render_template, session
from datetime import datetime
import mysql.connector

@app.route('/send_feedback', methods=['GET', 'POST'])
def send_feedback():
    if 'user_id' not in session:
        return redirect('/signin')  # Ensure user is logged in

    if request.method == 'POST':
        user_id = session['user_id']
        user_role = session['role']  # Make sure you store role in session on login
        subject = request.form['subject']
        message = request.form['message']

        cursor = conn.cursor()
        query = "INSERT INTO platform_feedback (user_id, user_role, subject, message) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (user_id, user_role, subject, message))
        conn.commit()
        cursor.close()

        return "Feedback sent to admin. Thank you!"

    return render_template('send_feedback.html')

@app.route('/admin/view_feedback')
def admin_view_feedback():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    status_filter = request.args.get('status')  # optional query param

    cursor = conn.cursor(dictionary=True)
    
    if status_filter in ['Pending', 'Resolved']:
        cursor.execute("SELECT * FROM platform_feedback WHERE status = %s ORDER BY timestamp DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM platform_feedback ORDER BY timestamp DESC")

    feedbacks = cursor.fetchall()
    cursor.close()

    return render_template('admin_view_feedback.html', feedbacks=feedbacks, current_filter=status_filter)


@app.route('/admin/resolve_feedback/<int:feedback_id>')
def resolve_feedback(feedback_id):

    if not session.get('admin_logged_in'):
        return redirect('/admin_login')
    

    cursor = conn.cursor()
    cursor.execute("UPDATE platform_feedback SET status = 'Resolved' WHERE id = %s", (feedback_id,))
    conn.commit()
    cursor.close()
    return redirect('/admin/view_feedback')

@app.route('/admin/help_requests')
def admin_help_requests():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    status_filter = request.args.get('status')
    cursor = conn.cursor(dictionary=True)

    base_query = """
        SELECT hr.*, 
               t.email AS tourist_email,
               l.email AS local_email
        FROM help_request hr
        LEFT JOIN users t ON hr.user_id = t.id
        LEFT JOIN users l ON hr.accepted_by = l.id
    """

    count_query = "SELECT status, COUNT(*) as count FROM help_request GROUP BY status"

    # Filtered query
    if status_filter in ['Pending', 'Accepted', 'Replied']:
        base_query += " WHERE hr.status = %s ORDER BY hr.created_at DESC"
        cursor.execute(base_query, (status_filter,))
    else:
        base_query += " ORDER BY hr.created_at DESC"
        cursor.execute(base_query)

    help_data = cursor.fetchall()

    # Get counts by status
    cursor.execute(count_query)
    counts = {row['status']: row['count'] for row in cursor.fetchall()}
    cursor.close()

    return render_template('admin_help_requests.html', help_data=help_data, current_filter=status_filter, counts=counts)


@app.route('/accept_request/<int:request_id>', methods=['POST'])
def accept_request(request_id):
    if 'user_id' not in session or session.get('role') != 'local':
        flash("Login required.")
        return redirect('/signin')

    local_id = session['user_id']
    cursor = conn.cursor()

    # Prevent re-accepting already accepted requests
    cursor.execute("""
        UPDATE help_request
        SET accepted_by = %s, status = 'Accepted'
        WHERE id = %s AND accepted_by IS NULL
    """, (local_id, request_id))

    conn.commit()
    cursor.close()
    flash("You have accepted the request.")
    return redirect('/local-inbox')





@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('signin'))

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Simple hardcoded admin login
        if username == 'tirth' and password == '9723':
            session['admin_logged_in'] = True
            return redirect('/admin_dashboard')
        else:
            return "Invalid credentials"

    return render_template('admin_login.html')


@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin_login')

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM platform_feedback")
    total_feedback = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM platform_feedback WHERE status='Resolved'")
    resolved = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM platform_feedback WHERE status='Pending'")
    pending = cursor.fetchone()[0]

    cursor.close()
    return render_template('admin_dashboard.html', total=total_feedback, resolved=resolved, pending=pending)

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin_login')



if __name__ == "__main__":
    app.run(debug=True)
