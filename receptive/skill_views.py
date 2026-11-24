"""Shared Reading/Listening views. Django MVT: URLs -> views -> ORM -> templates.

No autosave table: the student explicitly chose a 20-business-table ERD.
An active timed attempt stores only start/deadline/UUID in Django Session.
"""
import json
import re
import uuid
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from receptive.models import Exercise, Question, Attempt
from receptive.services.submission import submit_receptive_exercise
from receptive.services.scoring import band_ranges, full_test_minutes, reference_band_40
from core.productive import topic_art
from receptive.services.audio import has_audio

TYPE_LABELS = {
    "MCQ": "Multiple Choice", "SHORT_TEXT": "Điền đáp án", "MATCHING": "Matching",
    "TFNG": "True/False/Not Given", "YNNG": "Yes/No/Not Given",
}


def _skill(skill):
    if skill not in (Exercise.Skill.READING, Exercise.Skill.LISTENING):
        raise ValueError("Invalid skill")
    return skill.lower()


def _active_key(user, exercise_id, mode):
    return f"receptive_active_v2_{user.pk}_{exercise_id}_{mode}"


def _mode(raw):
    return Attempt.Mode.EXAM if str(raw).lower() == "exam" else Attempt.Mode.PRACTICE


def list_exercises(request, skill):
    ns = _skill(skill)
    base = Exercise.objects.filter(skill=skill, status=Exercise.Status.PUBLISHED)
    qs = base
    query = request.GET.get("q", "").strip()[:120]
    topic = request.GET.get("topic", "").strip()[:100]
    qtype = request.GET.get("question_type", "")
    level = request.GET.get("level", "")
    status = request.GET.get("practice_status", "")
    sort = request.GET.get("sort", "newest")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(topic__icontains=query) | Q(description__icontains=query))
    if topic:
        qs = qs.filter(topic__icontains=topic)
    if qtype in Question.Type.values:
        qs = qs.filter(pk__in=Question.objects.filter(question_type=qtype, status=Question.Status.PUBLISHED).values("exercise_id"))
    if level in Exercise.Level.values:
        qs = qs.filter(level=level)
    completed = Attempt.objects.filter(user=request.user, exercise__skill=skill).values_list('exercise_id', flat=True)
    if status == "completed":
        qs = qs.filter(id__in=completed)
    elif status == "not_started":
        qs = qs.exclude(id__in=completed)
    # This version intentionally has no persisted draft, therefore no "In progress" filter.
    qs = qs.distinct().annotate(question_count=Count('questions', filter=Q(questions__status=Question.Status.PUBLISHED), distinct=True))
    format_filter = request.GET.get("format", "")
    if format_filter == "full": qs = qs.filter(question_count=40)
    elif format_filter == "short": qs = qs.exclude(question_count=40)
    else: format_filter = ""
    ordering = {"oldest": "created_at", "questions": "-question_count", "duration": "time_limit_minutes"}.get(sort, "-created_at")
    qs = qs.order_by(ordering, "-pk")
    page_obj = Paginator(qs, 9).get_page(request.GET.get("page"))
    ids = [ex.pk for ex in page_obj]
    attempts = Attempt.objects.filter(user=request.user, exercise_id__in=ids).order_by('exercise_id', '-submitted_at', '-id')
    latest = {}
    for attempt in attempts:
        latest.setdefault(attempt.exercise_id, attempt)
    cards = []
    for ex in page_obj:
        types = list(ex.questions.filter(status=Question.Status.PUBLISHED).values_list("question_type", flat=True).distinct())
        cards.append({"exercise": ex, "question_count": ex.question_count,
                      "types_display": ", ".join(TYPE_LABELS.get(t,t) for t in types),
                      "latest_attempt": latest.get(ex.pk), "art": "images/topics/" + topic_art(ex.title, ex.topic, ns) + ".svg",
                      "full": ex.question_count == 40, "exam_minutes": full_test_minutes(skill, ex.question_count, ex.time_limit_minutes)})
    return render(request, f"{ns}/exercise_list.html", {
        "active_nav": ns, "skill_label": skill.title(), "ns": ns,
        "detail_url_name": f"{ns}:exercise_detail", "list_url_name": f"{ns}:exercise_list",
        "format_filter": format_filter, "page_obj": page_obj, "exercises_data": cards, "total_count": page_obj.paginator.count,
        "query": query, "topic_filter": topic, "question_type": qtype, "level_filter": level,
        "sort_option": sort, "practice_status": status,
        "available_topics": list(base.exclude(topic="").order_by("topic").values_list("topic", flat=True).distinct()),
        "question_type_choices": Question.Type.choices, "level_choices": Exercise.Level.choices,
    })


def exercise_detail(request, skill, pk):
    ns = _skill(skill)
    exercise = get_object_or_404(Exercise, pk=pk, skill=skill, status=Exercise.Status.PUBLISHED)
    questions = list(exercise.questions.filter(status=Question.Status.PUBLISHED).prefetch_related('options').order_by('order_no','id'))
    if len(questions) == 40:
        # IELTS-style full sets use ordered parts; the existing passage/transcript fields hold all source material.
        starts = {i+1: f'Part {i//10+1} · Câu {i+1}–{i+10}' for i in range(0,40,10)} if ns == 'listening' else {}
        if ns == 'reading':
            # Explicit ranges in the authored text; never guess boundaries for other sets.
            for part,first,last in re.findall(r'(?im)^\s*passage\s+([123])[^\n]*?questions?\s+(\d+)\s*[-–—]\s*(\d+)', exercise.passage or ''):
                if 1 <= int(first) <= int(last) <= 40:
                    starts[int(first)] = f'Passage {part} · Câu {first}–{last}'
        for question in questions:
            question.section_heading = starts.get(question.order_no, '')
    passage_sections = []
    if ns == 'reading':
        text = exercise.passage or ''
        markers = list(re.finditer(r'(?im)^\s*passage\s+([123])[^\n]*?questions?\s+(\d+)\s*[-–—]\s*(\d+)[^\n]*$', text))
        if markers:
            preamble = text[:markers[0].start()].strip()
            for i, marker in enumerate(markers):
                body = text[marker.end():markers[i+1].start() if i+1 < len(markers) else len(text)].strip()
                lines = body.splitlines()
                title = lines[0].strip() if lines else ''
                rest = '\n'.join(lines[1:]).strip()
                passage_sections.append({'number': marker.group(1), 'first': int(marker.group(2)), 'last': int(marker.group(3)), 'title':title, 'body':rest, 'preamble':preamble if i == 0 else ''})
        else:
            passage_sections = [{'number': 1, 'first':questions[0].order_no if questions else 1, 'last':questions[-1].order_no if questions else 0, 'title':exercise.title, 'body':text}]
    mode = Attempt.Mode.EXAM if len(questions) == 40 else Attempt.Mode.PRACTICE
    minutes = full_test_minutes(skill, len(questions), exercise.time_limit_minutes)
    audio_available = ns != 'listening' or has_audio(exercise)
    key = _active_key(request.user, pk, mode)
    record = request.session.get(key)
    if record and mode == Attempt.Mode.EXAM and record.get('deadline'):
        # Expired sessions can start again only by an explicit fresh visit.
        if timezone.now() > timezone.datetime.fromisoformat(record['deadline']):
            record = None
    if not record:
        start = timezone.now()
        record = {"key": str(uuid.uuid4()), "start": start.isoformat(),
                  "deadline": (start + timedelta(minutes=minutes)).isoformat() if mode == Attempt.Mode.EXAM else ""}
        request.session[key] = record
    return render(request, f"{ns}/exercise_detail.html", {
        "active_nav": ns, "skill_label": skill.title(), "ns": ns,
        "list_url_name": f"{ns}:exercise_list", "submit_url_name": f"{ns}:exercise_submit",
        "exercise": exercise, "questions": questions, "total_questions": len(questions), "passage_sections": passage_sections,
        "submission_key": record['key'], "started_at": record['start'],
        "deadline": record.get('deadline',''), "mode": mode,
        "is_exam": mode == Attempt.Mode.EXAM, "full_test": len(questions)==40, "exam_minutes": minutes, "audio_available": audio_available,
    })


def submit(request, skill, pk):
    ns = _skill(skill)
    if request.method != 'POST':
        return HttpResponseBadRequest('Chỉ hỗ trợ POST.')
    exercise = get_object_or_404(Exercise, pk=pk, skill=skill, status=Exercise.Status.PUBLISHED)
    is_json = request.content_type == 'application/json'
    if is_json:
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'JSON không hợp lệ.'}, status=400)
        if not isinstance(payload, dict):
            return JsonResponse({'error': 'JSON không hợp lệ.'}, status=400)
        answers = payload.get('answers', {})
        if not isinstance(answers, dict) or any(not isinstance(v, str) for v in answers.values()):
            return JsonResponse({'error': 'Câu trả lời không hợp lệ.'}, status=400)
    else:
        payload = request.POST
        answers = {key[len('answer_'):]:value for key,value in payload.items() if key.startswith('answer_')}
    mode = _mode(payload.get('mode'))
    expected_mode = Attempt.Mode.EXAM if exercise.questions.filter(status=Question.Status.PUBLISHED).count() == 40 else Attempt.Mode.PRACTICE
    active_key = _active_key(request.user, pk, mode)
    active = request.session.get(active_key)
    submission_key = payload.get('submission_key')
    # Idempotent replay is permitted only when this UUID already belongs to this user/exercise.
    existing = None
    if submission_key:
        try:
            parsed_key = uuid.UUID(str(submission_key))
        except (TypeError, ValueError, AttributeError):
            return HttpResponseBadRequest('Mã nộp bài không hợp lệ.')
        existing = Attempt.objects.filter(submission_key=parsed_key).first()
        if existing and (existing.user_id != request.user.pk or existing.exercise_id != pk):
            return HttpResponseForbidden('Không được truy cập bài nộp của người khác.')
    if mode != expected_mode and not existing:
        return HttpResponseBadRequest('Chế độ làm bài không phù hợp. Hãy mở lại bài.')
    if not active and not existing:
        return HttpResponseBadRequest('Phiên làm bài không còn hợp lệ. Hãy mở lại bài luyện.')
    if active and not existing and active['key'] != str(submission_key):
        return HttpResponseBadRequest('Mã nộp bài không khớp phiên làm bài.')
    if active and not existing and mode == Attempt.Mode.EXAM and active.get('deadline'):
        deadline = timezone.datetime.fromisoformat(active['deadline'])
        if timezone.now() > deadline + timedelta(seconds=10):
            request.session.pop(active_key, None)
            return render(request, f'{ns}/error.html', {'error_message': 'Thời gian thi đã hết. Không thể chấm một bài nộp muộn. Hãy bắt đầu lượt mới.'}, status=400)
    if ns == 'listening' and not existing and not has_audio(exercise):
        return HttpResponseBadRequest('Bài nghe thiếu audio hợp lệ, chưa thể nộp bài.')
    try:
        start = timezone.datetime.fromisoformat(active['start']) if active else existing.started_at
        attempt, created = submit_receptive_exercise(
            user=request.user, exercise=exercise, answers_dict=answers,
            started_at=start, submission_key=submission_key, mode=mode)
    except (ValidationError, ValueError) as exc:
        if is_json or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': str(exc)}, status=400)
        return render(request, f'{ns}/error.html', {'error_message': str(exc)}, status=400)
    if created:
        request.session.pop(active_key, None)
        request.session.modified = True
    result_url = reverse(f'{ns}:attempt_result', kwargs={'submission_key':attempt.submission_key})
    if is_json or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success':True,'result_url':result_url,'created':created})
    return redirect(result_url)


def attempt_result(request, skill, submission_key):
    ns = _skill(skill)
    attempt = get_object_or_404(Attempt.objects.select_related('exercise'), submission_key=submission_key, exercise__skill=skill)
    if attempt.user_id != request.user.pk and not request.user.is_staff:
        return HttpResponseForbidden('Không được xem kết quả của người khác.')
    answers = attempt.answers.select_related('question').order_by('id')
    display = []
    stats = {}
    wrong = unanswered = 0
    for ans in answers:
        snapshot = ans.question_snapshot or {}
        user_answer = ans.user_answer.strip() if ans.user_answer else ''
        status = 'unanswered' if not user_answer else ('correct' if ans.is_correct else 'wrong')
        if status == 'unanswered': unanswered += 1
        elif status == 'wrong': wrong += 1
        qtype = snapshot.get('question_type', ans.question.question_type)
        aggregate = stats.setdefault(qtype, {'label':TYPE_LABELS.get(qtype,qtype),'count':0,'correct':0})
        aggregate['count'] += 1
        if ans.is_correct: aggregate['correct'] += 1
        correct_list = snapshot.get('correct_answers', [])
        option_map = {str(o.get('option_key','')).strip().casefold(): str(o.get('option_text','')).strip() for o in snapshot.get('options', []) if isinstance(o,dict)}
        def answer_label(value):
            value=str(value)
            label=option_map.get(value.strip().casefold(), '')
            return f'{value}. {label}' if label and label.casefold()!=value.strip().casefold() else value
        display.append({
            'row_id':ans.pk,
            'type_label': TYPE_LABELS.get(qtype,qtype),
            'order_no':snapshot.get('order_no', ans.question.order_no),
            'question_text':snapshot.get('question_text', ans.question.question_text),
            'user_answer':answer_label(user_answer) if user_answer else 'Chưa trả lời',
            'correct_answer':', '.join(answer_label(x) for x in correct_list),
            'explanation':snapshot.get('explanation', ''),
            'evidence_quote':snapshot.get('evidence_quote',''),
            'status':status,
        })
    display.sort(key=lambda x:x['order_no'])
    band = reference_band_40(attempt.correct_answers, skill) if attempt.total_questions == 40 and attempt.mode == Attempt.Mode.EXAM else None
    hist_page = Paginator(Attempt.objects.filter(user=attempt.user, exercise=attempt.exercise).order_by('-submitted_at','-id'), 10).get_page(request.GET.get('history_page'))
    hist = list(hist_page.object_list)
    for h in hist:
        h.display_band = reference_band_40(h.correct_answers, skill) if h.total_questions == 40 and h.mode == Attempt.Mode.EXAM else None
        h.display_score_10 = h.score_10 if h.score_10 is not None else round(h.correct_answers/max(1,h.total_questions)*10,1)
        h.display_elapsed = h.time_spent_seconds or max(0,int((h.submitted_at-h.started_at).total_seconds()))
    for item in stats.values():
        item['percent'] = round(item['correct']/item['count']*100,1) if item['count'] else 0
    return render(request, f'{ns}/attempt_result.html', {
        'active_nav':ns, 'skill_label':skill.title(), 'ns':ns,
        'list_url_name': f'{ns}:exercise_list', 'detail_url_name':f'{ns}:exercise_detail',
        'attempt':attempt,'exercise':attempt.exercise,
        'correct_count':attempt.correct_answers,'total_count':attempt.total_questions,
        'wrong_count':wrong,'unanswered_count':unanswered,
        'percentage':round(attempt.correct_answers/max(1,attempt.total_questions)*100,1),
        'score_10':attempt.score_10 if attempt.score_10 is not None else round(attempt.correct_answers/max(1,attempt.total_questions)*10,1),
        'duration':attempt.time_spent_seconds or max(0,int((attempt.submitted_at-attempt.started_at).total_seconds())),
        'answers_display': display, 'type_stats':list(stats.values()), 'history':hist, 'history_page':hist_page,
        'band_reference': list(band_ranges(skill)), 'display_band': band, 'is_full_test': attempt.total_questions == 40,
        'gauge_percent': round(float(band)*100/9,1) if band is not None else round(attempt.correct_answers/max(1,attempt.total_questions)*100,1),
        'snapshot': attempt.exercise_snapshot or {},
        'audio_replay': ns == 'listening' and attempt.exercise.status == Exercise.Status.PUBLISHED and has_audio(attempt.exercise) and (attempt.exercise_snapshot or {}).get('audio_file') == attempt.exercise.audio_file.url,
        'transcript':(attempt.exercise_snapshot or {}).get('transcript',''),
    })
