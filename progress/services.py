"""Read-only aggregation of existing submitted practice records (no Progress table).

Django ORM, Chapter 2 (models/query), Chapter 4 (forms/validation) conventions.
The learning modules are never modified by Progress.
"""
from datetime import timedelta
from statistics import mean
import math
from zoneinfo import ZoneInfo

from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from receptive.models import Attempt as ReceptiveAttempt
from receptive.services.scoring import reference_band_40, overall_reference
from core.productive import valid_band
from writing.models import WritingSubmission
from speaking.models import SpeakingSubmission
from vocabulary.models import Attempt as VocabularyAttempt, Answer as VocabularyAnswer, UserWord

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SKILLS = ("LISTENING", "READING", "WRITING", "SPEAKING", "VOCABULARY")
LABELS = {"LISTENING": "Listening", "READING": "Reading", "WRITING": "Writing", "SPEAKING": "Speaking", "VOCABULARY": "Vocabulary"}


def _is_valid_band(score):
    return score is not None and 0 <= float(score) <= 9


def _score_percent(obj):
    if obj.total_questions and 0 <= obj.correct_answers <= obj.total_questions:
        return round(100.0 * obj.correct_answers / obj.total_questions, 1)
    return None


def _record(skill, obj):
    """One attempt = one history row; use existing result URL (no extra API call)."""
    if skill in ("READING", "LISTENING"):
        title = obj.exercise_snapshot.get("title") or obj.exercise.title
        score = _score_percent(obj)
        status = "Đã nộp"
        link = reverse(f"{skill.lower()}:attempt_result", kwargs={"submission_key": obj.submission_key})
        content_id = obj.exercise_id
    elif skill == "WRITING":
        title = obj.prompt_snapshot.get("title") or obj.prompt.title
        score = float(obj.score) if obj.status == "GRADED" and _is_valid_band(obj.score) else None
        status = obj.get_status_display()
        link = reverse("writing:submission_result", kwargs={"submission_key": obj.submission_key})
        content_id = obj.prompt_id
    elif skill == "SPEAKING":
        title = obj.exercise_snapshot.get("title") or obj.exercise.title
        score = float(obj.overall_score) if obj.status == "GRADED" and _is_valid_band(obj.overall_score) else None
        status = obj.get_status_display()
        link = reverse("speaking:submission_result", kwargs={"submission_key": obj.submission_key})
        content_id = obj.exercise_id
    else:
        title = (obj.topic_snapshot or {}).get("name") or (obj.topic.name if obj.topic_id else "Ôn từ vựng của tôi")
        score = _score_percent(obj)
        status = "Đã nộp"
        link = reverse("vocabulary:result", kwargs={"pk": obj.pk})
        content_id = obj.topic_id or "MY_WORDS"
    return {"skill": skill, "label": LABELS[skill], "title": title,
            "submitted_at": obj.submitted_at, "score": score,
            "unit": "Band" if skill in ("WRITING", "SPEAKING") else "%",
            "status": status, "url": link, "content_id": content_id, "id": obj.pk,
            "exam_band": reference_band_40(obj.correct_answers, skill) if skill in ("READING", "LISTENING") and obj.mode == "EXAM" and obj.total_questions == 40 else None}


def _query(skill, user):
    if skill in ("READING", "LISTENING"):
        return ReceptiveAttempt.objects.filter(user=user, exercise__skill=skill).select_related("exercise")
    if skill == "WRITING":
        return WritingSubmission.objects.filter(user=user).select_related("prompt")
    if skill == "SPEAKING":
        return SpeakingSubmission.objects.filter(user=user).select_related("exercise")
    return VocabularyAttempt.objects.filter(user=user).select_related("topic")


def _activity_days(user):
    """One day counted once, across all 5 modules in local timezone."""
    qs_list = [
        ReceptiveAttempt.objects.filter(user=user),
        WritingSubmission.objects.filter(user=user),
        SpeakingSubmission.objects.filter(user=user),
        VocabularyAttempt.objects.filter(user=user),
    ]
    dates = set()
    for qs in qs_list:
        dates.update(d for d in qs.annotate(local_day=TruncDate("submitted_at", tzinfo=TZ))
                     .values_list("local_day", flat=True).distinct() if d)
    return dates


def streak_info(user):
    dates = _activity_days(user)
    today = timezone.localdate(timezone.now(), timezone=TZ)
    newest = max(dates) if dates else None
    longest, current_run, previous = 0, 0, None
    for day in sorted(dates):
        current_run = current_run + 1 if previous and day - previous == timedelta(days=1) else 1
        longest = max(longest, current_run)
        previous = day
    end = today if today in dates else today - timedelta(days=1)
    current = 0
    while end in dates:
        current += 1
        end -= timedelta(days=1)
    inactivity = (today - newest).days if newest else None
    if inactivity is None:
        reminder = "Bạn chưa bắt đầu luyện tập. Hãy thử một bài học đầu tiên nhé!"
    elif inactivity == 0:
        reminder = "Bạn đã hoàn thành luyện tập hôm nay. Tiếp tục duy trì nhé!"
    elif inactivity == 1:
        reminder = "Đừng quên hoàn thành một bài luyện hôm nay để duy trì streak!"
    elif inactivity == 2:
        reminder = "Đã hai ngày bạn chưa luyện tập. Hãy bắt đầu một bài ngắn hôm nay nhé!"
    elif inactivity < 7:
        reminder = "Đã vài ngày bạn chưa luyện tập. Hãy quay lại với một bài luyện ngắn nhé!"
    elif inactivity < 14:
        reminder = "Bạn đã gián đoạn luyện tập khoảng một tuần. Hãy dành ít phút để bắt đầu lại!"
    else:
        reminder = "Đã lâu rồi bạn chưa luyện IELTS. Hãy quay lại từng bước với một bài luyện phù hợp."
    calendar = [{"date": today - timedelta(days=i), "active": today - timedelta(days=i) in dates}
                for i in range(13, -1, -1)]
    monday = today - timedelta(days=today.weekday())
    week_calendar = [{"date": monday + timedelta(days=i),
                      "short": ("T2", "T3", "T4", "T5", "T6", "T7", "CN")[i],
                      "active": monday + timedelta(days=i) in dates,
                      "is_today": monday + timedelta(days=i) == today,
                      "future": monday + timedelta(days=i) > today}
                     for i in range(7)]
    milestone = next((mark for mark in (30, 14, 7, 3) if current >= mark), None)
    return {"current": current, "longest": longest, "last_date": newest,
            "inactivity": inactivity, "reminder": reminder, "calendar": calendar,
            "week_calendar": week_calendar, "milestone": milestone,
            "studied_today": today in dates}


def recent_records(user, per_skill=3):
    records = []
    for skill in SKILLS:
        records.extend(_record(skill, obj) for obj in _query(skill, user).order_by("-submitted_at")[:per_skill])
    return sorted(records, key=lambda row: row["submitted_at"], reverse=True)


def skill_statistics(user):
    stats = []
    for skill in SKILLS:
        qs = _query(skill, user)
        count = qs.count()
        if skill in ("WRITING", "SPEAKING"):
            field = "score" if skill == "WRITING" else "overall_score"
            scored = qs.filter(status="GRADED", **{f"{field}__isnull": False,
                                                    f"{field}__gte": 0, f"{field}__lte": 9})
            values = list(scored.values_list(field, flat=True))
            last = scored.order_by("-submitted_at").values_list(field, flat=True).first()
            average = round(float(mean(values)), 1) if values else None
            best = round(float(max(values)), 1) if values else None
            latest = round(float(last), 1) if last is not None else None
            score_count = len(values)
            distinct_contents = qs.values("prompt_id" if skill == "WRITING" else "exercise_id").distinct().count()
            unit = "Band"
        else:
            values = []
            for total, correct in qs.values_list("total_questions", "correct_answers"):
                if total and 0 <= correct <= total:
                    values.append(round(correct * 100 / total, 1))
            recent = qs.order_by("-submitted_at").values_list("total_questions", "correct_answers").first()
            latest = (round(100 * recent[1] / recent[0], 1) if recent and recent[0] else None)
            average = round(mean(values), 1) if values else None
            best = max(values) if values else None
            score_count = len(values)
            if skill == "VOCABULARY":
                distinct_contents = qs.exclude(topic_id__isnull=True).values("topic_id").distinct().count()
                if qs.filter(topic_id__isnull=True).exists():
                    distinct_contents += 1  # một nhóm 'ôn kho cá nhân', không bịa Topic
            else:
                distinct_contents = qs.values("exercise_id").distinct().count()
            unit = "%"
        last_date = qs.aggregate(last=Max("submitted_at"))["last"]
        stats.append({"skill": skill, "label": LABELS[skill], "total": count,
                      "scored": score_count, "average": average, "best": best,
                      "latest": latest, "last_date": last_date,
                      "contents": distinct_contents, "unit": unit})
    return stats



def study_nudge(streak):
    """User-facing contextual messages from real submission dates, never AI guesses."""
    days = streak["inactivity"]
    if days is None:
        return {"tone":"start", "icon":"✦", "title":"Hành trình IELTS bắt đầu từ đây!",
                "message":"Bài luyện đầu tiên đang chờ bạn. Bắt đầu ngay để tạo chuỗi học của riêng mình!",
                "action":"Làm bài đầu tiên", "hero":"Một bài luyện hôm nay cũng là một bước tiến."}
    if days == 0:
        return {"tone":"done", "icon":"✓", "title":"Hôm nay bạn đã hoàn thành rồi!",
                "message":"Một ngày học nữa được ghi nhận. Cứ giữ nhịp học phù hợp với bạn nhé!",
                "action":"Luyện thêm một bài", "hero":"Hôm nay bạn đã luyện tập. Cùng giữ phong độ nhé!"}
    if days == 1:
        return {"tone":"keep", "icon":"♨", "title":"Chuỗi học đang đợi bạn!",
                "message":"Hôm qua bạn đã luyện tập. Hoàn thành một bài hôm nay để duy trì chuỗi nhé!",
                "action":"Giữ chuỗi học", "hero":f"Bạn đã có {streak['current']} ngày học liên tiếp. Đừng bỏ lỡ hôm nay!"}
    if days == 2:
        return {"tone":"restart", "icon":"↗", "title":"Mình bắt đầu lại nhé!",
                "message":"Hai ngày chưa luyện tập rồi. Một bài ngắn hôm nay là đủ để khởi động lại.",
                "action":"Khởi động lại", "hero":"Một bước nhỏ là đủ để trở lại nhịp học."}
    if days < 7:
        return {"tone":"restart", "icon":"◷", "title":"IELTS nhớ bạn rồi đấy!",
                "message":"Đã vài ngày bạn chưa luyện tập. Thử quay lại bằng một bài ngắn nhé!",
                "action":"Quay lại luyện tập", "hero":"Không cần học thật nhiều, chỉ cần bắt đầu lại."}
    if days < 14:
        return {"tone":"restart", "icon":"◷", "title":"Một tuần rồi, quay lại thôi!",
                "message":"Nhịp học bị gián đoạn cũng không sao. Bạn có thể bắt đầu lại từ hôm nay.",
                "action":"Bắt đầu lại", "hero":"Hãy lấy lại cảm giác học bằng một bài luyện ngắn."}
    return {"tone":"restart", "icon":"✦", "title":"Lâu quá không gặp, chiến hữu IELTS!",
            "message":"Không cần học quá nhiều ngay đâu. Chọn một bài luyện để lấy lại cảm giác nhé!",
            "action":"Luyện một bài ngay", "hero":"Hành trình học tập luôn có thể bắt đầu lại."}


def mini_chart_data(user, stats):
    """Small real-data trend for the dashboard preview; no artificial samples."""
    eligible = [s for s in stats if s["scored"]]
    if not eligible:
        return {"points":[], "path":"", "label":"Chưa có kết quả", "latest":None,
                "unit":"", "skill":None, "count":0}
    chosen = max(eligible, key=lambda s: (s["scored"] >= 2, s["scored"], s["last_date"] or timezone.now() - timedelta(days=36500)))
    skill = chosen["skill"]
    qs = _query(skill,user)
    if skill in ("WRITING","SPEAKING"):
        score_field = "score" if skill == "WRITING" else "overall_score"
        qs = qs.filter(status="GRADED", **{f"{score_field}__isnull":False,
                   f"{score_field}__gte":0,f"{score_field}__lte":9})
    data = []
    for obj in qs.order_by("-submitted_at")[:10]:
        row = _record(skill,obj)
        if row["score"] is not None:
            data.append(row)
    data.reverse()
    upper = 9 if chosen["unit"] == "Band" else 100
    points = [{"x":round(14+284*i/max(1,len(data)-1),1),
               "y":round(79-62*min(upper,max(0,row["score"]))/upper,1),
               "score":row["score"],"day":row["submitted_at"]}
              for i,row in enumerate(data)]
    return {"points":points, "path":" ".join(f"{p['x']},{p['y']}" for p in points),
            "label":chosen["label"], "latest":data[-1]["score"] if data else None,
            "unit":chosen["unit"], "skill":skill, "count":len(data)}

def current_band_summary(user):
    rows=[]
    for skill in SKILLS[:4]:
        qs=_query(skill,user).order_by('-submitted_at','-pk')
        if skill in ('READING','LISTENING'):
            obj=qs.filter(total_questions=40,mode='EXAM').first()
            band=reference_band_40(obj.correct_answers,skill) if obj else None
        else:
            field='score' if skill=='WRITING' else 'overall_score'
            obj=qs.filter(status='GRADED', **{field+'__isnull':False}).first()
            band=valid_band(getattr(obj,field)) if obj else None
        rows.append({'skill':skill,'label':LABELS[skill],'band':band,'date':obj.submitted_at if obj else None, 'raw': obj.correct_answers if obj and skill in ('READING','LISTENING') else None})
    return {'bands':rows,'overall':overall_reference([r['band'] for r in rows]),'count':sum(r['band'] is not None for r in rows)}

def band_chart_data(user, skill, period="30"):
    """Score series with one consistent IELTS scale; excludes short practice."""
    period = period if period in ('7','30','90','all') else '30'
    qs = _query(skill, user)
    if period != 'all':
        qs = qs.filter(submitted_at__gte=timezone.now()-timedelta(days=int(period)))
    if skill in ('READING','LISTENING'):
        qs = qs.filter(mode='EXAM', total_questions=40)
    else:
        qs = qs.filter(status='GRADED')
    rows=[]
    for obj in qs.order_by('-submitted_at','-pk')[:30]:
        row=_record(skill,obj)
        value=row['exam_band'] if skill in ('READING','LISTENING') else row['score']
        if value is not None:
            rows.append((float(value),row['submitted_at']))
    rows.reverse()
    points=[]
    for i,(score,day) in enumerate(rows):
        x=44+ (532*i/max(1,len(rows)-1) if len(rows)>1 else 266)
        y=170-150*score/9
        points.append({'x':round(x,2),'y':round(y,2),'score':score,'day':day})
    return {'skill':skill,'label':LABELS[skill],'period':period,'points':points,
            'path':' '.join(f"{p['x']},{p['y']}" for p in points),
            'latest':rows[-1][0] if rows else None,'best':max((r[0] for r in rows), default=None),
            'first_date':rows[0][1] if rows else None,'last_date':rows[-1][1] if rows else None,
            'color':{'LISTENING':'#326bb1','READING':'#167f87','WRITING':'#c92127','SPEAKING':'#8151a5'}[skill]}


def dashboard_data(user):
    stats = skill_statistics(user)
    streak = streak_info(user)
    recent = recent_records(user)
    nudge = study_nudge(streak)
    mini_chart = mini_chart_data(user, stats)
    for skill in stats:
        skill["meter_percent"] = round(100*skill["average"]/(9 if skill["unit"] == "Band" else 100), 1) if skill["average"] is not None else None
    # A word is practiced only if at least one submitted answer has actual user input.
    practiced_words = (VocabularyAnswer.objects.filter(attempt__user=user)
                       .exclude(user_answer="").values("word_id").distinct().count())
    correct_words = (VocabularyAnswer.objects.filter(attempt__user=user, is_correct=True)
                     .exclude(user_answer="").values("word_id").distinct().count())
    saved_words = UserWord.objects.filter(user=user).count()
    marked_learned = UserWord.objects.filter(user=user, status="LEARNED").count()
    return {"band_charts": [band_chart_data(user, skill) for skill in SKILLS[:4]], "band_summary": current_band_summary(user), "skills": stats, "total_attempts": sum(s["total"] for s in stats),
            "distinct_contents": sum(s["contents"] for s in stats),
            "ielts_skills": sum(s["total"] > 0 for s in stats if s["skill"] != "VOCABULARY"),
            "practiced_words": practiced_words, "correct_words": correct_words,
            "saved_words": saved_words, "marked_learned": marked_learned,
            "streak": streak, "nudge": nudge, "mini_chart": mini_chart, "recent": recent[:3],
            "speaking_total_attempts": stats[3]["total"],
            "speaking_graded_count": stats[3]["scored"],
            "speaking_avg_score": stats[3]["average"],
            "writing_total_attempts": stats[2]["total"],
            "writing_graded_count": stats[2]["scored"],
            "writing_avg_score": stats[2]["average"],
            "listening_count": stats[0]["total"], "reading_count": stats[1]["total"]}


def chart_data(user, skill, period):
    skill = skill if skill in SKILLS else "VOCABULARY"
    period = period if period in ("7", "30", "90", "all") else "30"
    qs = _query(skill, user)
    if period != "all":
        qs = qs.filter(submitted_at__gte=timezone.now() - timedelta(days=int(period)))
    if skill in ("WRITING", "SPEAKING"):
        score_field = "score" if skill == "WRITING" else "overall_score"
        qs = qs.filter(status="GRADED", **{f"{score_field}__isnull":False, f"{score_field}__gte":0, f"{score_field}__lte":9})
    rows = []
    for obj in qs.order_by("submitted_at"):
        row = _record(skill, obj)
        if row["score"] is not None:
            rows.append(row)
    coords = []
    top = 9 if skill in ("WRITING", "SPEAKING") else 100
    for i, row in enumerate(rows):
        x = round(35 + (660 * i / max(1, len(rows)-1)), 1)
        y = round(165 - (130 * row["score"] / top), 1)
        coords.append({"x":x, "y":y, "score":row["score"], "day":row["submitted_at"], "skill":row["label"]})
    return {"points":coords, "path":" ".join(f'{p["x"]},{p["y"]}' for p in coords),
            "skill":skill, "period":period, "label":LABELS[skill],
            "unit":"Band / 9" if top == 9 else "Tỷ lệ đúng / 100%", "top":top}


def history_data(user, skill="ALL", status="ALL", period="all", page=1):
    skill = skill if skill in SKILLS else "ALL"
    status = status if status in ("ALL", "GRADED", "GRADING", "FAILED", "DONE") else "ALL"
    period = period if period in ("7", "30", "90", "all") else "all"
    page = max(1, min(int(page), 100))
    limit = page * 10 + 1
    records = []
    for name in SKILLS:
        if skill != "ALL" and name != skill:
            continue
        qs = _query(name, user)
        if period != "all":
            qs = qs.filter(submitted_at__gte=timezone.now() - timedelta(days=int(period)))
        if name in ("WRITING", "SPEAKING"):
            if status in ("GRADED", "GRADING", "FAILED"):
                qs = qs.filter(status=status)
            elif status == "DONE":
                continue
        elif status not in ("ALL", "DONE"):
            continue
        records.extend(_record(name, obj) for obj in qs.order_by("-submitted_at")[:limit])
    records.sort(key=lambda row:row["submitted_at"], reverse=True)
    start = (page-1)*10
    return {"rows": records[start:start+10], "page":page, "has_prev":page>1,
            "has_next":len(records)>start+10, "skill":skill, "status":status, "period":period}


def admin_summary():
    """UC-PRG-02: only submissions; no averaging incompatible band and percentage."""
    from django.contrib.auth import get_user_model
    from accounts.permissions import HOC_VIEN_GROUP
    active = get_user_model().objects.filter(groups__name=HOC_VIEN_GROUP).distinct().count()
    user_ids = set()
    counts = {}
    for skill in SKILLS:
        if skill in ("LISTENING", "READING"):
            q = ReceptiveAttempt.objects.filter(exercise__skill=skill)
        elif skill == "WRITING":q = WritingSubmission.objects.all()
        elif skill == "SPEAKING":q = SpeakingSubmission.objects.all()
        else:q = VocabularyAttempt.objects.all()
        counts[skill] = q.count()
        user_ids.update(q.values_list("user_id", flat=True).distinct())
    recent = []
    for skill in SKILLS:
        if skill in ("LISTENING", "READING"):
            qs = ReceptiveAttempt.objects.filter(exercise__skill=skill).select_related("exercise", "user")
        elif skill == "WRITING":
            qs = WritingSubmission.objects.all().select_related("prompt", "user")
        elif skill == "SPEAKING":
            qs = SpeakingSubmission.objects.all().select_related("exercise", "user")
        else:
            qs = VocabularyAttempt.objects.all().select_related("topic", "user")
        for obj in qs.order_by("-submitted_at")[:3]:
            row = _record(skill, obj)
            row["username"] = obj.user.get_full_name() or obj.user.username
            recent.append(row)
    recent.sort(key=lambda item: item["submitted_at"], reverse=True)
    return {"active_students":active, "ever_practiced":len(user_ids),
            "total_attempts":sum(counts.values()), "counts":counts,
            "recent":recent[:5]}


def admin_analytics(period="30"):
    """Learning Analytics Dashboard aggregation for teacher overview.
    Strictly read-only; calculates KPIs, chart coordinates, module performance,
    AI grading health, insights, and engagement without altering models.
    """
    from django.contrib.auth import get_user_model
    from accounts.permissions import HOC_VIEN_GROUP

    User = get_user_model()
    now = timezone.now()
    today = timezone.localdate(now, timezone=TZ)

    # 1. Determine period window
    if period in ("7", "14", "30"):
        days_count = int(period)
        cutoff = now - timedelta(days=days_count)
    else:
        period = "all"
        days_count = 30
        cutoff = None

    # 2. Student scope
    active_group_students = User.objects.filter(groups__name=HOC_VIEN_GROUP)
    active_student_ids = set(active_group_students.values_list("pk", flat=True))

    all_practiced_ids = set()
    models_map = {
        "READING": (ReceptiveAttempt, "exercise__skill", "READING"),
        "LISTENING": (ReceptiveAttempt, "exercise__skill", "LISTENING"),
        "WRITING": (WritingSubmission, None, None),
        "SPEAKING": (SpeakingSubmission, None, None),
        "VOCABULARY": (VocabularyAttempt, None, None),
    }

    # Module models without filter
    base_qs = {
        "LISTENING": ReceptiveAttempt.objects.filter(exercise__skill="LISTENING"),
        "READING": ReceptiveAttempt.objects.filter(exercise__skill="READING"),
        "WRITING": WritingSubmission.objects.all(),
        "SPEAKING": SpeakingSubmission.objects.all(),
        "VOCABULARY": VocabularyAttempt.objects.all(),
    }

    period_qs = {}
    for skill, qs in base_qs.items():
        all_practiced_ids.update(qs.values_list("user_id", flat=True).distinct())
        if cutoff:
            period_qs[skill] = qs.filter(submitted_at__gte=cutoff)
        else:
            period_qs[skill] = qs

    all_student_ids = set(active_student_ids) | set(all_practiced_ids)
    total_students_count = len(all_student_ids)
    active_role_count = len(active_student_ids)

    # Attempts count
    period_attempts = {skill: qs.count() for skill, qs in period_qs.items()}
    total_period_attempts = sum(period_attempts.values())
    all_time_attempts = sum(qs.count() for qs in base_qs.values())

    # Active students in the selected period (or 7 days if 'all')
    recent_active_window = cutoff
    recent_active_uids = set()
    for qs in base_qs.values():
        recent_active_uids.update(
            (qs.filter(submitted_at__gte=recent_active_window) if recent_active_window else qs).values_list("user_id", flat=True).distinct()
        )
    active_students_count = len(recent_active_uids)
    active_rate = round((active_students_count / max(1, total_students_count)) * 100, 1)

    avg_attempts_per_student = round(total_period_attempts / max(1, total_students_count), 1)

    # 3. Student inactivity & At-risk detection
    user_last_attempt = {}
    user_attempt_counts = {uid: 0 for uid in all_student_ids}

    for qs in base_qs.values():
        for row in qs.values("user_id").annotate(last_at=Max("submitted_at"), n=Count("pk")):
            uid = row["user_id"]
            user_attempt_counts[uid] = user_attempt_counts.get(uid, 0) + row["n"]
            if uid not in user_last_attempt or (row["last_at"] and row["last_at"] > user_last_attempt[uid]):
                user_last_attempt[uid] = row["last_at"]

    at_risk_list = []
    never_practiced_count = 0
    inactive_14d_count = 0
    inactive_7d_count = 0

    for u in active_group_students:
        last_dt = user_last_attempt.get(u.pk)
        if not last_dt:
            never_practiced_count += 1
            days_inactive = None
            risk_tier = "never"
        else:
            local_date = timezone.localtime(last_dt, TZ).date()
            days_inactive = (today - local_date).days
            if days_inactive >= 14:
                inactive_14d_count += 1
                risk_tier = "high"
            elif days_inactive >= 7:
                inactive_7d_count += 1
                risk_tier = "medium"
            else:
                risk_tier = "safe"

        if risk_tier in ("never", "high", "medium"):
            at_risk_list.append({
                "user": u,
                "name": u.get_full_name() or u.username,
                "email": u.email,
                "days_inactive": days_inactive,
                "last_at": last_dt,
                "risk_tier": risk_tier,
                "total_attempts": user_attempt_counts.get(u.pk, 0),
            })

    # Sort at_risk: never first, then descending inactivity
    at_risk_list.sort(key=lambda x: (0 if x["risk_tier"] == "never" else 1, -(x["days_inactive"] or 0)))
    total_at_risk = len(at_risk_list)

    # 4. Trend Chart (Area / Line Chart)
    # Collect daily attempts for the chart window
    chart_days = 30 if period == "all" else days_count
    chart_start_date = today - timedelta(days=chart_days - 1)
    
    daily_counts = {chart_start_date + timedelta(days=i): 0 for i in range(chart_days)}
    chart_cutoff = timezone.make_aware(timezone.datetime.combine(chart_start_date, timezone.datetime.min.time()), TZ)

    for qs in base_qs.values():
        daily_rows = (
            qs.filter(submitted_at__gte=chart_cutoff)
            .annotate(day=TruncDate("submitted_at", tzinfo=TZ))
            .values("day")
            .annotate(cnt=Count("pk"))
        )
        for r in daily_rows:
            d = r["day"]
            if d in daily_counts:
                daily_counts[d] += r["cnt"]

    # Scale to SVG viewport (viewBox: 0 0 680 160)
    chart_max_val = max(daily_counts.values()) if daily_counts and max(daily_counts.values()) > 0 else 5
    svg_w, svg_h = 680, 160
    pad_x, pad_y_top, pad_y_bottom = 20, 20, 30
    plot_w = svg_w - 2 * pad_x
    plot_h = svg_h - pad_y_top - pad_y_bottom

    points = []
    days_list = sorted(daily_counts.keys())
    step_x = plot_w / max(1, len(days_list) - 1)

    for i, d in enumerate(days_list):
        val = daily_counts[d]
        x = round(pad_x + i * step_x, 1)
        y = round(pad_y_top + (1 - val / chart_max_val) * plot_h, 1)
        points.append({
            "x": x,
            "y": y,
            "date": d.strftime("%d/%m"),
            "count": val,
            "is_weekend": d.weekday() >= 5
        })

    if points:
        line_path = "M " + " L ".join(f"{p['x']},{p['y']}" for p in points)
        area_path = (
            f"M {points[0]['x']},{pad_y_top + plot_h} "
            + " ".join(f"L {p['x']},{p['y']}" for p in points)
            + f" L {points[-1]['x']},{pad_y_top + plot_h} Z"
        )
    else:
        line_path = ""
        area_path = ""

    # 5. Engagement Donut Chart
    # Group students into tiers based on attempts
    tier_counts = {"high": 0, "medium": 0, "low": 0, "zero": 0}
    for uid in all_student_ids:
        cnt = user_attempt_counts.get(uid, 0)
        if cnt >= 10:
            tier_counts["high"] += 1
        elif cnt >= 4:
            tier_counts["medium"] += 1
        elif cnt >= 1:
            tier_counts["low"] += 1
        else:
            tier_counts["zero"] += 1

    total_engagement = max(1, total_students_count)
    donut_radius = 42
    circumference = 2 * math.pi * donut_radius  # ~263.89

    donut_segments = []
    tiers_meta = [
        ("high", "Chăm chỉ (≥10 bài)", tier_counts["high"], "#16A34A"),
        ("medium", "Đều đặn (4–9 bài)", tier_counts["medium"], "#3B82F6"),
        ("low", "Thỉnh thoảng (1–3 bài)", tier_counts["low"], "#F59E0B"),
        ("zero", "Chưa làm bài nào (0 bài)", tier_counts["zero"], "#E2E8F0"),
    ]

    accumulated_pct = 0.0
    for key, label, count, color in tiers_meta:
        pct = (count / total_engagement)
        dash_len = pct * circumference
        offset = - (accumulated_pct * circumference)
        donut_segments.append({
            "key": key,
            "label": label,
            "count": count,
            "pct": round(pct * 100, 1),
            "color": color,
            "dasharray": f"{dash_len:.2f} {circumference:.2f}",
            "dashoffset": f"{offset:.2f}",
        })
        accumulated_pct += pct

    # 6. 5 Module Cards with Circular Progress
    MODULE_CONFIG = {
        "LISTENING": {"color": "#3B5FBD", "bg": "#EFF4FF", "icon": "♫", "unit": "%"},
        "READING": {"color": "#0E8A9E", "bg": "#E6F8FA", "icon": "▤", "unit": "%"},
        "WRITING": {"color": "#C92127", "bg": "#FFF0F1", "icon": "✎", "unit": "Band"},
        "SPEAKING": {"color": "#8B55AC", "bg": "#F7F0FC", "icon": "◉", "unit": "Band"},
        "VOCABULARY": {"color": "#1B8866", "bg": "#EDF9F4", "icon": "Aa", "unit": "%"},
    }

    modules_data = []
    circ_radius = 28
    circ_circumference = 2 * math.pi * circ_radius  # ~175.93

    for skill in SKILLS:
        qs = period_qs[skill]
        conf = MODULE_CONFIG[skill]
        attempts_n = qs.count()
        stud_count = qs.values("user_id").distinct().count()

        # Score calculation
        if skill in ("WRITING", "SPEAKING"):
            score_col = "score" if skill == "WRITING" else "overall_score"
            scored_vals = list(
                qs.filter(status="GRADED", **{f"{score_col}__isnull": False, f"{score_col}__gte": 0, f"{score_col}__lte": 9})
                .values_list(score_col, flat=True)
            )
            avg_score = round(float(mean(scored_vals)), 1) if scored_vals else None
            # Progress % of Band 9.0
            percent_of_max = round((avg_score / 9.0) * 100, 1) if avg_score is not None else 0
        else:
            pct_list = []
            for tq, ca in qs.values_list("total_questions", "correct_answers"):
                if tq and 0 <= ca <= tq:
                    pct_list.append((ca * 100.0) / tq)
            avg_score = round(mean(pct_list), 1) if pct_list else None
            percent_of_max = avg_score if avg_score is not None else 0

        band_vals = []
        if skill in ("READING", "LISTENING"):
            band_vals = [v for raw in qs.filter(total_questions=40, mode="EXAM").values_list("correct_answers",flat=True) if (v:=reference_band_40(raw,skill)) is not None]
        dash_progress = (percent_of_max / 100.0) * circ_circumference

        modules_data.append({
            "skill": skill,
            "label": LABELS[skill],
            "attempts": attempts_n,
            "students_count": stud_count,
            "avg_score": avg_score,
            "unit": conf["unit"],
            "percent": percent_of_max,
            "color": conf["color"],
            "bg": conf["bg"],
            "icon": conf["icon"],
            "band_average": (round(mean([float(v) for v in band_vals]),1) if band_vals else None),
            "circ_dash": f"{dash_progress:.2f} {circ_circumference:.2f}",
            "circ_full": f"{circ_circumference:.2f}",
        })

    # 7. AI Grading Status
    ai_status = {
        "writing": {
            "grading": WritingSubmission.objects.filter(status="GRADING").count(),
            "graded": WritingSubmission.objects.filter(status="GRADED").count(),
            "failed": WritingSubmission.objects.filter(status="FAILED").count(),
            "total": WritingSubmission.objects.count(),
        },
        "speaking": {
            "grading": SpeakingSubmission.objects.filter(status="GRADING").count(),
            "graded": SpeakingSubmission.objects.filter(status="GRADED").count(),
            "failed": SpeakingSubmission.objects.filter(status="FAILED").count(),
            "total": SpeakingSubmission.objects.count(),
        }
    }

    # 8. Top Active Students (by attempt count)
    top_student_rows = []
    top_uids = sorted(user_attempt_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    user_objs = {u.pk: u for u in User.objects.filter(pk__in=[uid for uid, _ in top_uids])}
    for uid, cnt in top_uids:
        if cnt > 0 and uid in user_objs:
            u = user_objs[uid]
            top_student_rows.append({
                "user": u,
                "name": u.get_full_name() or u.username,
                "email": u.email,
                "attempts": cnt,
                "last_at": user_last_attempt.get(uid),
                "is_student": uid in active_student_ids,
            })

    # 9. Smart Learning Insights
    insights = []
    # Insight 1: Most practiced module
    if period_attempts:
        top_skill = max(period_attempts.items(), key=lambda x: x[1])
        if top_skill[1] > 0:
            insights.append({
                "type": "positive",
                "icon": "🔥",
                "title": f"Kỹ năng được làm nhiều nhất: {LABELS[top_skill[0]]}",
                "desc": f"Ghi nhận {top_skill[1]} bài nộp, chiếm {round(top_skill[1] / max(1, total_period_attempts) * 100)}% tổng số lượt làm bài trong kỳ."
            })

    # Insight 2: Activity engagement
    if active_rate >= 50:
        insights.append({
            "type": "positive",
            "icon": "✨",
            "title": f"Mức độ chuyên cần tốt ({active_rate}% học viên làm bài)",
            "desc": f"Có {active_students_count}/{total_students_count} học viên tích cực làm bài tập và duy trì tiến độ học tập."
        })
    else:
        insights.append({
            "type": "warning",
            "icon": "⚠️",
            "title": f"Cần nhắc nhở làm bài ({active_rate}% học viên hoạt động)",
            "desc": f"Hiện có {active_students_count} trong tổng số {total_students_count} học viên có nộp bài trong kỳ. Giáo viên nên gửi thông báo đôn đốc."
        })

    # Insight 3: Pending AI Grading
    pending_ai = ai_status["writing"]["grading"] + ai_status["speaking"]["grading"]
    failed_ai = ai_status["writing"]["failed"] + ai_status["speaking"]["failed"]
    graded_ai = ai_status["writing"]["graded"] + ai_status["speaking"]["graded"]
    total_ai = ai_status["writing"]["total"] + ai_status["speaking"]["total"]
    if failed_ai:
        insights.append({"type":"warning", "title":f"{failed_ai} bài chấm AI thất bại", "desc":f"Đã có điểm {graded_ai}/{total_ai} bài; {pending_ai} bài đang chấm. Không tính bài lỗi là đã chấm thành công."})
    elif pending_ai > 0:
        insights.append({
            "type": "info",
            "icon": "🤖",
            "title": f"{pending_ai} bài đang trong hàng đợi chấm AI",
            "desc": f"Hệ thống đang xử lý {ai_status['writing']['grading']} bài Writing và {ai_status['speaking']['grading']} bài Speaking."
        })
    elif total_ai and graded_ai == total_ai:
        insights.append({"type":"positive", "title":"Tất cả bài AI đã có điểm", "desc":f"{graded_ai}/{total_ai} bài nộp đã có kết quả."})
    else:
        insights.append({"type":"info", "title":"Chưa đủ dữ liệu chấm AI", "desc":f"Đã có điểm {graded_ai}/{total_ai} bài."})

    # Insight 4: At-risk attention
    if total_at_risk > 0:
        insights.append({
            "type": "warning",
            "icon": "⏱",
            "title": f"Có {total_at_risk} học viên cần liên hệ nhắc nhở",
            "desc": f"Gồm {never_practiced_count} học viên chưa nộp bài nào và {inactive_14d_count + inactive_7d_count} học viên đã hơn 7 ngày chưa làm bài."
        })

    # 10. Recent history (all skills combined)
    recent = []
    for skill in SKILLS:
        qs = base_qs[skill].select_related("user")
        if skill in ("LISTENING", "READING"):
            qs = qs.select_related("exercise")
        elif skill == "WRITING":
            qs = qs.select_related("prompt")
        elif skill == "SPEAKING":
            qs = qs.select_related("exercise")
        else:
            qs = qs.select_related("topic")

        for obj in qs.order_by("-submitted_at")[:4]:
            row = _record(skill, obj)
            row["username"] = obj.user.get_full_name() or obj.user.username
            row["email"] = obj.user.email
            recent.append(row)

    recent.sort(key=lambda item: item["submitted_at"], reverse=True)

    return {
        "period": period,
        "kpis": {
            "total_students": total_students_count,
            "active_role_students": active_role_count,
            "active_recent_students": active_students_count,
            "active_rate": active_rate,
            "total_attempts": total_period_attempts,
            "all_time_attempts": all_time_attempts,
            "avg_attempts": avg_attempts_per_student,
            "at_risk_count": total_at_risk,
            "never_practiced_count": never_practiced_count,
        },
        "trend_chart": {
            "points": points,
            "line_path": line_path,
            "area_path": area_path,
            "max_val": chart_max_val,
            "days_count": len(days_list),
        },
        "donut_chart": {
            "segments": donut_segments,
            "total": total_students_count,
            "active_percent": round((tier_counts["high"] / total_engagement) * 100, 1),
        },
        "modules": modules_data,
        "insights": insights,
        "at_risk": {
            "total": total_at_risk,
            "never_count": never_practiced_count,
            "inactive_14d": inactive_14d_count,
            "inactive_7d": inactive_7d_count,
            "list": at_risk_list[:12],
        },
        "ai_status": ai_status,
        "top_students": top_student_rows,
        "recent": recent[:8],
    }
