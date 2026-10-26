import json
import unittest
from pathlib import Path

from quiz_logic import build_answer_feedback, evaluate_answer, prepare_attempt, validate_quiz


QUIZ_DIR = Path(__file__).resolve().parents[1] / 'quizzes'


class QuizContentTests(unittest.TestCase):
    def test_all_quizzes_have_valid_content_and_separate_explanations(self):
        quiz_files = sorted(QUIZ_DIR.glob('*.json'))
        self.assertEqual(len(quiz_files), 6)

        for path in quiz_files:
            with self.subTest(quiz=path.name):
                quiz = validate_quiz(json.loads(path.read_text(encoding='utf-8')))
                self.assertEqual(len(quiz['perguntas']), 20)
                for question in quiz['perguntas']:
                    self.assertNotEqual(question['explicacao'], question['dica_erro'])

    def test_invalid_question_is_rejected(self):
        invalid_quiz = {
            'perguntas': [{
                'texto': 'Pergunta de teste',
                'alternativas': ['A', 'A', 'C', 'D'],
                'resposta_correta': 0,
                'dica_erro': 'Dica',
                'explicacao': 'Explicacao',
            }] * 10,
        }
        with self.assertRaises(ValueError):
            validate_quiz(invalid_quiz)


class QuizAttemptTests(unittest.TestCase):
    def test_first_incorrect_choice_allows_another_attempt(self):
        result = evaluate_answer(2, [], 1)
        self.assertFalse(result['correct'])
        self.assertFalse(result['question_done'])
        self.assertEqual(result['pending_choices'], [1])

    def test_second_incorrect_choice_finishes_without_revealing_answer(self):
        result = evaluate_answer(2, [1], 3)
        feedback = build_answer_feedback(
            {'dica_erro': 'Dica', 'explicacao': 'Resposta correta'},
            result,
        )
        self.assertFalse(result['correct'])
        self.assertTrue(result['question_done'])
        self.assertNotIn('correct_option_idx', result)
        self.assertNotIn('answer', result)
        self.assertEqual(feedback, {'hint': None, 'explanation': None})

    def test_feedback_uses_the_answered_question(self):
        question = {
            'dica_erro': 'A dica desta pergunta',
            'explicacao': 'A explicação desta pergunta',
        }
        first_wrong = evaluate_answer(2, [], 0)
        correct_on_retry = evaluate_answer(2, [0], 2)

        self.assertEqual(
            build_answer_feedback(question, first_wrong),
            {'hint': 'A dica desta pergunta', 'explanation': None},
        )
        self.assertEqual(
            build_answer_feedback(question, correct_on_retry),
            {'hint': None, 'explanation': 'A explicação desta pergunta'},
        )

    def test_correct_answer_awards_server_calculated_points(self):
        first_try = evaluate_answer(2, [], 2)
        retry = evaluate_answer(2, [0], 2)
        self.assertEqual(first_try['points'], 3)
        self.assertEqual(retry['points'], 1)
        self.assertTrue(first_try['mastered'])
        self.assertFalse(retry['mastered'])

    def test_repeating_a_wrong_choice_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_answer(2, [1], 1)

    def test_attempt_payload_hides_answer_and_hint(self):
        quiz = json.loads((QUIZ_DIR / 'ciencias_p1.json').read_text(encoding='utf-8'))
        _, _, public_questions, _, _ = prepare_attempt(quiz)
        self.assertEqual(len(public_questions), 10)
        for question in public_questions:
            self.assertEqual(set(question), {'texto', 'alternativas'})

    def test_question_and_answer_orders_change_between_attempts(self):
        quiz = json.loads((QUIZ_DIR / 'ciencias_p1.json').read_text(encoding='utf-8'))
        quiz['perguntas'] = quiz['perguntas'][:10]
        _, first_data, _, previous_questions, previous_options = prepare_attempt(quiz)
        _, second_data, _, _, _ = prepare_attempt(quiz, previous_questions, previous_options)
        self.assertNotEqual(
            [question['question_idx'] for question in first_data],
            [question['question_idx'] for question in second_data],
        )
        first_options = {
            question['question_idx']: question['option_order']
            for question in first_data
        }
        second_options = {
            question['question_idx']: question['option_order']
            for question in second_data
        }
        for question_idx in first_options.keys() & second_options.keys():
            self.assertNotEqual(first_options[question_idx], second_options[question_idx])


if __name__ == '__main__':
    unittest.main()
