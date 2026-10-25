from app.schemas.answer import Answer
from app.schemas.question import Question


def validate_answer(question: Question, answer: Answer) -> Answer:
    if answer.question_id != question.id:
        raise ValueError("response question ID does not match")
    if answer.question_type != question.question_type:
        raise ValueError("response question type does not match")
    known = {option.id for option in question.options}
    if not set(answer.selected_option_ids) <= known:
        raise ValueError("response contains unknown option IDs")
    if len(set(answer.selected_option_ids)) != len(answer.selected_option_ids):
        raise ValueError("response repeats option IDs")
    if question.question_type in ("single_choice", "true_false") and len(answer.selected_option_ids) > 1:
        raise ValueError("single-choice response has multiple selections")
    if answer.status == "solved" and not (answer.selected_option_ids or answer.text_answer):
        raise ValueError("solved response has no answer")
    if answer.status == "solved" and question.options and not answer.selected_option_ids:
        raise ValueError("choice response needs option IDs")
    return answer
