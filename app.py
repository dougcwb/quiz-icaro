import hmac
import json
import logging
import os
import re
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect

load_dotenv()

logger = logging.getLogger(__name__)
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError('A variavel SECRET_KEY precisa estar configurada.')

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true',
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=16 * 1024,
)
CSRFProtect(app)

QUIZ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quizzes')
DB_URL = os.environ.get('DATABASE_URL')
RESET_PASSWORD = os.environ.get('RESET_PASSWORD', '2814')
QUIZ_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
ALLOWED_CONTROLLERS = {'teclado', 'xbox', 'ps', 'switch', 'celular'}


def get_db_connection():
    if not DB_URL:
        raise RuntimeError('A variavel DATABASE_URL precisa estar configurada.')
    return psycopg2.connect(DB_URL)


@contextmanager
def db_transaction():
    conn = get_db_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def get_quiz_path(quiz_id):
    if not QUIZ_ID_PATTERN.fullmatch(quiz_id):
        abort(404)
    return os.path.join(QUIZ_DIR, f'{quiz_id}.json')


def load_quiz(quiz_id):
    filepath = get_quiz_path(quiz_id)
    try:
        with open(filepath, 'r', encoding='utf-8') as quiz_file:
            return json.load(quiz_file)
    except FileNotFoundError:
        abort(404)
    except json.JSONDecodeError:
        logger.exception('Arquivo JSON invalido para o quiz %s', quiz_id)
        abort(500)


@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    with db_transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE site_stats SET stat_value = stat_value + 1 WHERE stat_name = 'visits' RETURNING stat_value")
            row_visits = cursor.fetchone()
            visits = row_visits[0] if row_visits else 0

            cursor.execute("INSERT INTO daily_visits (visit_date, visits) VALUES (CURRENT_DATE, 1) ON CONFLICT (visit_date) DO UPDATE SET visits = daily_visits.visits + 1 RETURNING visits")
            row_today = cursor.fetchone()
            visits_today = row_today[0] if row_today else 0

    if request.method == 'POST':
        nome = request.form.get('player_name', '').strip().upper()
        controller = request.form.get('controller_type', 'teclado')
        if not nome or len(nome) > 30 or controller not in ALLOWED_CONTROLLERS:
            abort(400)
        session.clear()
        session['player_name'] = nome
        session['controller'] = controller
        return redirect(url_for('index'))

    player_name = session.get('player_name')
    controller = session.get('controller', 'teclado')
    if not player_name:
        return render_template('index.html', player_name=None, quizzes=[], visits=visits, visits_today=visits_today)

    with db_transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT quiz_id, highscore FROM scores WHERE player_name = %s', (player_name,))
            scores_dict = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute('SELECT quiz_id, COUNT(question_idx) FROM answered_questions WHERE player_name = %s GROUP BY quiz_id', (player_name,))
            progress_dict = {row[0]: row[1] for row in cursor.fetchall()}

    quizzes = []
    if os.path.exists(QUIZ_DIR):
        for filename in os.listdir(QUIZ_DIR):
            if not filename.endswith('.json'):
                continue
            quiz_id = filename[:-5]
            if not QUIZ_ID_PATTERN.fullmatch(quiz_id):
                continue
            try:
                with open(os.path.join(QUIZ_DIR, filename), 'r', encoding='utf-8') as quiz_file:
                    data = json.load(quiz_file)
                quizzes.append({
                    'id': quiz_id,
                    'titulo': data.get('titulo', 'Sem Titulo'),
                    'materia': data.get('materia', 'Geral'),
                    'highscore': scores_dict.get(quiz_id, 0),
                    'progress': progress_dict.get(quiz_id, 0),
                    'total': len(data.get('perguntas', []))
                })
            except (OSError, json.JSONDecodeError):
                logger.exception('Nao foi possivel carregar o arquivo de quiz %s', filename)
    return render_template('index.html', player_name=player_name, quizzes=quizzes, visits=visits, visits_today=visits_today, controller=controller)


@app.route('/leaderboard')
def leaderboard():
    with db_transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT p.player_name, COALESCE(SUM(s.highscore), 0) as total_score,
                (SELECT COUNT(DISTINCT quiz_id || question_idx) FROM answered_questions aq WHERE aq.player_name = p.player_name) as total_mastered
                FROM (SELECT player_name FROM scores UNION SELECT player_name FROM answered_questions) p
                LEFT JOIN scores s ON p.player_name = s.player_name
                GROUP BY p.player_name ORDER BY total_score DESC, total_mastered DESC
            ''')
            ranking = cursor.fetchall()
    return render_template('leaderboard.html', ranking=ranking, controller=session.get('controller', 'teclado'))


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/quiz/<quiz_id>')
def quiz_page(quiz_id):
    if 'player_name' not in session:
        return redirect(url_for('index'))
    load_quiz(quiz_id)
    return render_template('quiz.html', quiz_id=quiz_id, controller=session.get('controller', 'teclado'))


@app.route('/api/quiz/<quiz_id>')
def get_quiz(quiz_id):
    return jsonify(load_quiz(quiz_id))


@app.route('/api/score/<quiz_id>', methods=['GET', 'POST'])
def handle_score(quiz_id):
    player_name = session.get('player_name')
    if not player_name:
        return jsonify({"error": "Nao autenticado"}), 401
    quiz = load_quiz(quiz_id)

    try:
        with db_transaction() as conn:
            with conn.cursor() as cursor:
                if request.method == 'GET':
                    cursor.execute('SELECT highscore FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
                    row = cursor.fetchone()
                    return jsonify({"highscore": row[0] if row else 0})

                data = request.get_json()
                if not isinstance(data, dict):
                    abort(400)

                new_score = data.get('score')
                correct_ids = data.get('correct_ids')
                question_count = len(quiz.get('perguntas', []))
                max_questions = min(10, question_count)
                if (
                    isinstance(new_score, bool)
                    or not isinstance(new_score, int)
                    or not 0 <= new_score <= 3 * max_questions
                    or not isinstance(correct_ids, list)
                    or len(correct_ids) > max_questions
                    or any(
                        isinstance(q_idx, bool)
                        or not isinstance(q_idx, int)
                        or not 0 <= q_idx < question_count
                        for q_idx in correct_ids
                    )
                    or len(set(correct_ids)) != len(correct_ids)
                ):
                    abort(400)

                cursor.execute('SELECT highscore FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
                row = cursor.fetchone()
                if row is None or new_score > row[0]:
                    cursor.execute('''
                        INSERT INTO scores (player_name, quiz_id, highscore) VALUES (%s, %s, %s)
                        ON CONFLICT (player_name, quiz_id) DO UPDATE SET highscore = EXCLUDED.highscore
                    ''', (player_name, quiz_id, new_score))

                for q_idx in correct_ids:
                    cursor.execute('''
                        INSERT INTO answered_questions (player_name, quiz_id, question_idx) VALUES (%s, %s, %s)
                        ON CONFLICT (player_name, quiz_id, question_idx) DO NOTHING
                    ''', (player_name, quiz_id, q_idx))
        return jsonify({"status": "ok"})
    except psycopg2.Error:
        logger.exception('Erro no banco ao salvar/consultar pontuacao do quiz %s', quiz_id)
        return jsonify({"error": "Erro interno ao processar a pontuacao."}), 500


@app.route('/reset/<quiz_id>', methods=['POST'])
def reset_scores(quiz_id):
    get_quiz_path(quiz_id)
    player_name = session.get('player_name')
    if not player_name:
        return redirect(url_for('index'))
    password = request.form.get('reset_password', '')
    if not hmac.compare_digest(password, RESET_PASSWORD):
        flash('Senha incorreta. Os dados nao foram apagados.', 'error')
        return redirect(url_for('index'))
    with db_transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
            cursor.execute('DELETE FROM answered_questions WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
