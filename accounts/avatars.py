"""One private, normalized avatar per existing user; no database schema changes."""
from pathlib import Path
from tempfile import NamedTemporaryFile
import os

from django.conf import settings
from django.core.exceptions import ValidationError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


def avatar_path(user_id):
    return Path(settings.BASE_DIR) / 'private_avatars' / f'{int(user_id)}.jpg'


def save_avatar(user_id, uploaded):
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not uploaded or uploaded.size > MAX_BYTES:
        raise ValidationError('Chọn ảnh JPG, PNG hoặc WebP không quá 5 MB.')
    target = avatar_path(user_id)
    temp_path = None
    try:
        with Image.open(uploaded) as source:
            if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValidationError('Chỉ hỗ trợ ảnh JPG, PNG và WebP.')
            if source.width * source.height > MAX_PIXELS:
                raise ValidationError('Ảnh quá lớn. Hãy chọn ảnh dưới 16 triệu điểm ảnh.')
            source.load()
            oriented = ImageOps.exif_transpose(source).convert('RGBA')
            background = Image.new('RGBA', oriented.size, 'white')
            background.alpha_composite(oriented)
            photo = ImageOps.fit(background.convert('RGB'), (320, 320), method=Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=target.parent, suffix='.tmp', delete=False) as temp:
            temp_path = Path(temp.name)
            photo.save(temp, 'JPEG', quality=88, optimize=True)
        os.replace(temp_path, target)
    except (UnidentifiedImageError, Image.DecompressionBombError, ValueError, SyntaxError, OSError) as exc:
        raise ValidationError('Không thể sử dụng ảnh này. Hãy chọn một ảnh hợp lệ và thử lại.') from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
