from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Bang(models.Model):
    user: models.ForeignKey[AbstractUser] = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bangs",
    )
    shortcut = models.CharField(max_length=10)
    # e.g. 'https://www.google.com/search?q={query}'
    url_template = models.CharField(max_length=256)

    class Meta:
        unique_together = ("user", "shortcut")

    def __str__(self) -> str:
        return f"!{self.shortcut} -> {self.url_template}"


class SearchUser(AbstractUser):
    default_search_engine_url = models.URLField(
        max_length=500,
        default="https://duckduckgo.com/?q={query}",
        help_text="Default search engine URL template. Use {query} as placeholder.",
    )
