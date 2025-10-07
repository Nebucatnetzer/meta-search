"""Start script used inside the container CMD."""

import multiprocessing
from typing import Any

import django
import gunicorn.app.base
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application


class GunicornApplication(gunicorn.app.base.BaseApplication):
    """Custom Gunicorn application to run Django with specific config."""

    def __init__(self, app: WSGIHandler, options: dict[str, str | int | bool]) -> None:
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self) -> None:
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self) -> WSGIHandler:
        return self.application


def number_of_workers() -> int:
    return multiprocessing.cpu_count() + 1


def start_gunicorn() -> Any:
    options: dict[str, str | int | bool] = {
        "bind": "0.0.0.0:8000",
        "reload": True,
        "workers": number_of_workers(),
    }
    app = get_wsgi_application()
    return GunicornApplication(app=app, options=options).run()


def run_migrations() -> None:
    django.setup()
    call_command("migrate", interactive=False)


def setup_admin() -> None:
    user_model = get_user_model()
    if not user_model.objects.filter(username="admin").exists():
        user = user_model.objects.create_user("admin", password="password")
        user.is_superuser = True
        user.is_staff = True
        user.save()


def main() -> None:
    run_migrations()
    setup_admin()
    start_gunicorn()


if __name__ == "__main__":
    main()
