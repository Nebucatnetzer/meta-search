"""Django models for the search application."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Bang(models.Model):
    """A Bang shortcut for quick search redirection."""

    user: models.ForeignKey[AbstractUser] = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bangs",
    )
    shortcut = models.CharField(max_length=10)
    url_template = models.CharField(
        max_length=256
    )  # e.g. 'https://www.google.com/search?q={query}'

    class Meta:
        """Meta options for Bang model."""

        unique_together = ("user", "shortcut")

    def __str__(self) -> str:
        """Return string representation of Bang."""
        return f"!{self.shortcut} -> {self.url_template}"


class BlockedDomain(models.Model):
    """A domain that can be blocked from search results."""

    domain = models.CharField(max_length=255, unique=True)

    def __str__(self) -> str:
        """Return string representation of BlockedDomain."""
        return self.domain


class BlockList(models.Model):
    """A user's list of blocked domains."""

    user: models.OneToOneField[AbstractUser] = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocklist",
    )
    blocked_domains: models.ManyToManyField[BlockedDomain, BlockedDomain] = (
        models.ManyToManyField(
            BlockedDomain,
            related_name="blocklists",
            help_text="List of blocked domains",
        )
    )

    def __str__(self) -> str:
        """Return string representation of BlockList."""
        return f"Block list for {self.user}"


class SearchUser(AbstractUser):
    """Custom user model for the search application."""
