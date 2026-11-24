"""UC-PRG-02/03/04 for business administrators, read-only and permission-bound.
Only Progress management URLs/templates change. Django Admin and account roles unchanged.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count, Max
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import HOC_VIEN_GROUP
from .permissions import teacher_dashboard_required
from receptive.models import Attempt as ReceptiveAttempt
from writing.models import WritingSubmission
from speaking.models import SpeakingSubmission
from vocabulary.models import Attempt as VocabularyAttempt
from progress import services, views as progress_views


def _require_student_view_perm(request):
    if not (request.user.is_superuser or request.user.has_perm("auth.view_user")):
        raise PermissionDenied("Chưa được cấp quyền xem tiến độ học viên.")


def _summary_counts():
    models = (ReceptiveAttempt, WritingSubmission, SpeakingSubmission, VocabularyAttempt)
    ids = set(get_user_model().objects.filter(groups__name=HOC_VIEN_GROUP).values_list("pk", flat=True))
    for model in models:
        ids.update(model.objects.values_list("user_id", flat=True).distinct())
    return ids


@teacher_dashboard_required
def student_progress_list(request):
    _require_student_view_perm(request)
    period = request.GET.get('period', '30')
    if period not in ('7', '14', '30', 'all'):
        period = '30'
    User = get_user_model()
    q = request.GET.get("q", "").strip()
    state = request.GET.get("state", "ALL")
    days = request.GET.get("inactive", "")
    ids = _summary_counts()
    queryset = User.objects.filter(pk__in=ids).order_by("username", "pk")
    if q:
        queryset = queryset.filter(Q(username__icontains=q) | Q(email__icontains=q)
                                   | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if state == "ACTIVE":
        queryset = queryset.filter(groups__name=HOC_VIEN_GROUP)
    elif state == "FORMER":
        queryset = queryset.exclude(groups__name=HOC_VIEN_GROUP)
    # Avoid an ORM query per student. Aggregate attempts for all users by model.
    totals, last, contents = {}, {}, {}
    for model in (ReceptiveAttempt, WritingSubmission, SpeakingSubmission, VocabularyAttempt):
        for row in model.objects.filter(user_id__in=ids).values("user_id").annotate(
                n=Count("pk"), last_date=Max("submitted_at")):
            uid = row["user_id"]
            totals[uid] = totals.get(uid, 0) + row["n"]
            if uid not in last or (row["last_date"] and row["last_date"] > last[uid]):
                last[uid] = row["last_date"]
    for model, field, filters in (
        (ReceptiveAttempt, "exercise_id", {}),
        (WritingSubmission, "prompt_id", {}),
        (SpeakingSubmission, "exercise_id", {}),
        (VocabularyAttempt, "topic_id", {"topic_id__isnull": False}),
    ):
        grouped = model.objects.filter(user_id__in=ids, **filters).values("user_id").annotate(
            unique_n=Count(field, distinct=True))
        for r in grouped:
            contents[r["user_id"]] = contents.get(r["user_id"], 0) + r["unique_n"]
    # Một phiên ôn hỗn hợp từ kho cá nhân là một nội dung, không phải chủ đề giả.
    for uid in VocabularyAttempt.objects.filter(user_id__in=ids, topic_id__isnull=True).values_list("user_id", flat=True).distinct():
        contents[uid] = contents.get(uid, 0) + 1
    active_ids = set(User.objects.filter(pk__in=ids, groups__name=HOC_VIEN_GROUP).values_list("pk", flat=True))
    today = timezone.localdate(timezone.now(), timezone=ZoneInfo("Asia/Ho_Chi_Minh"))
    # filter inactivity after grouped query, no N+1 query
    selected = []
    for u in queryset:
        timestamp = last.get(u.pk)
        inactive = (today - timezone.localtime(timestamp, ZoneInfo("Asia/Ho_Chi_Minh")).date()).days if timestamp else None
        if days == "never" and inactive is not None:
            continue
        if days in ("3", "7", "14") and (inactive is None or inactive < int(days)):
            continue
        selected.append({"user":u,"total":totals.get(u.pk,0),"contents":contents.get(u.pk,0),"is_student":u.pk in active_ids,
                         "last_at":timestamp,"inactive":inactive})
    page_obj = Paginator(selected, 10).get_page(request.GET.get("page"))
    # UC-PRG-02: analytics dashboard with real data from existing submissions.
    return render(request, "management/student_progress_list.html", {
        "records":page_obj.object_list, "page_obj":page_obj, "q":q, "state":state,
        "inactive_filter":days, "analytics":services.admin_analytics(period),
        "period":period, "active_nav":"student_progress", "count":len(selected),
    })


@teacher_dashboard_required
def student_progress_detail(request, user_id):
    _require_student_view_perm(request)
    user = get_object_or_404(get_user_model(), pk=user_id)
    context = progress_views.dashboard_context(user, admin=True)
    context.update({"student":user,"active_nav":"student_progress"})
    return render(request, "management/student_progress_detail.html", context)


@teacher_dashboard_required
def student_progress_section(request, user_id, section):
    _require_student_view_perm(request)
    user = get_object_or_404(get_user_model(), pk=user_id)
    if section not in progress_views.SECTIONS:
        raise Http404()
    return render(request, progress_views.SECTIONS[section],
                  {**progress_views._section_context(user, section, request.GET), "read_only_admin": True})


@teacher_dashboard_required
def grading_detail(request):
    _require_student_view_perm(request)
    skill = request.GET.get("skill", "ALL").upper()
    status = request.GET.get("status", "FAILED").upper()
    if skill not in ("ALL", "WRITING", "SPEAKING"):
        skill = "ALL"
    if status not in ("ALL", "FAILED", "GRADING", "GRADED"):
        status = "FAILED"
    q = request.GET.get("q", "").strip()
    rows = []
    for name, model, rel in (("WRITING", WritingSubmission, "prompt"), ("SPEAKING", SpeakingSubmission, "exercise")):
        if skill not in ("ALL", name):
            continue
        qs = model.objects.select_related("user", rel)
        if status != "ALL":
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(user__username__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(**{rel+"__title__icontains": q}))
        for obj in qs:
            rows.append({"skill": name.title(), "user": obj.user, "title": getattr(obj, rel).title,
                         "status": obj.status, "submitted_at": obj.submitted_at, "id": obj.pk,
                         "score": obj.score if name == "WRITING" else obj.overall_score,
                         "url": reverse("management:grading_submission", kwargs={"skill":name.lower(),"pk":obj.pk}) if request.user.has_perm(name.lower()+".view_"+name.lower()+"submission") else None})
    rows.sort(key=lambda r: (r["submitted_at"],r["id"]), reverse=True)
    page_obj = Paginator(rows, 20).get_page(request.GET.get("page"))
    return render(request, "management/grading_detail.html", {"page_obj": page_obj, "skill":skill,"status":status,"q":q,"active_nav":"student_progress"})


@teacher_dashboard_required
def grading_submission(request, skill, pk):
    _require_student_view_perm(request)
    if skill not in ("writing", "speaking"):
        raise Http404()
    if not request.user.has_perm(f"{skill}.view_{skill}submission"):
        raise PermissionDenied()
    model = WritingSubmission if skill == "writing" else SpeakingSubmission
    obj = get_object_or_404(model.objects.select_related("user"), pk=pk)
    snapshot = obj.prompt_snapshot if skill == "writing" else obj.exercise_snapshot
    return render(request,"management/grading_submission.html", {"obj":obj,"skill":skill,"snapshot":snapshot or {},"active_nav":"student_progress"})
