cat << 'EOF' > /DATA/AppData/quiz-icaro/app.py
from flask import Flask, render_template, jsonify, request, redirect, url_for
import os, json, psycopg2

app = Flask(__name__)
QUIZ_DIR = '/app/quizzes'
# Lê da variável de ambiente no Render, ou usa a string local do Supabase
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:U.%3FPBw39%25q%26r6f9@db.kgcmzvhigfooidjtfoay.supabase.co:5432/postgres')

def get_db_connection():
    return psycopg2.connect(DB_URL)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.errorhandler(404)
def page_not_found(e):
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_exception(e):
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('SELECT quiz_id, highscore FROM scores')
    scores_dict = {row[0]: row[1] for row in c.fetchall()}
    
    c.execute('SELECT quiz_id, COUNT(question_idx) FROM answered_questions GROUP BY quiz_id')
    progress_dict = {row[0]: row[1] for row in c.fetchall()}
    
    c.close()
    conn.close()

    quizzes = []
    if os.path.exists(QUIZ_DIR):
        for filename in os.listdir(QUIZ_DIR):
            if filename.endswith('.json'):
                try:
                    quiz_id = filename.replace('.json', '')
                    with open(os.path.join(QUIZ_DIR, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total_q = len(data.get('perguntas', []))
                        quizzes.append({
                            'id': quiz_id,
                            'titulo': data.get('titulo', 'Sem Título'),
                            'materia': data.get('materia', 'Geral'),
                            'highscore': scores_dict.get(quiz_id, 0),
                            'progress': progress_dict.get(quiz_id, 0),
                            'total': total_q
                        })
                except Exception:
                    pass
    return render_template('index.html', quizzes=quizzes)

@app.route('/quiz/<quiz_id>')
def quiz_page(quiz_id):
    return render_template('quiz.html', quiz_id=quiz_id)

@app.route('/api/quiz/<quiz_id>')
def get_quiz(quiz_id):
    filepath = os.path.join(QUIZ_DIR, f"{quiz_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Not found"}), 404

@app.route('/api/score/<quiz_id>', methods=['GET', 'POST'])
def handle_score(quiz_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            new_score = data.get('score', 0)
            correct_ids = data.get('correct_ids', [])
            
            c.execute('SELECT highscore FROM scores WHERE quiz_id = %s', (quiz_id,))
            row = c.fetchone()
            if row is None or new_score > row[0]:
                c.execute('''
                    INSERT INTO scores (quiz_id, highscore) VALUES (%s, %s)
                    ON CONFLICT (quiz_id) DO UPDATE SET highscore = EXCLUDED.highscore
                ''', (quiz_id, new_score))
            
            for q_idx in correct_ids:
                c.execute('''
                    INSERT INTO answered_questions (quiz_id, question_idx) VALUES (%s, %s)
                    ON CONFLICT (quiz_id, question_idx) DO NOTHING
                ''', (quiz_id, q_idx))
                
            conn.commit()
            c.close()
            conn.close()
            return jsonify({"status": "ok"})
        else:
            c.execute('SELECT highscore FROM scores WHERE quiz_id = %s', (quiz_id,))
            row = c.fetchone()
            highscore = row[0] if row else 0
            c.close()
            conn.close()
            return jsonify({"highscore": highscore})
    except Exception as e:
        return jsonify({"highscore": 0, "error": str(e)})

@app.route('/reset')
def reset_scores():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM scores')
    c.execute('DELETE FROM answered_questions')
    conn.commit()
    c.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF