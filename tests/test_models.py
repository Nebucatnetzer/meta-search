import os

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zweili_search.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.test import TestCase

from search.models import Bang

User = get_user_model()


class BangModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_bang_str_method(self):
        bang = Bang.objects.create(
            user=self.user,
            shortcut="g",
            url_template="https://www.google.com/search?q={query}",
        )
        expected_str = "!g -> https://www.google.com/search?q={query}"
        self.assertEqual(str(bang), expected_str)

    def test_bang_unique_together_constraint(self):
        Bang.objects.create(
            user=self.user,
            shortcut="test",
            url_template="https://example.com/search?q={query}",
        )

        user2 = User.objects.create_user(username="testuser2", password="testpass123")
        Bang.objects.create(
            user=user2,
            shortcut="test",
            url_template="https://another.com/search?q={query}",
        )

        bang1 = Bang.objects.get(user=self.user, shortcut="test")
        bang2 = Bang.objects.get(user=user2, shortcut="test")

        self.assertNotEqual(bang1.id, bang2.id)
        self.assertEqual(bang1.shortcut, bang2.shortcut)
        self.assertNotEqual(bang1.user, bang2.user)
