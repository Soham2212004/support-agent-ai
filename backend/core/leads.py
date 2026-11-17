"""Client-facing leads list and CSV export — every unique visitor who has started a chat."""
import csv

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .api import client_required
from .models import Lead


def _serialize(lead):
    return {
        "name": lead.name,
        "email": lead.email,
        "first_seen_at": lead.first_seen_at.isoformat(),
        "last_seen_at": lead.last_seen_at.isoformat(),
        "conversation_count": lead.conversation_count,
    }


@require_GET
@client_required(approved_only=True)
def lead_list(request):
    leads = Lead.objects.filter(account=request.client_account)
    return JsonResponse({"leads": [_serialize(lead) for lead in leads], "count": leads.count()})


@require_GET
@client_required(approved_only=True)
def lead_export_csv(request):
    leads = Lead.objects.filter(account=request.client_account)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="leads.csv"'
    writer = csv.writer(response)
    writer.writerow(["name", "email", "first_seen_at", "last_seen_at", "conversation_count"])
    for lead in leads:
        # Formula-injection guard: a cell starting with =, +, - or @ opens as a formula in
        # Excel/Sheets, so a visitor-supplied name could execute code on whoever opens the export.
        name = lead.name
        if name and name[0] in ("=", "+", "-", "@"):
            name = "'" + name
        writer.writerow([name, lead.email, lead.first_seen_at.isoformat(), lead.last_seen_at.isoformat(), lead.conversation_count])
    return response