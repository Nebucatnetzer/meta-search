"""Script to create default admin user for development."""

from django.contrib.auth import get_user_model

# see ref. below
UserModel = get_user_model()

if not UserModel.objects.filter(username="admin").exists():
    user = UserModel.objects.create_user("admin", password="password")  # noqa: S106
    user.is_superuser = True
    user.is_staff = True
    user.save()
