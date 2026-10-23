from flask import Flask, render_template, jsonify, request, redirect, url_for
import os, json, sqlite3

app = Flask(__name__)
QUIZ_DIR = '/app/quizzes'
DB_PATH = os.path.join(QUIZ_DIR, 'scores.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS scores (quiz_id TEXT PRIMARY KEY, highscore INTEGER)')
    # Nova tabela para rastrear cada pergunta única respondida corretamente
    c.execute('CREATE TABLE IF NOT EXISTS answered_questions (quiz_id TEXT, question_idx INTEGER, PRIMARY KEY(quiz_id, question_idx))')
    conn.commit()
    conn.close()

init_db()

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Busca os recordes
    c.execute('SELECT quiz_id, highscore FROM scores')
    scores_dict = {row[0]: row[1] for row in c.fetchall()}
    
    # Busca o progresso (quantas perguntas únicas ele já acertou)
    c.execute('SELECT quiz_id, COUNT(question_idx) FROM answered_questions GROUP BY quiz_id')
    progress_dict = {row[0]: row[1] for row in c.fetchall()}
    conn.close()

    quizzes = []
    if os.path.exists(QUIZ_DIR):
        for filename in os.listdir(QUIZ_DIR):
            if filename.endswith('.json'):
                try:
                    quiz_id = filename.replace('.json', '')
                    with open(os.path.join(QUIZ_DIR, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total_q = len(data.get('perguntas', [])) # Pega o total de perguntas do banco
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
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            new_score = data.get('score', 0)
            correct_ids = data.get('correct_ids', []) # Recebe os IDs das perguntas acertadas de primeira
            
            # Atualiza o recorde se for maior
            c.execute('SELECT highscore FROM scores WHERE quiz_id = ?', (quiz_id,))
            row = c.fetchone()
            if row is None or new_score > row[0]:
                c.execute('REPLACE INTO scores (quiz_id, highscore) VALUES (?, ?)', (quiz_id, new_score))
            
            # Grava as perguntas únicas acertadas
            for q_idx in correct_ids:
                c.execute('INSERT OR IGNORE INTO answered_questions (quiz_id, question_idx) VALUES (?, ?)', (quiz_id, q_idx))
                
            conn.commit()
            conn.close()
            return jsonify({"status": "ok"})
        else:
            c.execute('SELECT highscore FROM scores WHERE quiz_id = ?', (quiz_id,))
            row = c.fetchone()
            highscore = row[0] if row else 0
            conn.close()
            return jsonify({"highscore": highscore})
    except Exception as e:
        return jsonify({"highscore": 0, "error": str(e)})

@app.route('/reset')
def reset_scores():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM scores')
    c.execute('DELETE FROM answered_questions') # Limpa o progresso também
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)