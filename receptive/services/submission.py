"""
Submission Service dùng chung cho cả Reading và Listening theo UC-REA-03 và UC-LIS-03.
Thực hiện lưu Attempt và Answer trong một Atomic Transaction kèm Snapshot dữ liệu.
Hỗ trợ Idempotent qua submission_key (UUID v4) chống tạo lượt trùng khi gửi lặp.
"""

import uuid
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from receptive.services.scoring import band_for_result, full_test_minutes
from receptive.models import Attempt, Answer, Exercise
from receptive.services.grading import grade_exercise_submission


def build_exercise_snapshot(exercise: Exercise) -> dict:
    """Tạo bản chụp JSON của Exercise tại thời điểm nộp bài."""
    return {
        "id": exercise.id,
        "title": exercise.title,
        "description": exercise.description,
        "topic": exercise.topic,
        "level": exercise.level,
        "skill": exercise.skill,
        "passage": exercise.passage,
        "transcript": exercise.transcript,
        "time_limit_minutes": exercise.time_limit_minutes,
        "audio_file": exercise.audio_file.url if exercise.audio_file else None,
    }


def build_question_snapshot(question) -> dict:
    """Tạo bản chụp JSON của Question và các Option đi kèm."""
    options_data = [
        {
            "id": opt.id,
            "option_key": opt.option_key,
            "option_text": opt.option_text,
            "order_no": opt.order_no,
        }
        for opt in question.options.all().order_by("order_no", "id")
    ]

    return {
        "id": question.id,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "correct_answers": question.correct_answers,
        "explanation": question.explanation,
        "evidence_quote": question.evidence_quote,
        "order_no": question.order_no,
        "options": options_data,
    }


def submit_receptive_exercise(
    user,
    exercise: Exercise,
    answers_dict: dict,
    started_at=None,
    submission_key=None,
    mode="PRACTICE",
) -> tuple[Attempt, bool]:
    """Nộp bài và chấm điểm một Exercise.
    
    Args:
        user: User Django đang nộp bài
        exercise: Đối tượng Exercise
        answers_dict: dict mapping str(question_id) -> user_answer
        started_at: datetime thời điểm bắt đầu làm bài (nếu None sẽ lấy submitted_at)
        submission_key: UUIDv4 hoặc chuỗi UUID để chống gửi lặp. Nếu None sẽ tự sinh.

    Returns:
        (attempt, created): tuple đối tượng Attempt và boolean created.
    """
    if exercise.status != Exercise.Status.PUBLISHED:
        raise ValidationError("Bài luyện này hiện đang bị ẩn hoặc không còn khả dụng.")

    # Kiểm tra submission_key chống nộp lặp (Idempotency)
    if submission_key:
        existing_attempt = Attempt.objects.filter(submission_key=submission_key).first()
        if existing_attempt:
            # Submission UUID is not an authorization token: never expose another user's attempt.
            if existing_attempt.user_id != user.pk or existing_attempt.exercise_id != exercise.pk:
                raise ValidationError("Mã nộp bài không hợp lệ.")
            return existing_attempt, False

    submitted_at = timezone.now()
    if not started_at or started_at > submitted_at:
        started_at = submitted_at

    # Chấm điểm bài làm
    grade_data = grade_exercise_submission(exercise, answers_dict)
    total_questions = grade_data["total_questions"]
    correct_count = grade_data["correct_count"]
    results = grade_data["results"]

    if total_questions < 1:
        raise ValidationError("Bài luyện chưa có câu hỏi nào được công bố để làm bài.")

    if mode not in ("PRACTICE", "EXAM"):
        raise ValidationError("Chế độ làm bài không hợp lệ.")
    elapsed = max(0, int((submitted_at - started_at).total_seconds()))
    score_10 = round((correct_count / total_questions) * 10, 1)
    # IELTS itself uses 40 scored questions, and thresholds differ across test versions.
    band_score = band_for_result(correct_count, total_questions, exercise.skill, mode)
    # A concurrent double-click may race the early duplicate-key check.
    # A database UNIQUE constraint remains authoritative, not only a disabled button.
    try:
        with transaction.atomic():
            attempt = Attempt.objects.create(
                submission_key=submission_key or uuid.uuid4(),
                user=user,
                exercise=exercise,
                exercise_snapshot={**build_exercise_snapshot(exercise), "mode": mode, "time_limit_minutes": full_test_minutes(exercise.skill,total_questions,exercise.time_limit_minutes)},
                total_questions=total_questions,
                correct_answers=correct_count,
                started_at=started_at,
                mode=mode,
                time_spent_seconds=elapsed,
                score_10=score_10,
                band_score=band_score,
                submitted_at=submitted_at,
            )
    
            answer_objs = []
            for q_id, res in results.items():
                question = res["question"]
                answer_objs.append(
                    Answer(
                        attempt=attempt,
                        question=question,
                        question_snapshot=build_question_snapshot(question),
                        user_answer=res["user_answer"],
                        is_correct=res["is_correct"],
                    )
                )
    
            Answer.objects.bulk_create(answer_objs)
    except IntegrityError:
        if submission_key:
            same = Attempt.objects.filter(submission_key=submission_key).first()
            if same and same.user_id == user.pk and same.exercise_id == exercise.pk:
                return same, False
        raise

    return attempt, True
