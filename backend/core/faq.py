"""CRUD API for FAQ entries: a typed Q&A knowledge source alongside the uploaded document."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api import client_required, error, read_json
from .models import FAQEntry

MAX_QUESTION_CHARS = 300
MAX_ANSWER_CHARS = 2000
MAX_ENTRIES_PER_ACCOUNT = 200


def serialize(entry):
    return {
        "id": entry.pk,
        "question": entry.question,
        "answer": entry.answer,
        "index_status": entry.index_status,
        "index_error": entry.index_error,
        "updated_at": entry.updated_at.isoformat(),
    }


def _validate(question, answer):
    errors = {}
    if not question:
        errors["question"] = "Question is required."
    elif len(question) > MAX_QUESTION_CHARS:
        errors["question"] = f"Question cannot exceed {MAX_QUESTION_CHARS} characters."
    if not answer:
        errors["answer"] = "Answer is required."
    elif len(answer) > MAX_ANSWER_CHARS:
        errors["answer"] = f"Answer cannot exceed {MAX_ANSWER_CHARS} characters."
    return errors


def _queue_index(entry_id):
    from .tasks import index_faq_entry_task

    index_faq_entry_task.delay(entry_id)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@client_required(approved_only=True, allow_suspended_read=True)
def faq_list(request):
    account = request.client_account

    if request.method == "GET":
        entries = FAQEntry.objects.filter(account=account)
        return JsonResponse({"entries": [serialize(e) for e in entries]})

    if FAQEntry.objects.filter(account=account).count() >= MAX_ENTRIES_PER_ACCOUNT:
        return error(f"You can have up to {MAX_ENTRIES_PER_ACCOUNT} FAQ entries.", 409)

    data = read_json(request) or {}
    question = str(data.get("question", "")).strip()
    answer = str(data.get("answer", "")).strip()
    errors = _validate(question, answer)
    if errors:
        return error("Please fix the highlighted fields.", 400, errors)

    entry = FAQEntry.objects.create(account=account, question=question, answer=answer)
    _queue_index(entry.pk)
    return JsonResponse({"entry": serialize(entry)}, status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@client_required(approved_only=True)
def faq_detail(request, entry_id):
    account = request.client_account
    entry = FAQEntry.objects.filter(pk=entry_id, account=account).first()
    if entry is None:
        return error("FAQ entry not found.", 404)

    if request.method == "DELETE":
        entry.delete()
        return JsonResponse({"message": "FAQ entry deleted."})

    data = read_json(request) or {}
    question = str(data.get("question", entry.question)).strip()
    answer = str(data.get("answer", entry.answer)).strip()
    errors = _validate(question, answer)
    if errors:
        return error("Please fix the highlighted fields.", 400, errors)

    changed = question != entry.question or answer != entry.answer
    entry.question = question
    entry.answer = answer
    if changed:
        entry.index_status = FAQEntry.IndexStatus.PENDING
    entry.save()
    if changed:
        _queue_index(entry.pk)
    return JsonResponse({"entry": serialize(entry)})