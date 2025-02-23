from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, Upload, User  # Ensure User model is imported
from config import Config
import os

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"  # Redirect users to login page if not authenticated
login_manager.init_app(app)

# User loader function (Required by Flask-Login)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ensure UPLOAD_FOLDER exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
from flask_login import login_user, logout_user, login_required

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):  # Ensure you have a check_password method
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))

        flash('Invalid credentials, try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# Home route
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'audio' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)

        file = request.files['audio']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)

        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        new_upload = Upload(user_id=current_user.id, filename=file.filename)
        db.session.add(new_upload)
        db.session.commit()
        
        flash('File uploaded successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('upload.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']  # Get username from form
        email = request.form['email']
        password = request.form['password']
        
        # Ensure username, email, and password are provided
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('signup'))

        # Create new user instance
        new_user = User(username=username, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Sign up successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()  # Rollback the session in case of an error
            flash(str(e), 'danger')

    return render_template('signup.html')


# Run Flask app
if __name__ == "__main__":
    app.run(debug=True)
