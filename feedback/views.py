from datetime import timedelta

import logging

from django.contrib import messages
from django.db import models, transaction, OperationalError
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from accounts.permissions import hoc_vien_required, staff_required
from .forms import ServiceFeedbackForm
from .models import ServiceFeedback

logger = logging.getLogger(__name__)

REVIEW_COOLDOWN = timedelta(seconds=60)
REVIEW_DAILY_LIMIT = 3


def _rating_filter(qs, rating):
    if rating in {"1", "2", "3", "4", "5"}:
        return qs.filter(rating=int(rating))
    if rating == "unrated":
        return qs.filter(rating__isnull=True)
    return qs


def _stats(qs):
    rated = qs.filter(rating__isnull=False)
    total = rated.count()
    distribution = dict(rated.order_by().values_list("rating").annotate(total=Count("id")))
    now = timezone.localtime()
    average = rated.aggregate(value=Avg("rating"))["value"]
    return {
        "average": average,
        "average_stars": int(average + 0.5) if average is not None else 0,
        "rated_count": total,
        "review_count": qs.count(),
        "reviewer_count": qs.order_by().values("user_id").distinct().count(),
        "positive_percent": round(sum(distribution.get(star, 0) for star in (4, 5)) * 100 / total) if total else None,
        "low_count": sum(distribution.get(star, 0) for star in (1, 2)),
        "month_count": qs.filter(created_at__year=now.year, created_at__month=now.month).count(),
        "distribution": [
            {"star": star, "count": distribution.get(star, 0),
             "percent": round(distribution.get(star, 0) * 100 / total) if total else 0}
            for star in range(5, 0, -1)
        ],
    }


def _community(request, form, editing=None):
    # Đánh giá cũ chưa có sao là góp ý riêng tư; chỉ công khai sau khi người viết
    # chủ động gửi lại qua form có thông báo công khai.
    public = ServiceFeedback.objects.filter(status=ServiceFeedback.Status.VISIBLE, rating__isnull=False)
    mine = ServiceFeedback.objects.filter(user=request.user)
    tab = "mine" if editing or request.GET.get("tab") == "mine" else "all"
    qs = (mine if tab == "mine" else public).select_related("user")
    search_q = request.GET.get("q", "").strip()[:150]
    rating_filter = request.GET.get("rating", "")
    sort = request.GET.get("sort", "newest")
    if search_q:
        qs = qs.filter(content__icontains=search_q)
    qs = _rating_filter(qs, rating_filter)
    orders = {"newest": ("-created_at", "-pk"), "oldest": ("created_at", "pk"),
              "highest": (models.F("rating").desc(nulls_last=True), "-created_at", "-pk"),
              "lowest": (models.F("rating").asc(nulls_last=True), "-created_at", "-pk")}
    if sort not in orders:
        sort = "newest"
    page = Paginator(qs.order_by(*orders[sort]), 9).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "feedback/feedback_form.html", {
        "form": form, "editing": editing, "page_obj": page, "tab": tab,
        "search_q": search_q, "rating_filter": rating_filter, "sort": sort,
        "mine_count": mine.count(), "stats": _stats(public),
        "page_query": query.urlencode(), "active_nav": "feedback",
        "open_editor": bool(editing or form.is_bound),
        "filter_active": bool(search_q or rating_filter or sort != "newest"),
    })


@hoc_vien_required
@require_http_methods(["GET", "POST"])
def feedback_submit(request):
    form = ServiceFeedbackForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                # Khóa bản ghi người dùng trên DB hỗ trợ row lock, không thêm bảng.
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                now = timezone.now()
                recent = ServiceFeedback.objects.filter(user=request.user, created_at__gte=now - timedelta(days=1))
                if recent.filter(created_at__gte=now - REVIEW_COOLDOWN).exists():
                    form.add_error(None, "Vui lòng đợi ít nhất 60 giây giữa hai lần đăng đánh giá.")
                elif recent.count() >= REVIEW_DAILY_LIMIT:
                    form.add_error(None, "Bạn đã gửi 3 đánh giá trong 24 giờ qua. Bạn vẫn có thể chỉnh sửa các đánh giá cũ.")
                elif any(" ".join(text.split()).casefold() == " ".join(form.cleaned_data["content"].split()).casefold()
                         for text in recent.values_list("content", flat=True)):
                    form.add_error("content", "Bạn đã gửi nội dung giống đánh giá này trong 24 giờ qua.")
                else:
                    feedback = form.save(commit=False)
                    feedback.user = request.user
                    feedback.status = ServiceFeedback.Status.VISIBLE
                    feedback.save()
                    messages.success(request, "Cảm ơn bạn! Đánh giá của bạn đã được đăng.")
                    return redirect(reverse("feedback:feedback_submit") + "?tab=mine")
        except OperationalError as exc:
            # SQLite không hỗ trợ SELECT FOR UPDATE; khi hai lần ghi đồng thời
            # tranh khóa, trả lỗi thân thiện thay vì tạo phản hồi trùng hoặc HTTP 500.
            if "locked" not in str(exc).lower():
                raise
            form.add_error(None, "Hệ thống đang xử lý một yêu cầu khác. Vui lòng thử lại sau ít phút.")
    return _community(request, form)


@hoc_vien_required
@require_http_methods(["GET", "POST"])
def feedback_edit(request, pk):
    feedback = get_object_or_404(ServiceFeedback, pk=pk, user=request.user)
    form = ServiceFeedbackForm(request.POST if request.method == "POST" else None, instance=feedback)
    if request.method == "POST" and form.is_valid():
        # Chỉ cập nhật nội dung và sao, không ghi đè trạng thái kiểm duyệt.
        item = form.save(commit=False)
        item.save(update_fields=["content", "rating", "updated_at"])
        messages.success(request, "Đã cập nhật đánh giá của bạn.")
        return redirect(reverse("feedback:feedback_submit") + "?tab=mine")
    return _community(request, form, editing=feedback)


@staff_required
@permission_required("feedback.view_servicefeedback", raise_exception=True)
def feedback_list(request):
    """
    UC-FBK-02: Quản trị viên xem danh sách đánh giá / góp ý.
    - Hiển thị danh sách phản hồi, người gửi, nội dung, thời gian, trạng thái.
    - Lọc theo VISIBLE và HIDDEN (hoặc tất cả).
    - Mặc định chỉ lọc VISIBLE nếu chọn, hoặc xem toàn bộ.
    """
    status_filter = request.GET.get("status", "").strip().upper()
    search_q = request.GET.get("q", "").strip()[:150]

    qs = ServiceFeedback.objects.select_related("user").order_by("-created_at")

    if status_filter in [ServiceFeedback.Status.VISIBLE, ServiceFeedback.Status.HIDDEN]:
        qs = qs.filter(status=status_filter)

    if search_q:
        qs = qs.filter(
            Q(content__icontains=search_q) |
            Q(user__username__icontains=search_q) |
            Q(user__first_name__icontains=search_q) |
            Q(user__last_name__icontains=search_q)
        )

    rating_filter = request.GET.get("rating", "")
    qs = _rating_filter(qs, rating_filter)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    total_count = ServiceFeedback.objects.count()
    visible_count = ServiceFeedback.objects.filter(status=ServiceFeedback.Status.VISIBLE).count()
    hidden_count = ServiceFeedback.objects.filter(status=ServiceFeedback.Status.HIDDEN).count()

    context = {
        "feedbacks": page,
        "page_obj": page, "page_query": query.urlencode(),
        "rating_filter": rating_filter,
        "stats": _stats(ServiceFeedback.objects.all()),
        "public_count": ServiceFeedback.objects.filter(status=ServiceFeedback.Status.VISIBLE, rating__isnull=False).count(),
        "legacy_count": ServiceFeedback.objects.filter(rating__isnull=True).count(),
        "status_filter": status_filter,
        "search_q": search_q,
        "total_count": total_count,
        "visible_count": visible_count,
        "hidden_count": hidden_count,
        "active_nav": "feedback_manage",
    }
    return render(request, "feedback/feedback_list.html", context)


@require_POST
@staff_required
@permission_required("feedback.change_servicefeedback", raise_exception=True)
def feedback_status_toggle(request, pk):
    """
    UC-FBK-03: Ẩn hoặc Hiện lại đánh giá / góp ý.
    - Nếu đang VISIBLE -> chuyển sang HIDDEN (không xóa dữ liệu).
    - Nếu đang HIDDEN -> chuyển sang VISIBLE.
    """
    feedback = get_object_or_404(ServiceFeedback, pk=pk)
    if feedback.status == ServiceFeedback.Status.VISIBLE:
        feedback.status = ServiceFeedback.Status.HIDDEN
        msg = f"Đã ẩn đánh giá #{feedback.id} thành công (vẫn được lưu trong cơ sở dữ liệu)."
    else:
        feedback.status = ServiceFeedback.Status.VISIBLE
        msg = (f"Đã hiển thị lại đánh giá #{feedback.id} thành công." if feedback.rating is not None
               else f"Đã bỏ trạng thái ẩn cho góp ý #{feedback.id}. Nội dung vẫn riêng tư vì chưa có sao.")

    feedback.save(update_fields=["status", "updated_at"])
    messages.success(request, msg)
    return redirect("feedback:feedback_list")


@require_POST
@staff_required
@permission_required("feedback.delete_servicefeedback", raise_exception=True)
def feedback_delete(request, pk):
    """
    UC-FBK-03: Xóa đánh giá / góp ý (yêu cầu xác nhận từ hộp thoại trước khi xóa).
    """
    feedback = get_object_or_404(ServiceFeedback, pk=pk)
    feedback_id = feedback.id
    feedback.delete()
    messages.success(request, f"Đã xóa vĩnh viễn đánh giá #{feedback_id}.")
    return redirect("feedback:feedback_list")
