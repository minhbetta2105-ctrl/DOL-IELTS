"""Regression coverage for new UI, content protection and business-admin roles."""
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.permissions import HOC_VIEN_GROUP
from receptive.templatetags.receptive_tags import option_label
from receptive.models import Exercise
from speaking.models import SpeakingExercise, SpeakingSupport, SpeakingSubmission


class UnifiedRegressionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user(username='unified_student', password='pass123XYZ!')
        self.teacher = User.objects.create_user(username='unified_teacher', password='pass123XYZ!', is_staff=True)
        group, _ = Group.objects.get_or_create(name=HOC_VIEN_GROUP)
        self.student.groups.add(group)
        for app, code in [('auth','view_user'),('speaking','view_speakingexercise')]:
            self.teacher.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        self.admin = User.objects.create_superuser('unified_admin', 'admin@site.test', 'pass123XYZ!')

    def test_teacher_can_view_accounts_but_cannot_lock_or_grant(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse('accounts:manage_users')).status_code, 200)
        self.assertEqual(self.client.post(reverse('accounts:toggle_active', kwargs={'user_id':self.student.pk})).status_code,403)
        self.assertEqual(self.client.post(reverse('accounts:set_student', kwargs={'user_id':self.student.pk}),{'action':'revoke'}).status_code,403)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        self.assertTrue(self.student.groups.filter(name=HOC_VIEN_GROUP).exists())

    def test_teacher_uses_management_not_technical_admin(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse('management:dashboard')).status_code,200)
        self.assertNotEqual(self.client.get(reverse('admin:index')).status_code,200)

    def test_superuser_can_manage_accounts(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code,200)
        result=self.client.post(reverse('accounts:toggle_active',kwargs={'user_id':self.student.pk}))
        self.assertEqual(result.status_code,302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

    def test_speaking_published_status_change_keeps_existing_history(self):
        exercise=SpeakingExercise.objects.create(title='Existing task',part='PART_2',topic='Life',prompt_text='Describe a task.',level='INTERMEDIATE',status='PUBLISHED')
        SpeakingSubmission.objects.create(user=self.student,exercise=exercise,audio_file='test.webm',exercise_snapshot={'title':'Existing task'},status='GRADING')
        exercise.title='Changed title'
        with self.assertRaises(ValidationError):exercise.full_clean()
        exercise.refresh_from_db()
        exercise.status='HIDDEN'
        exercise.full_clean()
        exercise.save(update_fields=['status'])
        self.assertEqual(SpeakingSubmission.objects.filter(exercise=exercise).count(),1)

    def test_true_false_options_only_show_label_once(self):
        self.assertEqual(option_label(SimpleNamespace(option_key='True',option_text='True')),'True')
        self.assertEqual(option_label(SimpleNamespace(option_key='FALSE',option_text='False')),'False')
        self.assertEqual(option_label(SimpleNamespace(option_key='A',option_text='Because of volcanic ash')),'A. Because of volcanic ash')

    def test_reading_filter_combines_topic_keyword_and_level(self):
        Exercise.objects.create(skill='READING',title='A museum visit',description='Culture',topic='Arts',level='BEGINNER',passage='Paragraph',status='PUBLISHED')
        Exercise.objects.create(skill='READING',title='A museum visit',description='Culture',topic='Science',level='BEGINNER',passage='Paragraph',status='PUBLISHED')
        self.client.force_login(self.student)
        response=self.client.get(reverse('reading:exercise_list'),{'q':'museum','topic':'Arts','level':'BEGINNER'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total_count'],1)
        self.assertContains(response,'topic-options')

    def test_listening_filter_topic_and_question_type_without_hidden(self):
        Exercise.objects.create(skill='LISTENING',title='Transport interview',topic='Transport',level='INTERMEDIATE',audio_file='listening/test.mp3',status='PUBLISHED')
        Exercise.objects.create(skill='LISTENING',title='Transport interview',topic='Transport',level='INTERMEDIATE',audio_file='listening/test.mp3',status='HIDDEN')
        self.client.force_login(self.student)
        response=self.client.get(reverse('listening:exercise_list'),{'topic':'Transport'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total_count'],1)

    def test_teacher_permission_setup_is_whitelisted(self):
        sink = StringIO()
        call_command('grant_teacher_permissions', self.teacher.username, stdout=sink)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.has_perm('speaking.add_speakingexercise'))
        self.assertTrue(self.teacher.has_perm('writing.change_writingprompt'))
        self.assertTrue(self.teacher.has_perm('auth.view_user'))
        self.assertFalse(self.teacher.has_perm('auth.change_user'))
        self.assertFalse(self.teacher.has_perm('auth.add_group'))
        self.assertEqual(self.client.force_login(self.teacher), None)
        self.assertEqual(self.client.get(reverse('management:student_progress_list')).status_code, 200)
        self.assertEqual(self.client.post(reverse('accounts:toggle_active', kwargs={'user_id':self.student.pk})).status_code, 403)

    def test_listening_player_and_questions_use_shared_two_pane_layout(self):
        # A missing audio file must not expose a broken player; a real local
        # audio file should enable both the player and HTTP byte-range serving.
        self.assertEqual(self.client.force_login(self.student), None)
        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            exercise = Exercise.objects.create(
                skill='LISTENING', title='Player control sample', topic='Education',
                level='BEGINNER', audio_file='listening/test.mp3', status='PUBLISHED')
            detail_url = reverse('listening:exercise_detail', kwargs={'pk': exercise.pk})
            missing = self.client.get(detail_url)
            self.assertEqual(missing.status_code, 200)
            self.assertContains(missing, 'rt-listening-split')
            self.assertContains(missing, 'data-audio-available="0"')
            self.assertNotContains(missing, 'id="rt-audio"')
            self.assertContains(missing, 'id="rt-pane-questions"')

            audio_file = Path(media_dir) / 'listening' / 'test.mp3'
            audio_file.parent.mkdir(parents=True, exist_ok=True)
            audio_file.write_bytes(b'ID3' + b'\x00' * 1024)
            available = self.client.get(detail_url)
            self.assertEqual(available.status_code, 200)
            self.assertContains(available, 'data-audio-available="1"')
            self.assertContains(available, 'id="rt-audio"')
            self.assertContains(available, 'id="rt-pane-questions"')

            audio_url = reverse('listening:exercise_audio', kwargs={'pk': exercise.pk})
            stream = self.client.get(audio_url)
            self.assertEqual(stream.status_code, 200)
            self.assertEqual(stream['Content-Type'], 'audio/mpeg')
            stream.close()
            partial = self.client.get(audio_url, HTTP_RANGE='bytes=0-3')
            self.assertEqual(partial.status_code, 206)
            self.assertTrue(partial['Content-Range'].startswith('bytes 0-3/'))
            self.assertEqual(b''.join(partial.streaming_content), b'ID3\x00')
            partial.close()

    def test_speaking_support_remains_one_to_one_after_edit(self):
        # The project does not ship that seed command. Verify the real
        # support-record update invariant instead of invoking removed tooling.
        exercise = SpeakingExercise.objects.create(
            title='Support exercise', part='PART_1', topic='Education',
            prompt_text='Describe your school.', level='BEGINNER', status='PUBLISHED')
        support = SpeakingSupport.objects.create(
            exercise=exercise, idea_hint='Name your school.', sample_answer='My school is near my home.')
        updated, created = SpeakingSupport.objects.update_or_create(
            exercise=exercise, defaults={'idea_hint':'Explain what you study.'})
        self.assertFalse(created)
        self.assertEqual(updated.pk, support.pk)
        self.assertEqual(updated.sample_answer, 'My school is near my home.')
        self.assertEqual(SpeakingSupport.objects.filter(exercise=exercise).count(), 1)

    def test_speaking_result_uses_real_scores_radar_and_saved_feedback(self):
        exercise=SpeakingExercise.objects.create(title='My topic',part='PART_1',topic='Life',prompt_text='Tell me.',level='BEGINNER',status='PUBLISHED')
        sub=SpeakingSubmission.objects.create(user=self.student,exercise=exercise,
              exercise_snapshot={'title':'My topic','part':'PART_1','level':'BEGINNER','topic':'Life','prompt_text':'Tell me.'},
              audio_file='test.webm',overall_score=Decimal('6.5'),fluency_score=Decimal('6.5'),
              vocabulary_score=Decimal('6.0'),grammar_score=Decimal('6.5'),
              pronunciation_score=Decimal('6.5'),status='GRADED',feedback='{"transcript":"Hello world."}')
        self.client.force_login(self.student)
        response=self.client.get(reverse('speaking:submission_result',kwargs={'submission_key':sub.submission_key}))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'class="pd-radar"')
        self.assertContains(response,'class="pd-radar-shape"')
        self.assertContains(response,'Fluency and Coherence')
        self.assertContains(response,'Hello world.')
