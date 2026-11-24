"""Local media byte streaming for the existing Listening FileField."""
import mimetypes
import re
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe
from accounts.permissions import is_hoc_vien, is_quan_tri
from receptive.models import Exercise

def audio_path(exercise):
    try:
        if not exercise.audio_file: return None
        root=(Path(settings.MEDIA_ROOT)/'listening').resolve()
        path=Path(exercise.audio_file.path).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size<=0: return None
        return path
    except (OSError, ValueError, NotImplementedError): return None

def has_audio(exercise): return audio_path(exercise) is not None

@require_safe
def exercise_audio(request, pk):
    if not (is_hoc_vien(request.user) or is_quan_tri(request.user)):
        return HttpResponse(status=403)
    exercise=get_object_or_404(Exercise, pk=pk,skill='LISTENING',status='PUBLISHED')
    path=audio_path(exercise)
    if path is None: raise Http404('Audio unavailable')
    size=path.stat().st_size
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if path.suffix.lower()=='.wav': mime='audio/wav'
    raw=request.headers.get('Range','')
    start,end=0,size-1
    if raw:
        m=re.fullmatch(r'bytes=(\d*)-(\d*)',raw)
        if m and (m[1] or m[2]):
            if m[1]: start=int(m[1]); end=min(int(m[2]),size-1) if m[2] else size-1
            else: start=max(0,size-int(m[2]))
        else: start=size
        if start>=size or end<start or start<0:
            response=HttpResponse(status=416);response['Content-Range']=f'bytes */{size}';response['Accept-Ranges']='bytes';return response
        def chunks():
            with path.open('rb') as handle:
                handle.seek(start);remaining=end-start+1
                while remaining:
                    block=handle.read(min(65536,remaining))
                    if not block: break
                    remaining-=len(block);yield block
        response=HttpResponse(status=206,content_type=mime) if request.method=='HEAD' else StreamingHttpResponse(chunks(),status=206,content_type=mime)
        response['Content-Range']=f'bytes {start}-{end}/{size}'
    else:
        response=HttpResponse(content_type=mime) if request.method=='HEAD' else FileResponse(path.open('rb'),content_type=mime)
    response['Content-Length']=str(end-start+1);response['Accept-Ranges']='bytes';response['Cache-Control']='private, max-age=0';return response
