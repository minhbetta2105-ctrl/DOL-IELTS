"""Learning views for listening: thin wrappers around shared receptive MVT logic."""
from core.decorators import hoc_vien_required
from receptive import skill_views
from receptive.models import Exercise
SKILL = Exercise.Skill.LISTENING

@hoc_vien_required
def exercise_list(request):
    return skill_views.list_exercises(request, SKILL)

@hoc_vien_required
def exercise_detail(request, pk):
    return skill_views.exercise_detail(request, SKILL, pk)

@hoc_vien_required
def exercise_submit(request, pk):
    return skill_views.submit(request, SKILL, pk)

@hoc_vien_required
def attempt_result(request, submission_key):
    return skill_views.attempt_result(request, SKILL, submission_key)
