from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from dotenv import load_dotenv
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


@app.route("/")
def index():
    return render_template("index.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        print("DEBUG FORM DATA:")
        print("Name:", name)
        print("Email:", email)
        print("Password:", password)
        print("Role:", role)

        hashed_password = generate_password_hash(password)

        try:
            cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                           (name, email, hashed_password, role))
            conn.commit()
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
    if 'user_id' not in session or session['role'] != 'local':
        flash("Access denied.")
        return redirect('/login')

    if request.method == 'POST':
        request_id = request.form['request_id']
        reply_text = request.form['reply']
        local_id = session['user_id']

        # Insert reply into help_replies table
        cursor.execute("INSERT INTO help_replies (request_id, local_id, reply) VALUES (%s, %s, %s)",
                       (request_id, local_id, reply_text))

        # Update status in help_request
        cursor.execute("UPDATE help_request SET status = 'Replied' WHERE id = %s", (request_id,))
        conn.commit()
        flash("Reply sent!")

    # Get all pending requests
    cursor.execute("""
        SELECT hr.id, u.name, hr.query, hr.city, hr.status
        FROM help_request hr
        JOIN users u ON hr.user_id = u.id
        WHERE hr.status = 'Pending'
    """)
    requests = cursor.fetchall()

    return render_template('local_inbox.html', requests=requests)



@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        try:
            cursor.execute("INSERT INTO feedback (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
            conn.commit()
            flash("Thank you for your feedback!")
            return redirect('/')
        except Exception as e:
            print("Error saving feedback:", e)
            flash("Something went wrong.")
            return redirect('/feedback')

    return render_template('feedback.html')


@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for('signin'))


if __name__ == "__main__":
    app.run(debug=True)
