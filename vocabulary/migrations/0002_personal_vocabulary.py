# Additive migration: 1 personal vocabulary table, preserve all existing attempt history.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vocabulary", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="attempt", name="topic",
            field=models.ForeignKey(to="vocabulary.topic", related_name="attempts",
                                    on_delete=django.db.models.deletion.PROTECT, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="attempt", name="exercise_type",
            field=models.CharField(max_length=20, choices=[("MCQ", "Trắc nghiệm (Multiple Choice)"),
                  ("MATCH", "Nối từ"), ("DRAG", "Kéo & Thả"), ("TYPE", "Gõ lại từ")]),
        ),
        migrations.AlterField(
            model_name="answer", name="question_type",
            field=models.CharField(max_length=20, choices=[("MCQ_MEANING", "Trắc nghiệm - chọn nghĩa"),
                  ("MCQ_WORD", "Trắc nghiệm - điền từ"), ("MATCH", "Nối từ"),
                  ("DRAG", "Kéo & Thả"), ("TYPE", "Gõ lại từ")]),
        ),
        migrations.CreateModel(
            name="UserWord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(max_length=10, choices=[("SAVED", "Đã lưu"),
                    ("LEARNED", "Đã học")], default="SAVED")),
                ("saved_at", models.DateTimeField(auto_now_add=True)),
                ("learned_at", models.DateTimeField(null=True, blank=True)),
                ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE, related_name="saved_vocabulary")),
                ("word", models.ForeignKey(to="vocabulary.word", on_delete=django.db.models.deletion.CASCADE, related_name="saved_by")),
            ],
            options={"db_table": "vocabulary_user_word", "ordering": ["-saved_at"]},
        ),
        migrations.AddConstraint(
            model_name="userword", constraint=models.UniqueConstraint(
                fields=("user", "word"), name="vocab_user_word_unique"),
        ),
    ]
