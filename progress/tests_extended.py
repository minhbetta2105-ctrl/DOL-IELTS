"""Progress aggregation from Vocabulary, skill scores and read-only teacher access."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.permissions import HOC_VIEN_GROUP
from vocabulary.models import Topic, Word, Attempt, Answer
from . import services


class VocabularyProgressIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username="only_vocab", password="pw")
        group = Group.objects.create(name=HOC_VIEN_GROUP)
        cls.student.groups.add(group)
        cls.teacher = get_user_model().objects.create_user(username="teacher_prg",password="pw",is_staff=True)
        cls.teacher.user_permissions.add(Permission.objects.get(codename="view_user",content_type__app_label="auth"))
        cls.topic = Topic.objects.create(name="Technology",status="PUBLISHED")
        cls.word = Word.objects.create(topic=cls.topic,word="learn",meaning_vi="học",status="PUBLISHED")

    def setUp(self):
        self.client.force_login(self.student)

    def _attempt(self,submitted_at):
        return Attempt.objects.create(user=self.student, topic=self.topic,
            exercise_type="MCQ",topic_snapshot={"name":"Technology"},
            total_questions=1,correct_answers=1,started_at=submitted_at,submitted_at=submitted_at)

    def test_only_vocabulary_dashboard_streak_and_sections(self):
        attempt=self._attempt(timezone.now())
        Answer.objects.create(attempt=attempt,word=self.word,question_type="MCQ_MEANING",
            question_snapshot={"prompt":"learn","answer":"học"},user_answer="học",is_correct=True,order_no=1)
        response=self.client.get(reverse("progress:dashboard"))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context["total_attempts"],1)
        self.assertEqual(response.context["ielts_skills"],0)
        self.assertEqual(response.context["practiced_words"],1)
        self.assertEqual(response.context["streak"]["current"],1)
        for section in ("skills","chart","history"):
            self.assertEqual(self.client.get(reverse("progress:section",args=[section])).status_code,200)
        chart=self.client.get(reverse("progress:section",args=["chart"]),{"skill":"VOCABULARY"})
        self.assertContains(chart,"100")
        history=self.client.get(reverse("progress:section",args=["history"]),{"skill":"VOCABULARY"})
        self.assertContains(history,"Technology")

    def test_streak_multi_attempts_same_day_and_previous_day(self):
        now = timezone.now()
        first = self._attempt(now)
        second = self._attempt(now - timedelta(hours=1))
        info = services.streak_info(self.student)
        self.assertEqual(info["current"], 1)
        self.assertEqual(info["longest"], 1)
        third = self._attempt(now - timedelta(days=1))
        info = services.streak_info(self.student)
        self.assertEqual(info["current"], 2)
        self.assertEqual(info["longest"], 2)

    def test_wrong_answer_does_not_count_as_mastered(self):
        attempt = self._attempt(timezone.now())
        Answer.objects.create(attempt=attempt, word=self.word, question_type="MCQ_MEANING",
            question_snapshot={"prompt":"learn","answer":"học"},user_answer="sai",is_correct=False,order_no=1)
        dashboard = services.dashboard_data(self.student)
        self.assertEqual(dashboard["practiced_words"], 1)
        self.assertEqual(dashboard["correct_words"], 0)

    def test_teacher_progress_is_read_only_and_student_scoped(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("management:student_progress_list")).status_code,200)
        detail=self.client.get(reverse("management:student_progress_detail",args=[self.student.pk]))
        self.assertEqual(detail.status_code,200)
        self.assertContains(detail,"Chỉ xem")
        self.assertEqual(self.client.get(reverse("management:student_progress_section",args=[self.student.pk,"history"])).status_code,200)
        self.assertEqual(self.client.get(reverse("management:student_progress_section",args=[999999,"history"])).status_code,404)
