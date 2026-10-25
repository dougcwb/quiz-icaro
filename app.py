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
from werkzeug.exceptions import HTTPException
from quiz_logic import evaluate_answer, prepare_attempt, validate_quiz

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
ATTEMPT_ID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)
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
            return validate_quiz(json.load(quiz_file))
    except FileNotFoundError:
        abort(404)
    except json.JSONDecodeError:
        logger.exception('Arquivo JSON invalido para o quiz %s', quiz_id)
        abort(500)
    except ValueError:
        logger.exception('Conteudo invalido para o quiz %s', quiz_id)
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
                data = load_quiz(quiz_id)
                quizzes.append({
                    'id': quiz_id,
                    'titulo': data.get('titulo', 'Sem Titulo'),
                    'materia': data.get('materia', 'Geral'),
                    'highscore': scores_dict.get(quiz_id, 0),
                    'progress': progress_dict.get(quiz_id, 0),
                    'total': len(data.get('perguntas', []))
                })
            except (OSError, ValueError, HTTPException):
                logger.exception('Nao foi possivel carregar o arquivo de quiz %s', filename)
    return render_template('index.html', player_name=player_name, quizzes=quizzes, visits=visits, visits_today=visits_today, controller=controller)


@app.route('/leaderboard')
def leaderboard():
    with db_transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM quiz_attempts WHERE created_at < NOW() - INTERVAL '1 day'")
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


@app.route('/api/quiz/<quiz_id>/attempt', methods=['POST'])
def start_quiz_attempt(quiz_id):
    player_name = session.get('player_name')
    if not player_name:
        return jsonify({"error": "Nao autenticado"}), 401
    quiz = load_quiz(quiz_id)
    attempt_id, question_data, public_questions, question_order, option_orders = prepare_attempt(
        quiz,
        session.get(f'previous_questions:{quiz_id}'),
        session.get(f'previous_answers:{quiz_id}'),
    )
    session[f'previous_questions:{quiz_id}'] = question_order
    session[f'previous_answers:{quiz_id}'] = option_orders
    try:
        with db_transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO quiz_attempts (attempt_id, player_name, quiz_id, question_data)
                    VALUES (%s::uuid, %s, %s, %s)
                ''', (attempt_id, player_name, quiz_id, json.dumps(question_data, ensure_ascii=False)))
        return jsonify({"attempt_id": attempt_id, "perguntas": public_questions}), 201
    except psycopg2.Error:
        logger.exception('Erro no banco ao iniciar tentativa do quiz %s', quiz_id)
        return jsonify({"error": "Nao foi possivel iniciar o quiz."}), 500


@app.route('/api/quiz/<quiz_id>/attempt/<attempt_id>/answer', methods=['POST'])
def answer_quiz_question(quiz_id, attempt_id):
    player_name = session.get('player_name')
    if not player_name:
        return jsonify({"error": "Nao autenticado"}), 401
    if not ATTEMPT_ID_PATTERN.fullmatch(attempt_id):
        return jsonify({"error": "Tentativa inexistente ou expirada."}), 404

    data = request.get_json()
    if not isinstance(data, dict):
        abort(400)
    question_number = data.get('question_number')
    choice_index = data.get('choice_index')
    if (
        type(question_number) is not int
        or question_number < 0
        or type(choice_index) is not int
        or not 0 <= choice_index < 4
    ):
        abort(400)

    try:
        with db_transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT question_data, answer_log, pending_choices, score, combo, errors, correct_count,
                           first_try_correct, last_response, completed_at
                    FROM quiz_attempts
                    WHERE attempt_id = %s::uuid AND player_name = %s AND quiz_id = %s
                      AND created_at > NOW() - INTERVAL '2 hours'
                    FOR UPDATE
                ''', (attempt_id, player_name, quiz_id))
                attempt = cursor.fetchone()
                if attempt is None:
                    return jsonify({"error": "Tentativa inexistente ou expirada."}), 404

                question_data = attempt[0]
                answer_log = attempt[1]
                pending_choices = attempt[2]
                score = attempt[3]
                combo = attempt[4]
                errors = attempt[5]
                correct_count = attempt[6]
                first_try_correct = attempt[7]
                last_response = attempt[8]
                if (
                    last_response
                    and question_number == last_response['question_number']
                    and choice_index == last_response['choice_index']
                ):
                    return jsonify(last_response['response'])
                if attempt[9] is not None:
                    return jsonify({"error": "Tentativa inexistente ou expirada."}), 404
                if question_number != len(answer_log) or question_number >= len(question_data):
                    abort(400)

                question_record = question_data[question_number]
                try:
                    result = evaluate_answer(
                        question_record['correct_option_idx'],
                        pending_choices,
                        choice_index,
                    )
                except ValueError:
                    abort(400)
                errors += int(not result['correct'])
                explanation = None
                hint = None
                if result['correct']:
                    score += result['points']
                    correct_count += 1
                    combo = combo + 1 if result['mastered'] else 0
                    explanation = question_record['question']['explicacao']
                    if result['mastered']:
                        first_try_correct.append(question_record['question_idx'])
                    answer_log.append({
                        'question_idx': question_record['question_idx'],
                        'choices': result['choices'],
                        'correct': True,
                    })
                elif result['question_done']:
                    combo = 0
                    answer_log.append({
                        'question_idx': question_record['question_idx'],
                        'choices': result['choices'],
                        'correct': False,
                    })
                else:
                    combo = 0
                    hint = question_record['question']['dica_erro']

                complete = len(answer_log) == len(question_data)
                response_data = {
                    'correct': result['correct'],
                    'question_done': result['question_done'],
                    'hint': hint,
                    'explanation': explanation,
                    'complete': complete,
                    'score': score,
                    'combo': combo,
                    'errors': errors,
                    'correct_count': correct_count,
                }
                cursor.execute('''
                    UPDATE quiz_attempts
                    SET answer_log = %s, pending_choices = %s, score = %s, combo = %s,
                        errors = %s, correct_count = %s, first_try_correct = %s,
                        completed_at = CASE WHEN %s THEN NOW() ELSE completed_at END,
                        last_response = %s
                    WHERE attempt_id = %s::uuid
                ''', (
                    json.dumps(answer_log, ensure_ascii=False),
                    json.dumps(result['pending_choices'], ensure_ascii=False),
                    score,
                    combo,
                    errors,
                    correct_count,
                    json.dumps(first_try_correct, ensure_ascii=False),
                    complete,
                    json.dumps({
                        'question_number': question_number,
                        'choice_index': choice_index,
                        'response': response_data,
                    }, ensure_ascii=False),
                    attempt_id,
                ))

                if complete:
                    cursor.execute('''
                        INSERT INTO scores (player_name, quiz_id, highscore)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (player_name, quiz_id)
                        DO UPDATE SET highscore = GREATEST(scores.highscore, EXCLUDED.highscore)
                    ''', (player_name, quiz_id, score))
                    for mastered_question in first_try_correct:
                        cursor.execute('''
                            INSERT INTO answered_questions (player_name, quiz_id, question_idx)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (player_name, quiz_id, question_idx) DO NOTHING
                        ''', (player_name, quiz_id, mastered_question))

                return jsonify(response_data)
    except psycopg2.Error:
        logger.exception('Erro no banco ao registrar resposta do quiz %s', quiz_id)
        return jsonify({"error": "Nao foi possivel registrar a resposta."}), 500


@app.route('/api/score/<quiz_id>', methods=['GET'])
def handle_score(quiz_id):
    player_name = session.get('player_name')
    if not player_name:
        return jsonify({"error": "Nao autenticado"}), 401
    try:
        with db_transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT highscore FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
                row = cursor.fetchone()
                return jsonify({"highscore": row[0] if row else 0})
    except psycopg2.Error:
        logger.exception('Erro no banco ao consultar pontuacao do quiz %s', quiz_id)
        return jsonify({"error": "Erro interno ao consultar a pontuacao."}), 500


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
            cursor.execute('DELETE FROM quiz_attempts WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
            cursor.execute('DELETE FROM scores WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
            cursor.execute('DELETE FROM answered_questions WHERE player_name = %s AND quiz_id = %s', (player_name, quiz_id))
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
