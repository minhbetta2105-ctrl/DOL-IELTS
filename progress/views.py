"""Progress read-only dashboard; built from existing module submissions."""
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from accounts.permissions import hoc_vien_required
from . import services

SECTIONS = {"skills": "progress/_skills_detail.html", "chart": "progress/_chart_detail.html",
            "history": "progress/_history_detail.html"}


def _section_context(user, section, params):
    if section == "skills":
        return {"skills": services.skill_statistics(user)}
    if section == "chart":
        skill = params.get("skill", "READING")
        period = params.get("period", "30")
        if skill in services.SKILLS[:4]:
            series = services.band_chart_data(user, skill, period)
            context = {"band_series": series, "skill": skill, "period": series["period"]}
        else:
            context = services.chart_data(user, skill, period)
        context["skill_choices"] = [(c, services.LABELS[c]) for c in services.SKILLS]
        return context
    if section == "history":
        page = params.get("page", "1")
        page = int(page) if page.isdecimal() else 1
        return {**services.history_data(user, params.get("skill", "ALL"),
                                     params.get("status", "ALL"), params.get("period", "all"), page), "skill_choices": [(c, services.LABELS[c]) for c in services.SKILLS]}
    raise Http404("Mục tiến độ không tồn tại.")


def dashboard_context(user, *, admin=False):
    data = services.dashboard_data(user)
    data["read_only_admin"] = admin
    data["student"] = user
    data["section_urls"] = {
        section: reverse("management:student_progress_section", kwargs={"user_id":user.pk,"section":section})
        if admin else reverse("progress:section", kwargs={"section":section})
        for section in SECTIONS
    }
    return data


@hoc_vien_required
def progress_dashboard(request):
    """UC-PRG-01: one page, three detailed sections expand in place."""
    context = dashboard_context(request.user)
    # Compatibility with older lesson tests that check Speaking criteria in context.
    graded = services._query("SPEAKING", request.user).filter(status="GRADED", overall_score__isnull=False)
    from django.db.models import Avg
    avgs = graded.aggregate(fluency=Avg("fluency_score"), pronunciation=Avg("pronunciation_score"),
                            vocabulary=Avg("vocabulary_score"), grammar=Avg("grammar_score"))
    for key, value in avgs.items():
        context[f"speaking_avg_{'vocab' if key == 'vocabulary' else key}"] = round(float(value), 1) if value is not None else None
    context["active_nav"] = "progress"
    return render(request, "progress/dashboard.html", context)


@hoc_vien_required
def section(request, section):
    if section not in SECTIONS:
        raise Http404()
    return render(request, SECTIONS[section], _section_context(request.user, section, request.GET))
