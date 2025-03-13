import sounddevice as sd
import wave
import threading
import os
import uuid
import speech_recognition as sr
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from groq import Groq
from time import sleep

app = Flask(__name__)
CORS(app)

# Paramètres de l'enregistrement
SAMPLERATE = 44100  # Taux d'échantillonnage, 44100 Hz
CHANNELS = 1  # Mono
FILENAME = "audio_recording.wav"  # Fichier WAV temporaire
TEXT_FILENAME = "transcription.txt"  # Fichier texte pour stocker la transcription
audio_data = None  # Variable globale pour l'audio en temps réel
api_key = "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"
# Enregistrement en cours
is_recording = False
audio_thread = None

# Configuration de la base de données et de la connexion utilisateur
app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "prof" ou "etudiant"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()

# Fonction pour enregistrer l'audio en continu
def enregistrer_audio_continu():
    global audio_data
    global is_recording
    is_recording = True
    print("Enregistrement en cours...")
    audio_data = []

    with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, dtype='int16') as stream:
        while is_recording:
            chunk, overflowed = stream.read(1024)
            audio_data.append(chunk)

# Fonction de conversion de l'audio en texte
def convertir_audio_en_texte(fichier_wav):
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(fichier_wav) as source:
            print("Transcription en cours...")
            audio = recognizer.record(source)  # Lire le fichier audio
            texte = recognizer.recognize_google(audio, language="fr-FR")  # Reconnaissance vocale en français
            print("Texte transcrit :", texte)
            return texte
    except Exception as e:
        print("Erreur lors de la transcription :", str(e))
        return None

# transcription table
class Transcription(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # UUID stocké en string
    text = db.Column(db.Text, nullable=False)  # Texte transcrit
    professeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ID du professeur

    professor = db.relationship('User', backref='transcriptions')  # Association avec le professeur

with app.app_context():
    db.create_all()





# Fonction générique pour envoyer la requête via le client Groq
def send_request_to_groq(api_key, transcribed_text, retries=3, timeout=10):
    # Initialiser le client Groq avec la clé API
    groq_client = Groq(api_key=api_key)
    for attempt in range(retries):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "tu es un assistant merveilleux et serviable."},
                    {"role": "user", "content": f"Peux-tu générer une série de questions pour un quiz à partir de ce texte :\n\n{transcribed_text}\n\nChaque question devrait avoir quatre choix de réponse possibles et une réponse correcte. La structure des données doit être sous la forme suivante : question, choices, correct_answer."}
                ],
                model="llama-3.3-70b-versatile",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Erreur de connexion (tentative {attempt + 1} sur {retries}): {e}")
            if attempt < retries - 1:
                print("Nouvelle tentative dans 5 secondes...")
                sleep(5)
            else:
                print("Le nombre maximal de tentatives a été atteint.")
                return None
    return None

def generate_summary_from_text(transcribed_text, api_key):
    groq_client = Groq(api_key=api_key)
    try:
        chat_completion = groq_client.chat.completions.create(
    messages=[
        {"role": "system", "content": "Tu es un assistant qui génère des quiz éducatifs."},
        {"role": "user", "content": f"Génère un quiz basé sur le texte suivant. Pour chaque question, fournis quatre choix de réponse et indique la réponse correcte. Utilise le format suivant pour chaque question :\n\nQuestion : [la question]\nChoices : [choix 1, choix 2, choix 3, choix 4]\nCorrect_answer : [la bonne réponse]\n\nTexte :\n{transcribed_text}"}
    ],
    model="llama-3.3-70b-versatile",
)  
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Erreur lors de la génération du résumé : {e}")
        return None


def parse_quiz_response(response_data):
    questions = []
    lines = response_data.split("\n")
    current_question = None

    print("Début du parsing de la réponse...")  # Log de début
    print("Réponse brute :", response_data)  # Afficher la réponse brute

    for line in lines:
        line = line.strip()
        if not line:
            continue

        print("Traitement de la ligne :", line)  # Log pour chaque ligne

        if line.startswith("Question :"):
            if current_question:
                questions.append(current_question)
            current_question = {
                "question": line.split("Question :")[1].strip(),
                "choices": [],
                "answer": ""
            }
            print("Nouvelle question détectée :", current_question["question"])  # Log pour la question
        elif line.startswith("Choices :"):
            choices = line.split("Choices :")[1].strip().split(", ")
            current_question["choices"] = choices
            print("Choix détectés :", choices)  # Log pour les choix
        elif line.startswith("Correct_answer :"):
            current_question["answer"] = line.split("Correct_answer :")[1].strip()
            print("Réponse correcte détectée :", current_question["answer"])  # Log pour la réponse

    if current_question:
        questions.append(current_question)

    print("Parsing terminé. Questions générées :", questions)  # Log final
    return questions
def generate_pdf_with_summary(summary, filename="resume.pdf"):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 40, "Résumé de la transcription")

    # Résumé
    c.setFont("Helvetica", 12)
    y_position = height - 80
    for line in summary.split("\n"):
        c.drawString(100, y_position, line)
        y_position -= 15

    # Sauvegarder le PDF
    c.save()

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if User.query.filter_by(email=email).first():
            return "Cet email est déjà utilisé."

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template("register.html")
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            return "Email ou mot de passe incorrect"

        login_user(user)

        print(f"Utilisateur connecté : {user.email}, rôle : {user.role}")  # Vérifier le rôle dans la console

        if user.role == "prof":
            return redirect(url_for('quiz'))
        else:
            return redirect(url_for('enter_id'))  # Si c'est un étudiant, il doit aller vers enter_id

    return render_template("login.html")

@app.route('/quiz')
@login_required
def quiz():
    if current_user.role != "prof":
        return redirect(url_for('home'))
    return render_template("quiz.html")

# API pour commencer l'enregistrement
@app.route('/start_recording', methods=['GET'])
@login_required
def start_recording():
    if current_user.role != "prof":
        return jsonify({"message": "Accès refusé"}), 403
    global audio_thread
    if not is_recording:
        audio_thread = threading.Thread(target=enregistrer_audio_continu)
        audio_thread.start()
        return jsonify({"message": "Enregistrement démarré."}), 200
    else:
        return jsonify({"error": "Enregistrement déjà en cours."}), 400


# API pour arrêter l'enregistrement et convertir en texte
import random

# API pour arrêter l'enregistrement et convertir en texte
@app.route('/stop_recording', methods=['GET'])
@login_required
def stop_recording():
    if current_user.role != "prof":
        return jsonify({"message": "Accès refusé"}), 403
    global is_recording
    if is_recording:
        is_recording = False
        audio_thread.join()

        # Sauvegarde de l'audio en fichier WAV
        with wave.open(FILENAME, 'wb') as f:
            f.setnchannels(CHANNELS)
            f.setsampwidth(2)  # 16 bits
            f.setframerate(SAMPLERATE)
            for chunk in audio_data:
                f.writeframes(chunk.tobytes())

        # Convertir l'audio en texte
        texte_transcrit = convertir_audio_en_texte(FILENAME)

        if texte_transcrit:
            # Générer un ID à 5 chiffres
            transcription_id = str(random.randint(10000, 99999))

            # Sauvegarde dans la base de données
            transcription = Transcription(id=transcription_id, text=texte_transcrit, professeur_id=current_user.id)
            db.session.add(transcription)
            db.session.commit()

            return jsonify({
                "message": "Enregistrement arrêté.",
                "transcription": texte_transcrit,
                "transcription_id": transcription_id  # Retourner l'ID
            }), 200
        else:
            return jsonify({"error": "Impossible de transcrire l'audio."}), 500

    else:
        return jsonify({"error": "Aucun enregistrement en cours."}), 400
@app.route('/quiz1/<transcription_id>', methods=['GET'])
@login_required
def quiz1(transcription_id):
    if current_user.role != "etudiant":
        return redirect(url_for('home'))

    transcription = db.session.get(Transcription, transcription_id)
    if not transcription:
        return "ID invalide. Veuillez réessayer.", 400

    text = transcription.text
    quiz_response = generate_summary_from_text(text, api_key)

    if not quiz_response:
        return "Erreur lors de la génération du quiz.", 500

    # Vérifier que quiz_response est une chaîne de caractères
    if isinstance(quiz_response, list):
        quiz_response = "\n".join(quiz_response)  # Convertir la liste en chaîne de caractères

    quiz_questions = parse_quiz_response(quiz_response)
    if not quiz_questions:
        return "Erreur lors du parsing des questions.", 500

    return render_template('quiz1.html', transcription=transcription, questions=quiz_questions)

@app.route('/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    score = 0
    answers = {}

    # Récupérer l'ID de la transcription
    transcription_id = request.form.get('transcription_id')
    transcription = db.session.get(Transcription, transcription_id)
    if not transcription:
        return "ID de transcription invalide.", 400

    # Générer les questions à partir du texte transcrit
    quiz_response = generate_summary_from_text(transcription.text, api_key)
    quiz_questions = parse_quiz_response(quiz_response)

    # Vérifier les réponses de l'étudiant
    for i, question in enumerate(quiz_questions):
        student_answer = request.form.get(f"question_{i}")
        answers[i] = student_answer  # Stocker la réponse de l'étudiant
        if student_answer == question['answer']:  # Comparer avec la bonne réponse
            score += 1

    return render_template('quiz_result.html', score=score, total=len(quiz_questions), answers=answers, questions=quiz_questions)@app.route('/generate_summary_pdf/<transcription_id>', methods=['GET'])
@login_required
def generate_summary_pdf(transcription_id):
    if current_user.role != "etudiant":
        return redirect(url_for('home'))

    # Récupérer la transcription par son ID
    transcription = db.session.get(Transcription, transcription_id)
    if not transcription:
        return "ID invalide. Veuillez réessayer.", 400

    # Générer un résumé à partir du texte transcrit
    summary = generate_summary_from_text(transcription.text, api_key)

    if not summary:
        return "Erreur lors de la génération du résumé.", 500

    # Générer le PDF avec le résumé
    filename = "resume.pdf"
    generate_pdf_with_summary(summary, filename)

    # Retourner le PDF au format téléchargement
    return send_file(filename, as_attachment=True)

@app.route('/enter_id', methods=['GET'])
@login_required
def enter_id():
    if current_user.role != "etudiant":
        return redirect(url_for('home'))
    return render_template('enter_id.html')


@app.route('/validate_id', methods=['POST'])
@login_required
def validate_id():
    if current_user.role != "etudiant":
        return redirect(url_for('home'))

    transcription_id = request.form.get('transcription_id')
    transcription = db.session.get(Transcription, transcription_id)

    if transcription:
        return redirect(url_for('quiz1', transcription_id=transcription_id))
    else:
        return "ID invalide. Veuillez réessayer.", 400



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)







