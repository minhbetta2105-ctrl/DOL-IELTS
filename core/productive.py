"""Shared presentation adapters for Writing and Speaking. No model changes."""
import re
from decimal import Decimal, InvalidOperation

SPEAKING_CRITERIA = (
    ('fluency_coherence', 'FC', 'Fluency and Coherence', 'Độ trôi chảy và mạch lạc', 'fluency_score'),
    ('lexical_resource', 'LR', 'Lexical Resource', 'Vốn từ vựng', 'vocabulary_score'),
    ('grammar', 'GRA', 'Grammatical Range and Accuracy', 'Ngữ pháp', 'grammar_score'),
    ('pronunciation', 'PR', 'Pronunciation', 'Phát âm', 'pronunciation_score'),
)


def text(value):
    return value.strip() if isinstance(value, str) else ''


def items(value):
    return value if isinstance(value, list) else ([value] if isinstance(value, str) and value.strip() else [])


def strings(value):
    return [text(v) for v in items(value) if text(v)]


def valid_band(value):
    try:
        d = Decimal(str(value))
        if d.is_finite() and 0 <= d <= 9 and d * 2 == (d * 2).to_integral_value():
            return d.quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def compact(value):
    return ' '.join(re.findall(r"\w+", text(value).casefold()))


def grounded(quote, transcript):
    q = compact(quote)
    return bool(q and f' {q} ' in f' {compact(transcript)} ')


def error_rows(value, transcript=None, pronunciation=False):
    rows = []
    for entry in items(value):
        if isinstance(entry, str):
            if entry.strip(): rows.append({'issue': entry.strip()})
            continue
        if not isinstance(entry, dict): continue
        original = text(entry.get('original') or entry.get('word'))
        issue = text(entry.get('issue') or entry.get('explanation'))
        correction = text(entry.get('correction') or entry.get('suggestion') or entry.get('tip') or entry.get('guidance') or entry.get('correct_pronunciation') or entry.get('pronunciation_tip') or entry.get('correct_form') or entry.get('advice') or entry.get('recommendation'))
        # Missing old guidance remains explicitly unavailable, never fabricated.
        if transcript is not None and original and not grounded(original, transcript): continue
        if original or issue or correction:
            rows.append({'original': original, 'issue': issue, 'correction': correction, 'ipa': text(entry.get('ipa')), 'timestamp': text(entry.get('timestamp')), 'pronunciation': pronunciation})
    return rows


def evidence_rows(value, transcript=None):
    rows = []
    for entry in items(value):
        quote = text(entry if isinstance(entry, str) else entry.get('quote') if isinstance(entry, dict) else '')
        if not quote or (transcript is not None and not grounded(quote, transcript)): continue
        rows.append({'quote': quote, 'note': text(entry.get('note')) if isinstance(entry, dict) else '', 'timestamp': text(entry.get('timestamp')) if isinstance(entry, dict) else ''})
    return rows


def build_report(skill, submission, snapshot, assessment):
    data = assessment if isinstance(assessment, dict) else {}
    raw = data.get('criteria') if isinstance(data.get('criteria'), dict) else {}
    speaking = skill == 'speaking'
    transcript = text(data.get('transcript'))
    if speaking:
        definitions = SPEAKING_CRITERIA
        overall = valid_band(submission.overall_score)
    else:
        task1 = snapshot.get('task_type') == 'TASK_1'
        definitions = (
            ('task_achievement_or_response', 'TA' if task1 else 'TR', 'Task Achievement' if task1 else 'Task Response', 'Mức độ đáp ứng đề bài', None),
            ('coherence_cohesion', 'CC', 'Coherence and Cohesion', 'Mạch lạc và liên kết', None),
            ('lexical_resource', 'LR', 'Lexical Resource', 'Vốn từ vựng', None),
            ('grammar', 'GRA', 'Grammatical Range and Accuracy', 'Ngữ pháp', None),
        )
        overall = valid_band(submission.score)
    criteria = []
    for i, (key, short, name, label, field) in enumerate(definitions):
        crit = raw.get(key, {})
        if not isinstance(crit, dict): crit = {}
        band = valid_band(getattr(submission, field) if field else crit.get('band'))
        errors = error_rows(crit.get('errors'), transcript if speaking else None, key == 'pronunciation')
        if speaking and not errors:
            legacy = {'lexical_resource':'vocabulary_suggestions','grammar':'grammar_corrections','pronunciation':'pronunciation_feedback'}.get(key)
            if legacy: errors = error_rows(data.get(legacy), transcript or None, key == 'pronunciation')
        criteria.append({'key': key, 'short':short, 'name':name, 'label':label, 'band':band, 'percent':float(band)/9*100 if band is not None else 0,
                         'reason':text(crit.get('reason')), 'evidence':evidence_rows(crit.get('evidence'), transcript if speaking else None),
                         'errors': errors, 'improvements':strings(crit.get('improvements')), 'next_band':text(crit.get('next_band'))})
    points = []
    for i, c in enumerate(criteria):
        if c['band'] is None: break
        radius = float(c['band']) / 9 * 88
        x,y = [(120,120-radius),(120+radius,120),(120,120+radius),(120-radius,120)][i]
        c.update(x=round(x,2),y=round(y,2))
        points.append(f'{x:.2f},{y:.2f}')
    return {'overall':overall,'percent':float(overall)/9*100 if overall is not None else 0,
            'criteria':criteria,'radar':' '.join(points) if len(points)==4 else '',
            'summary':text(data.get('overall_feedback')) or (text(submission.feedback) if not data and not text(submission.feedback).startswith(('{','[')) else ''), 'priority':strings(data.get('priority_improvements') or data.get('improvement_suggestions')),
            'strengths':strings(data.get('strengths')), 'weaknesses':strings(data.get('weaknesses')),
            'transcript':transcript, 'has_detail':bool(raw), 'audio_quality':text(data.get('audio_quality'))}


def topic_art(title, topic='', kind=''):
    value = f'{title} {topic}'.casefold()
    if kind in ('reading', 'listening'):
        # More meaningful illustrations for receptive catalogues; retain the old productive mapping.
        for key, words in [('travel', ('bicycle','transport','planning','urban')), ('food', ('coffee','food','agriculture','bean')), ('nature', ('marine','coral','ecology','environment','sustainable')), ('technology', ('energy','lithium','technology','digital')), ('science', ('psychology','linguistic','research','science')), ('heritage', ('roman','archaeolog','architecture','concrete')), ('education', ('university','library','campus','academic','student')), ('daily', ('sports','leisure','housing','life'))]:
            if any(word in value for word in words): return key
        return 'reading' if kind == 'reading' else 'listening'
    for key, words in [('technology', ('technology','electronic','digital','computer','e-book')), ('education',('education','studies','learn','school','book')), ('travel',('travel','journey','transport','city','cities','town')), ('nature',('environment','nature','climate')), ('people',('people','family','someone','friend')), ('daily',('routine','daily','weekend','life'))]:
        if any(word in value for word in words): return key
    return 'speaking' if kind == 'speaking' else 'writing'


def build_cards(objects, skill):
    from django.urls import reverse
    cards=[]
    for obj in objects:
        speaking=skill=='speaking'
        cards.append({'title':obj.title,'kind':obj.get_part_display() if speaking else obj.get_task_type_display(),
                      'topic':obj.topic if speaking else '', 'level':obj.get_level_display(), 'snippet':obj.prompt_text,
                      'image': '' if speaking else obj.image_file, 'art':'images/topics/'+topic_art(obj.title,obj.topic if speaking else '',skill)+'.svg',
                      'done':obj.is_done, 'url':reverse('speaking:exercise_detail' if speaking else 'writing:prompt_detail',args=[obj.pk]),
                      'hint':'Luyện nói' if speaking else ('150+ từ' if obj.task_type=='TASK_1' else '250+ từ')})
    return cards
