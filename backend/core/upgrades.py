"""Client-facing upgrade request creation. Staff action it from Django admin — no billing."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api import client_required, error, read_json
from .models import Plan, UpgradeRequest


@csrf_exempt
@require_POST
@client_required(approved_only=True)
def request_upgrade(request):
    account = request.client_account
    data = read_json(request) or {}
    plan_key = str(data.get("plan", "")).strip().lower()
    message = str(data.get("message", "")).strip()[:1000]

    plan = Plan.objects.filter(key=plan_key).exclude(key=Plan.Key.INTERNAL).first()
    if plan is None:
        return error("Choose a valid plan to request.", 400)
    if account.plan_id == plan.pk:
        return error(f"You're already on the {plan.name} plan.", 400)

    existing = UpgradeRequest.objects.filter(account=account, status=UpgradeRequest.Status.OPEN).first()
    if existing:
        return error("You already have an open upgrade request.", 409)

    UpgradeRequest.objects.create(account=account, requested_plan=plan, message=message)
    return JsonResponse({"message": "Your request has been sent to our team."}, status=201)