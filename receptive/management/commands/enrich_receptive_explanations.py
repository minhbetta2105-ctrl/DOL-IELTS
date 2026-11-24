"""Fill only verifiable transcripts/evidence from the project's OWN audio-generation script.

Idempotent, no generated claims; existing teacher-entered fields are never overwritten.
"""
import re
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from receptive.models import Exercise, Question


class Command(BaseCommand):
    help = 'Populate missing Listening transcripts from generate_audio.ps1 and verified evidence quotes.'

    def handle(self, *args, **kwargs):
        source = Path(settings.BASE_DIR) / 'generate_audio.ps1'
        transcripts = {}
        if source.is_file():
            raw = source.read_text(encoding='utf-8-sig')
            for match in re.finditer(r'\$script(\d+)\s*=\s*@"\s*(.*?)\s*"@', raw, re.S):
                transcripts[int(match.group(1))] = match.group(2).strip()
        updated_scripts = 0
        for exercise in Exercise.objects.filter(skill=Exercise.Skill.LISTENING, transcript=''):
            stem = exercise.audio_file.name.rsplit('/', 1)[-1] if exercise.audio_file else ''
            match = re.fullmatch(r'audio_exercise_(\d+)\.wav', stem)
            if match and int(match.group(1)) in transcripts:
                exercise.transcript = transcripts[int(match.group(1))]
                exercise.save(update_fields=['transcript'])
                updated_scripts += 1
        updated_quotes = 0
        for q in Question.objects.select_related('exercise').filter(evidence_quote=''):
            source_text = q.exercise.passage if q.exercise.skill == 'READING' else q.exercise.transcript
            if not source_text or not q.explanation:
                continue
            for text in re.findall(r"['\"“](.{8,250}?)['\"”]", q.explanation):
                # Evidence must be a true substring of the passage/transcript.
                candidate = text.strip()
                if candidate and candidate.casefold() in source_text.casefold():
                    q.evidence_quote = candidate
                    q.save(update_fields=['evidence_quote'])
                    updated_quotes += 1
                    break
        self.stdout.write(self.style.SUCCESS(
            f'Transcripts verified from original script: {updated_scripts}; evidence quotes matched: {updated_quotes}.'))
