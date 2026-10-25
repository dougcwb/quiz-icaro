import secrets
from uuid import uuid4


def validate_quiz(quiz):
    if not isinstance(quiz, dict) or not isinstance(quiz.get('perguntas'), list):
        raise ValueError('O quiz precisa conter uma lista de perguntas.')
    if len(quiz['perguntas']) < 10:
        raise ValueError('O quiz precisa ter pelo menos 10 perguntas.')

    for question_number, question in enumerate(quiz['perguntas'], start=1):
        if not isinstance(question, dict) or not isinstance(question.get('texto'), str) or not question['texto'].strip():
            raise ValueError(f'Pergunta {question_number}: texto ausente.')
        alternatives = question.get('alternativas')
        if (
            not isinstance(alternatives, list)
            or len(alternatives) != 4
            or any(not isinstance(answer, str) or not answer.strip() for answer in alternatives)
            or len(set(alternatives)) != 4
        ):
            raise ValueError(f'Pergunta {question_number}: sao necessarias quatro alternativas distintas.')
        correct_index = question.get('resposta_correta')
        if type(correct_index) is not int or not 0 <= correct_index < len(alternatives):
            raise ValueError(f'Pergunta {question_number}: indice de resposta correta invalido.')
        for field in ('dica_erro', 'explicacao'):
            if not isinstance(question.get(field), str) or not question[field].strip():
                raise ValueError(f'Pergunta {question_number}: campo {field} ausente.')
    return quiz


def prepare_attempt(quiz, previous_question_order=None, previous_option_orders=None):
    previous_option_orders = dict(previous_option_orders or {})
    question_indices = secrets.SystemRandom().sample(range(len(quiz['perguntas'])), 10)
    while question_indices == list(range(10)) or question_indices == previous_question_order:
        question_indices = secrets.SystemRandom().sample(range(len(quiz['perguntas'])), 10)

    question_data = []
    public_questions = []
    option_orders = dict(previous_option_orders)
    for question_index in question_indices:
        question = quiz['perguntas'][question_index]
        previous_option_order = previous_option_orders.get(str(question_index))
        option_order = secrets.SystemRandom().sample(range(4), 4)
        while option_order == list(range(4)) or option_order == previous_option_order:
            option_order = secrets.SystemRandom().sample(range(4), 4)
        option_orders[str(question_index)] = option_order
        question_data.append({
            'question_idx': question_index,
            'option_order': option_order,
            'correct_option_idx': option_order.index(question['resposta_correta']),
            'question': question,
        })
        public_questions.append({
            'texto': question['texto'],
            'alternativas': [question['alternativas'][index] for index in option_order],
        })
    return str(uuid4()), question_data, public_questions, question_indices, option_orders


def evaluate_answer(correct_option_idx, previous_choices, choice_index):
    if type(choice_index) is not int or not 0 <= choice_index < 4:
        raise ValueError('A alternativa selecionada e invalida.')
    if len(previous_choices) >= 2 or choice_index in previous_choices:
        raise ValueError('A pergunta ja foi respondida ou a alternativa foi repetida.')

    choices = previous_choices + [choice_index]
    if choice_index == correct_option_idx:
        return {
            'choices': choices,
            'pending_choices': [],
            'question_done': True,
            'correct': True,
            'points': 3 if not previous_choices else 1,
            'mastered': not previous_choices,
        }
    if len(choices) == 1:
        return {
            'choices': choices,
            'pending_choices': choices,
            'question_done': False,
            'correct': False,
            'points': 0,
            'mastered': False,
        }
    return {
        'choices': choices,
        'pending_choices': [],
        'question_done': True,
        'correct': False,
        'points': 0,
        'mastered': False,
    }


def build_answer_feedback(question, result):
    return {
        'hint': question['dica_erro'] if not result['correct'] and not result['question_done'] else None,
        'explanation': question['explicacao'] if result['correct'] else None,
    }
