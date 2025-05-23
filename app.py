from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from models import db, Upload, User
from config import Config
import os
import tensorflow as tf
import numpy as np
import librosa
from skimage.transform import resize
from tensorflow.keras.models import load_model
from pydub import AudioSegment

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Ensure UPLOAD_FOLDER exists
UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Load Trained Model
model = load_model("best_model.h5")

# Class Labels
CLASS_LABELS = ['cat', 'dog', 'bird', 'cow', 'lion', 'sheep', 'frog', 'chicken', 'donkey', 'monkey', 'others']
TARGET_SHAPE = (128, 128)

def convert_audio_to_wav(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format='wav')

def preprocess_audio(file_path, target_shape=(128, 128)):
    try:
        print(f"Processing file: {file_path}")

        if not os.path.exists(file_path):
            print(f"Error: File {file_path} not found.")
            return None

        if not file_path.endswith(".wav"):
            wav_path = file_path.rsplit(".", 1)[0] + ".wav"
            convert_audio_to_wav(file_path, wav_path)
            file_path = wav_path

        audio_data, sr = librosa.load(file_path, sr=22050)

        if audio_data is None or len(audio_data) == 0:
            print("Error: Audio data is empty.")
            return None

        mel_spectrogram = librosa.feature.melspectrogram(y=audio_data, sr=sr, n_mels=128)
        mel_spectrogram = librosa.power_to_db(mel_spectrogram, ref=np.max)
        mel_spectrogram = resize(mel_spectrogram, target_shape, mode='constant', anti_aliasing=True)
        mel_spectrogram = np.expand_dims(mel_spectrogram, axis=-1)
        return np.expand_dims(mel_spectrogram, axis=0)

    except Exception as e:
        print(f"Error in preprocessing audio: {e}")
        return None

@app.route('/')
def home():
    prediction_result = request.args.get('prediction_result', None)
    return render_template('index.html', prediction_result=prediction_result)

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

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        input_data = preprocess_audio(filepath)
        if input_data is None:
            flash("Error in processing the audio file.", "danger")
            return redirect(url_for('upload'))

        prediction = model.predict(input_data)
        predicted_index = np.argmax(prediction)
        predicted_animal = CLASS_LABELS[predicted_index]
        prediction_result = f"Predicted Animal: {predicted_animal}"

        new_upload = Upload(user_id=current_user.id, filename=file.filename)
        db.session.add(new_upload)
        db.session.commit()

        flash('File uploaded successfully!', 'success')
        return redirect(url_for('home', prediction_result=prediction_result))

    return redirect(url_for('home'))

@app.route('/predict/<filename>', methods=['GET'])
@login_required
def predict(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash(f"Error: File {filename} not found!", "danger")
        return redirect(url_for('home'))

    input_data = preprocess_audio(file_path)
    if input_data is None:
        flash("Error in audio processing. Try again with a valid audio file.", "danger")
        return redirect(url_for('home'))

    prediction = model.predict(input_data)
    predicted_index = np.argmax(prediction)
    predicted_animal = CLASS_LABELS[predicted_index]

    return f"Predicted Animal: {predicted_animal}"

# Login / Logout / Signup
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
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

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('signup'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Sign up successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(str(e), 'danger')

    return render_template('signup.html')

if __name__ == "__main__":
    app.run(debug=True)
