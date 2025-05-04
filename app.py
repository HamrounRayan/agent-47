from flask import Flask, render_template, request, redirect, url_for, flash
import os
import json
from werkzeug.utils import secure_filename
from openai import OpenAI
import sqlite3
import PyPDF2
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')
upload_dir = os.path.join(current_dir, 'pdfs')

os.makedirs(template_dir, exist_ok=True)
os.makedirs(upload_dir, exist_ok=True)

app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'supersecretkey'

ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = upload_dir

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

def setup_database():
    db_path = os.path.join(current_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, cv TEXT)''')
    conn.commit()
    conn.close()

def get_users():
    db_path = os.path.join(current_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, cv FROM users")
    users = [{"id": row[0], "cv": row[1]} for row in c.fetchall()]
    conn.close()
    return users

def run_analysis(criteria=None):
    users = get_users()
    
    if not users:
        return "No CVs found in the database. Please upload some PDFs first."
    
    if criteria is None:
        criteria = """
        give some of the best candidates from the users based on 
        Evaluation Criteria:
        1. Technical skills depth and relevance to software development
        2. Demonstrated impact in previous roles (quantifiable achievements)
        3. Education/certifications in computer science/related fields
        4. Complexity of projects handled
        5. Leadership/team collaboration experience"""
    
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("KEY")
        )
        user_prompt = f"you are an experience data base searcher and u can judge resumes, be professional and do {criteria}:\n\n{json.dumps(users, indent=2)}"
        
        completion = client.chat.completions.create(
          extra_headers={
            "HTTP-Referer": "https://example.com",
            "X-Title": "CV Analysis",
          },
          model="qwen/qwen2.5-vl-72b-instruct:free",
          messages=[
            {"role": "user", "content": user_prompt}
          ]
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        files = request.files.getlist('file')

        if len(files) == 1 and files[0].filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                try:
                    cv_text = extract_text_from_pdf(file_path)
                    db_path = os.path.join(current_dir, 'users.db')
                    conn = sqlite3.connect(db_path)
                    c = conn.cursor()
                    c.execute("INSERT INTO users (cv) VALUES (?)", (cv_text,))
                    conn.commit()
                    conn.close()
                    flash(f'Successfully uploaded and processed {filename}')
                except Exception as e:
                    flash(f'Error processing {filename}: {str(e)}')
        
        return redirect(url_for('index'))
    
    uploaded_files = []
    if os.path.exists(upload_dir):
        uploaded_files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
    
    db_path = os.path.join(current_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    cv_count = c.fetchone()[0]
    conn.close()
    
    return render_template('index.html', uploaded_files=uploaded_files, cv_count=cv_count)

@app.route('/analyze', methods=['POST'])
def analyze():
    custom_criteria = request.form.get('criteria', '')
    
    if not custom_criteria.strip():
        result = run_analysis()
    else:
        result = run_analysis(custom_criteria)

    uploaded_files = []
    if os.path.exists(upload_dir):
        uploaded_files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
    
    db_path = os.path.join(current_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    cv_count = c.fetchone()[0]
    conn.close()
    
    return render_template('index.html', uploaded_files=uploaded_files, cv_count=cv_count, result=result)

@app.route('/reset', methods=['POST'])
def reset_database():
    db_path = os.path.join(current_dir, 'users.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    
    flash('Database has been reset')
    return redirect(url_for('index'))

if __name__ == '__main__':
    setup_database() 
    print(f"Current directory: {current_dir}")
    print(f"Template directory: {template_dir}")
    print(f"Upload directory: {upload_dir}")
    app.run(debug=True)