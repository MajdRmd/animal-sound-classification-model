from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, Upload, User  # Ensure User model is imported
from config import Config
import os
import tensorflow as tf
import numpy as np
import librosa
from skimage.transform import resize
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical



# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

model = tf.keras.models.load_model("awid_model.h5")


# Define the target shape used during training
TARGET_SHAPE = (128, 128)

# Class Labels from training
CLASS_LABELS = ['cat', 'dog', 'bird', 'cow', 'lion', 'sheep', 'frog', 'chicken', 'donkey', 'monkey']

def preprocess_audio(file_path):
    # Load audio
    audio_data, sample_rate = librosa.load(file_path, sr=None)

    # Convert to Mel spectrogram
    mel_spectrogram = librosa.feature.melspectrogram(y=audio_data, sr=sample_rate)

    # Resize to match input shape (128x128)
    mel_spectrogram = resize(mel_spectrogram, TARGET_SHAPE)

    # Expand dimensions to match CNN input (batch_size, height, width, channels)
    mel_spectrogram = np.expand_dims(mel_spectrogram, axis=-1)  # Add channel dimension
    mel_spectrogram = np.expand_dims(mel_spectrogram, axis=0)   # Add batch dimension

    return mel_spectrogram

# Prediction route
@app.route('/predict/<filename>', methods=['GET'])
@login_required
def predict(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Preprocess the audio
    input_data = preprocess_audio(file_path)  # Ensure shape is (1, 128, 128, 1)

    # Load model (ensure the path is correct)
    model = load_model('best_model.h5')

    # Get predictions
    prediction = model.predict(input_data)

    # Get predicted class index
    predicted_index = np.argmax(prediction)

    # Get predicted class label
    predicted_animal = CLASS_LABELS[predicted_index]

    return f"Prediction Result\nPredicted Animal: {predicted_animal}"


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
    prediction_result = request.args.get('prediction_result', None)  # Get prediction result from query string
    return render_template('index.html', prediction_result=prediction_result)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    prediction_result = None  # Variable to hold prediction result
    
    if request.method == 'POST':
        if 'audio' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)

        file = request.files['audio']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Preprocess the audio and get prediction
        input_data = preprocess_audio(filepath)
        prediction = model.predict(input_data)
        predicted_index = np.argmax(prediction)
        predicted_animal = CLASS_LABELS[predicted_index]
        prediction_result = f"Predicted Animal: {predicted_animal}"

        # Save the uploaded file information to the database
        new_upload = Upload(user_id=current_user.id, filename=file.filename)
        db.session.add(new_upload)
        db.session.commit()
        
        flash('File uploaded successfully!', 'success')

        # Redirect to home and pass prediction result
        return redirect(url_for('home', prediction_result=prediction_result))

    return render_template('upload.html')  # If no POST, stay on the upload page

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
