"""Run the migrations and serve the application with Gunicorn."""

import multiprocessing
import os
import sys

import django
import gunicorn.app.base  # type: ignore[import-untyped] # no stubs in nixpkgs
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.core.management import execute_from_command_line
from django.core.wsgi import get_wsgi_application

DEFAULT_BIND = "0.0.0.0:8000"
TRUE_VALUES = {"1", "true", "yes", "on"}


class GunicornApplication(gunicorn.app.base.BaseApplication):  # type: ignore[misc] # gunicorn is untyped
    """Custom Gunicorn application to run Django with specific config."""

    def __init__(self, app: WSGIHandler, options: dict[str, str | int | bool]) -> None:
        """Initialize the Gunicorn application with Django WSGI app and options.

        Args:
            app: The Django WSGI application handler.
            options: Configuration options for Gunicorn.
        """
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self) -> None:
        """Load configuration settings from options into Gunicorn config."""
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self) -> WSGIHandler:
        """Load and return the WSGI application."""
        return self.application


def env_flag(name: str) -> bool:
    """Return True if the environment variable is set to a true value."""
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def worker_count() -> int:
    """Return the number of Gunicorn workers, by default one more than the CPUs."""
    workers = os.getenv("ZWEILI_SEARCH_WORKERS")
    if workers is None:
        return multiprocessing.cpu_count() + 1
    return int(workers)


def gunicorn_options() -> dict[str, str | int | bool]:
    """Build the Gunicorn options from the environment."""
    return {
        "bind": os.getenv("ZWEILI_SEARCH_BIND", DEFAULT_BIND),
        "reload": env_flag("GUNICORN_RELOAD"),
        "workers": worker_count(),
    }


def run_migrations() -> None:
    """Run Django database migrations."""
    django.setup()
    call_command("migrate", interactive=False)


def setup_admin() -> None:
    """Create default admin user if it doesn't exist."""
    user_model = get_user_model()
    if not user_model.objects.filter(username="admin").exists():
        user = user_model.objects.create_user(
            "admin", password="password"  # noqa: S106
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()


def main() -> None:
    """Run migrations, optionally create the admin user, and start Gunicorn."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    run_migrations()
    if env_flag("ZWEILI_SEARCH_CREATE_DEFAULT_ADMIN"):
        setup_admin()
    app = get_wsgi_application()
    GunicornApplication(app=app, options=gunicorn_options()).run()


def manage() -> None:
    """Run Django management commands with the project settings."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    execute_from_command_line(sys.argv)
