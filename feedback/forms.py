from django import forms
from django.core.exceptions import ValidationError
from .models import ServiceFeedback


class ServiceFeedbackForm(forms.ModelForm):
    """
    Form tiếp nhận phản hồi / góp ý của học viên về trải nghiệm website (UC-FBK-01).
    """
    rating = forms.TypedChoiceField(
        label="Mức độ hài lòng", choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int, widget=forms.RadioSelect,
        error_messages={"required": "Vui lòng chọn số sao.", "invalid_choice": "Chỉ được chọn từ 1 đến 5 sao."},
    )
    publish = forms.BooleanField(
        label="Tôi đồng ý chia sẻ đánh giá theo thông báo bên dưới.",
        error_messages={"required": "Vui lòng xác nhận trước khi lưu đánh giá."},
    )
    content = forms.CharField(
        label="Nội dung đánh giá",
        min_length=5, max_length=2000,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 6,
            "placeholder": "Bạn thích điều gì khi luyện tập? DOL có thể cải thiện điều gì?",
            "aria-describedby": "fb-count fb-content-hint",
        }),
        required=True,
        error_messages={
            "required": "Vui lòng nhập nội dung đánh giá trước khi gửi.",
        }
    )

    class Meta:
        model = ServiceFeedback
        fields = ["rating", "content", "publish"]

    def clean_content(self):
        content = self.cleaned_data.get("content", "").strip()
        if not content:
            raise ValidationError("Nội dung đánh giá không được để trống.")
        if len(content) < 5:
            raise ValidationError("Nội dung đánh giá quá ngắn. Vui lòng nhập tối thiểu 5 ký tự.")
        return content
