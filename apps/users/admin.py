# apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, WorkerProfile


# ==================== INLINE FOR WORKER PROFILE ====================
class WorkerProfileInline(admin.StackedInline):
    model = WorkerProfile
    can_delete = False
    verbose_name_plural = "Worker Profile"
    fk_name = "user"
    extra = 0

    fieldsets = (
        (None, {
            "fields": ("profession", "hourly_rate", "experience_years")
        }),
        ("Skills", {
            "fields": ("skills",),
            "description": "Skills are stored as a list. Workers can add unlimited custom skills."
        }),
        ("Status", {
            "fields": ("is_approved", "rating", "total_jobs"),
        }),
    )
    readonly_fields = ("rating", "total_jobs")


# ==================== CUSTOM USER ADMIN ====================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("id", "email", "full_name", "user_type", "is_profile_complete", "date_joined", "is_active")
    list_filter = ("user_type", "is_profile_complete", "is_active", "date_joined")
    search_fields = ("email", "full_name")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name", "user_type")}),
        ("Status", {"fields": ("is_profile_complete", "is_active", "is_staff", "is_superuser")}),
        ("Timestamps", {"fields": ("date_joined", "last_login")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "password1", "password2", "user_type"),
        }),
    )

    # Show Worker Profile inline only for workers
    inlines = []

    def get_inlines(self, request, obj=None):
        if obj and obj.user_type == "worker":
            return [WorkerProfileInline]
        return []

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("worker_profile")


# ==================== SEPARATE WORKER LIST (Optional but Recommended) ====================
@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("worker_link", "profession", "hourly_rate", "experience", "skills_list", "is_approved", "rating")
    list_filter = ("profession", "is_approved", "experience_years")
    search_fields = ("user__email", "user__full_name")
    list_editable = ("is_approved", "hourly_rate")
    readonly_fields = ("rating", "total_jobs")

    def worker_link(self, obj):
        return format_html(
            '<a href="/admin/users/user/{}/change/">{} ({})</a>',
            obj.user.id, obj.user.full_name or "No Name", obj.user.email
        )
    worker_link.short_description = "Worker"

    def experience(self, obj):
        return f"{obj.experience_years} years"
    experience.short_description = "Experience"

    def skills_list(self, obj):
        if not obj.skills:
            return "—"
        return ", ".join(obj.skills[:5]) + ("..." if len(obj.skills) > 5 else "")
    skills_list.short_description = "Skills (Top 5)"