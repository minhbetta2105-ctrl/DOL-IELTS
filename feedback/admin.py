from django.contrib import admin
from .models import ServiceFeedback


@admin.register(ServiceFeedback)
class ServiceFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content_preview", "rating", "status", "created_at")
    list_filter = ("status", "rating", "created_at")
    search_fields = ("user__username", "content")
    # Admin kiểm duyệt trạng thái, không viết/sửa số sao thay học viên.
    readonly_fields = ("user", "content", "rating", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def content_preview(self, obj):
        return (obj.content[:80] + "...") if len(obj.content) > 80 else obj.content
    content_preview.short_description = "Nội dung"
