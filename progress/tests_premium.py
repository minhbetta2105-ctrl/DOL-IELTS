"""Regression checks for premium Progress presentation and real-data summaries."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.permissions import HOC_VIEN_GROUP
from vocabulary.models import Topic, Word, Attempt, Answer, UserWord
from . import services


class PremiumDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username='premium_student',password='qaPass123')
        group, _ = Group.objects.get_or_create(name=HOC_VIEN_GROUP)
        cls.student.groups.add(group)
        cls.topic = Topic.objects.create(name='Travel',status='PUBLISHED')
        cls.word = Word.objects.create(topic=cls.topic,word='journey',meaning_vi='hành trình',status='PUBLISHED')

    def setUp(self):
        self.client.force_login(self.student)

    def test_empty_dashboard_has_contextual_start_and_no_fake_chart(self):
        result = self.client.get(reverse('progress:dashboard'))
        self.assertEqual(result.status_code,200)
        self.assertContains(result,'Hành trình IELTS của bạn')
        self.assertContains(result,'Hành trình IELTS bắt đầu từ đây!')
        self.assertContains(result,'Overall hiện tại: Chưa đủ dữ liệu')
        self.assertContains(result,'Chưa có bài đủ điều kiện tính Band.')
        self.assertEqual(result.context['band_summary']['count'], 0)
        self.assertEqual(result.context['mini_chart']['count'],0)
        self.assertEqual(len(result.context['streak']['week_calendar']),7)
        self.assertFalse(result.context['streak']['studied_today'])

    def test_one_vocab_submission_drives_kpi_streak_and_preview(self):
        now = timezone.now()
        att = Attempt.objects.create(user=self.student,topic=self.topic,
            exercise_type='MCQ',topic_snapshot={'name':'Travel'},
            total_questions=1,correct_answers=1,started_at=now,submitted_at=now)
        Answer.objects.create(attempt=att,word=self.word,question_type='MCQ_MEANING',
            question_snapshot={'prompt':'journey','answer':'hành trình'},user_answer='hành trình',is_correct=True,order_no=1)
        UserWord.objects.create(user=self.student,word=self.word,status='LEARNED')
        res = self.client.get(reverse('progress:dashboard'))
        self.assertEqual(res.context['total_attempts'],1)
        self.assertEqual(res.context['ielts_skills'],0)
        self.assertEqual(res.context['practiced_words'],1)
        self.assertEqual(res.context['marked_learned'],1)
        self.assertEqual(res.context['streak']['current'],1)
        self.assertEqual(res.context['mini_chart']['skill'],'VOCABULARY')
        self.assertEqual(res.context['mini_chart']['count'],1)
        self.assertContains(res,'Hôm nay bạn đã hoàn thành rồi!')
        self.assertContains(res,'Chưa có bài đủ điều kiện tính Band.')
        self.assertEqual(res.context['band_summary']['count'], 0)
        self.assertContains(res,'Travel')

    def test_week_calendar_never_marks_future_days_as_completed(self):
        details = services.streak_info(self.student)
        today = timezone.localdate(timezone.now(),timezone=services.TZ)
        self.assertEqual(details['week_calendar'][0]['date'].weekday(),0)
        self.assertEqual(details['week_calendar'][-1]['date'].weekday(),6)
        for d in details['week_calendar']:
            self.assertEqual(d['future'],d['date']>today)
            if d['future']:
                self.assertFalse(d['active'])
