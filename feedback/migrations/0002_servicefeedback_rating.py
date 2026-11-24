from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("feedback", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="servicefeedback", name="rating",
            field=models.PositiveSmallIntegerField(null=True, blank=True,
                validators=[MinValueValidator(1), MaxValueValidator(5)]),
        ),
        migrations.AddConstraint(
            model_name="servicefeedback",
            constraint=models.CheckConstraint(
                check=models.Q(rating__isnull=True) | models.Q(rating__gte=1, rating__lte=5),
                name="feedback_rating_1_to_5",
            ),
        ),
    ]
