from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import os, json, psycopg2

app = Flask(__name__)
app.secret_key = 'senha_secreta_retro_16bits'
QUIZ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quizzes')
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:U.%3FPBw39%25q%26r6f9@aws-0-sa-east-1.pooler.supabase.com:6543/postgres')

def get_db_connection():
    return psycopg2.connect(DB_URL)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Incrementa e busca o contador de visitas
    c.execute("UPDATE site_stats SET stat_value = stat_value + 1 WHERE stat_name = 'visits' RETURNING stat_value")
    row_visits = c.fetchone()
    visits = row_visits[0] if row_visits else 0

    if request.method == 'POST':
        nome = request.form.get('player_name', '').strip().upper()
        if nome:
            session['player_name'] = nome
        c.close()
        conn.close()
        return redirect(url_for('index'))

    player_name = session.get('player_name')
    if not player_name:
        c.close()
        conn.close()
        return render_template('index.html', player_name=None, quizzes=[], visits=visits)

    c.execute('SELECT quiz_id, highscore FROM scores WHERE player_name = %s', (player_name,))
    scores_dict = {row[0]: row[1] for row in c.fetchall()}
    
    c.execute('SELECT quiz_id, COUNT(question_idx) FROM answered_questions WHERE player_name = %s GROUP BY quiz_id', (player_name,))
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
                        quizzes.append({
                            'id': quiz_id,
                            'titulo': data.get('titulo', 'Sem Título'),
                            'materia': data.get('materia', 'Geral'),
                            'highscore': scores_dict.get(quiz_id, 0),
                            'progress': progress_dict.get(quiz_id, 0),
                            'total': len(data.get('perguntas', []))
                        })
                except Exception:
                    pass
    return render_template('index.html', player_name=player_name, quizzes=quizzes, visits=visits)

@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    c = conn.cursor()
    # Puxa o ranking ordenado pelas estrelas totais
    c.execute('''
        SELECT 
            p.player_name, 
            COALESCE(SUM(s.highscore), 0) as total_score,
            (SELECT COUNT(DISTINCT quiz_id || question_idx) FROM answered_questions aq WHERE aq.player_name = p.player_name) as total_mastered
        FROM (
            SELECT player_name FROM scores
            UNION
            SELECT player_name FROM answered_questions
        ) p
        LEFT JOIN scores s ON p.player_name = s.player_name
        GROUP BY p.player_name
        ORDER BY total_score DESC, total_mastered DESC
    ''')
    ranking = c.fetchall()
    c.close()
    conn.close()
    return render_template('leaderboard.html', ranking=ranking)

@app.route('/logout')
def logout():
    session.pop('player_name', None)
    return redirect(url_for('index'))

@app.route('/quiz/<quiz_id>')
def quiz_page(quiz_id):
    if 'player_name' not in session:
        return redirect(url_for('index'))
    return render_template('quiz.html', quiz_id=quiz_id)

@app.route('/api/quiz/<quiz_id>')
def get_quiz(quiz_id):
    filepath = os.path.join(QUIZ_DIR, f"{quiz_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Not found"}), 404

@app.route('/api/score/<quiz_id>', methods=['POST'])
def handle_score(quiz_id):
    player_name = session.get('player_name')
    if not player_name: return jsonify({"error": "Não autenticado"}), 401
    try:
        conn = get_db_connection()
        c = conn.cursor()
        data = request.get_json(silent=True) or {}
        new_score = data.get('score', 0)
        correct_ids = data.get('correct_ids', [])
        
        c.execute('SELECT highscore FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
        row = c.fetchone()
        if row is None or new_score > row[0]:
            c.execute('''
                INSERT INTO scores (player_name, quiz_id, highscore) VALUES (%s, %s, %s)
                ON CONFLICT (player_name, quiz_id) DO UPDATE SET highscore = EXCLUDED.highscore
            ''', (player_name, quiz_id, new_score))
        
        for q_idx in correct_ids:
            c.execute('''
                INSERT INTO answered_questions (player_name, quiz_id, question_idx) VALUES (%s, %s, %s)
                ON CONFLICT (player_name, quiz_id, question_idx) DO NOTHING
            ''', (player_name, quiz_id, q_idx))
            
        conn.commit()
        c.close()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/reset')
def reset_scores():
    player_name = session.get('player_name')
    if player_name:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM scores WHERE player_name = %s', (player_name,))
        c.execute('DELETE FROM answered_questions WHERE player_name = %s', (player_name,))
        conn.commit()
        c.close()
        conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
