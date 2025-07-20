from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


# Assuming you want the Bang model:
class Bang(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bangs"
    )
    shortcut = models.CharField(max_length=10)
    url_template = models.CharField(
        max_length=256
    )  # e.g. 'https://www.google.com/search?q={query}'

    class Meta:
        unique_together = ("user", "shortcut")

    def __str__(self) -> str:
        return f"!{self.shortcut} -> {self.url_template}"


class BlockedDomain(models.Model):
    domain = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.domain


class BlockList(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocklist"
    )
    blocked_domains = models.ManyToManyField(
        BlockedDomain, related_name="blocklists", help_text="List of blocked domains"
    )


class SearchUser(AbstractUser):
    pass
