# Master Quiz

Master Quiz is an interactive educational platform designed to enhance learning through AI-powered quiz generation. Teachers can create courses via voice recordings, while students engage with automatically generated quizzes and downloadable PDF summaries for effective revision.

##  Key Features

- **Automated Quiz Generation**: Instantly creates MCQs from lecture transcripts
- **PDF Course Summaries**: Generate and download concise course summaries
- **Role-Based Access**: 
  - Teachers: Record lessons,share course IDs
  - Students: Access courses via ID, take quizzes, view results and can download pdfs
- **Voice-to-Text Transcription**: Real-time audio recording and transcription
- **AI Integration**: Utilizes Groq API with llama-3.3-70b-versatile model for content generation

## Technologies Used
- **Backend**: Python, Flask
- **DataBase**: MySQL avec SQLAlchemy
- **Vocal recognition**: SpeechRecognition, sounddevice ,numpy
- **IA**: Groq API (llama-3.3-70b-versatile)
- **Authentification**: Flask-Login
- **PDF**: ReportLab
- **Frontend**: HTML, CSS, JavaScript

## Installation

### Prerequisites
- Python 3.9+
- MySQL Server
- Compte Groq (pour l'API key)

1. Clone repository:
```bash
https://github.com/IlhamBouatioui15/Quiz_master.git
```
2. Create environement :In your project directory (where your Python files are):
```bash  
python -m venv venv
```
This creates a virtual environment named venv.

3. Activate the virtual environment
```bash  
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Database setup on MySQL:
```sql
CREATE DATABASE master_quiz;
```

6. Run application:
```bash
python quiz.py
```

## Configuration

```env
SECRET_KEY=your_secret_key_here
SQLALCHEMY_DATABASE_URI=mysql+pymysql://username:password@localhost/master_quiz
GROQ_API_KEY=your_groq_api_key_here
```
## Usage Guide

### For Teachers
1. Register with "professor" role
2. Navigate to recording interface
3. Start/stop voice recording sessions
4. Share generated course ID with students

### For Students
1. Register with "student" role
2. Enter provided course ID
3. Complete auto-generated quiz
4. View results and download PDF summary

## Development Team | Data Girls

| Member             | Role              | Affiliation                                                                 |
|--------------------|-------------------|-----------------------------------------------------------------------------|
| Maria El Houdaigui | Data Engineer     | Big Data & Information Systems Student, ENSA Berrechid                      |
| Ilham Bouatioui    | Data Scientist    | Big Data & Information Systems Student, ENSA Berrechid                      |
| Imane Benzegunine  | AI Engineer       | Big Data & Information Systems Student, ENSA Berrechid                      |

## License
This project is currently not licensed for public use.  
Please contact me if you would like to use or contribute to this project.
