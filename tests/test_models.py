"""Unit tests for Django models."""

import pytest

from search.models import Bang
from search.models import BlockedDomain
from search.models import BlockList
from search.models import SearchUser


@pytest.mark.django_db
class TestBangModel:
    """Tests for Bang model."""

    def test_create_bang(self) -> None:
        """Test creating a Bang instance."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        bang = Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com/search?q={query}",
        )
        assert bang.shortcut == "g"
        assert bang.url_template == "https://google.com/search?q={query}"
        assert bang.user == user

    def test_bang_str_representation(self) -> None:
        """Test __str__ method of Bang."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        bang = Bang.objects.create(
            user=user,
            shortcut="gh",
            url_template="https://github.com/search?q={query}",
        )
        assert str(bang) == "!gh -> https://github.com/search?q={query}"

    def test_bang_unique_together_constraint(self) -> None:
        """Test that user + shortcut must be unique."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com/search?q={query}",
        )

        # Creating duplicate should raise IntegrityError
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Bang.objects.create(
                user=user,
                shortcut="g",
                url_template="https://different.com?q={query}",
            )

    def test_different_users_same_shortcut(self) -> None:
        """Test that different users can have the same shortcut."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass")
        user2 = SearchUser.objects.create_user(username="user2", password="pass")

        bang1 = Bang.objects.create(
            user=user1,
            shortcut="g",
            url_template="https://google.com?q={query}",
        )
        bang2 = Bang.objects.create(
            user=user2,
            shortcut="g",
            url_template="https://different.com?q={query}",
        )

        assert bang1.shortcut == bang2.shortcut
        assert bang1.user != bang2.user

    def test_bang_cascade_delete_on_user_delete(self) -> None:
        """Test that bangs are deleted when user is deleted."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com?q={query}",
        )

        assert Bang.objects.filter(user=user).count() == 1
        user.delete()
        assert Bang.objects.filter(shortcut="g").count() == 0

    def test_bang_max_shortcut_length(self) -> None:
        """Test shortcut with maximum allowed length."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        long_shortcut = "a" * 10  # max_length is 10
        bang = Bang.objects.create(
            user=user,
            shortcut=long_shortcut,
            url_template="https://example.com?q={query}",
        )
        assert len(bang.shortcut) == 10


@pytest.mark.django_db
class TestBlockedDomainModel:
    """Tests for BlockedDomain model."""

    def test_create_blocked_domain(self) -> None:
        """Test creating a BlockedDomain instance."""
        domain = BlockedDomain.objects.create(domain="spam.com")
        assert domain.domain == "spam.com"

    def test_blocked_domain_str_representation(self) -> None:
        """Test __str__ method of BlockedDomain."""
        domain = BlockedDomain.objects.create(domain="ads.example.com")
        assert str(domain) == "ads.example.com"

    def test_blocked_domain_unique_constraint(self) -> None:
        """Test that domain must be unique."""
        BlockedDomain.objects.create(domain="spam.com")

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            BlockedDomain.objects.create(domain="spam.com")

    def test_blocked_domain_max_length(self) -> None:
        """Test domain with maximum allowed length."""
        long_domain = "a" * 255  # max_length is 255
        domain = BlockedDomain.objects.create(domain=long_domain)
        assert len(domain.domain) == 255


@pytest.mark.django_db
class TestBlockListModel:
    """Tests for BlockList model."""

    def test_create_blocklist(self) -> None:
        """Test creating a BlockList instance."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)
        assert blocklist.user == user
        assert blocklist.blocked_domains.count() == 0

    def test_blocklist_str_representation(self) -> None:
        """Test __str__ method of BlockList."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)
        assert str(blocklist) == "Block list for testuser"

    def test_blocklist_add_domains(self) -> None:
        """Test adding domains to blocklist."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)

        domain1 = BlockedDomain.objects.create(domain="spam.com")
        domain2 = BlockedDomain.objects.create(domain="ads.com")

        blocklist.blocked_domains.add(domain1, domain2)

        assert blocklist.blocked_domains.count() == 2
        assert domain1 in blocklist.blocked_domains.all()
        assert domain2 in blocklist.blocked_domains.all()

    def test_blocklist_remove_domain(self) -> None:
        """Test removing a domain from blocklist."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)
        domain = BlockedDomain.objects.create(domain="spam.com")

        blocklist.blocked_domains.add(domain)
        assert blocklist.blocked_domains.count() == 1

        blocklist.blocked_domains.remove(domain)
        assert blocklist.blocked_domains.count() == 0

    def test_blocklist_cascade_delete_on_user_delete(self) -> None:
        """Test that blocklist is deleted when user is deleted."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)

        user_id = user.id
        user.delete()

        assert not BlockList.objects.filter(user_id=user_id).exists()

    def test_blocked_domain_shared_across_blocklists(self) -> None:
        """Test that blocked domains can be shared across multiple blocklists."""
        user1 = SearchUser.objects.create_user(username="user1", password="pass")
        user2 = SearchUser.objects.create_user(username="user2", password="pass")

        blocklist1 = BlockList.objects.create(user=user1)
        blocklist2 = BlockList.objects.create(user=user2)

        domain = BlockedDomain.objects.create(domain="spam.com")

        blocklist1.blocked_domains.add(domain)
        blocklist2.blocked_domains.add(domain)

        assert domain in blocklist1.blocked_domains.all()
        assert domain in blocklist2.blocked_domains.all()

    def test_blocklist_one_per_user(self) -> None:
        """Test that each user can have only one blocklist (OneToOneField)."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        BlockList.objects.create(user=user)

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            BlockList.objects.create(user=user)


@pytest.mark.django_db
class TestSearchUserModel:
    """Tests for SearchUser model."""

    def test_create_search_user(self) -> None:
        """Test creating a SearchUser instance."""
        user = SearchUser.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        assert user.username == "testuser"
        assert user.check_password("testpass123")

    def test_search_user_inherits_from_abstract_user(self) -> None:
        """Test that SearchUser has AbstractUser fields."""
        user = SearchUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        assert user.email == "test@example.com"
        assert hasattr(user, "is_active")
        assert hasattr(user, "is_staff")
        assert hasattr(user, "is_superuser")

    def test_search_user_related_bangs(self) -> None:
        """Test accessing related bangs through user."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        bang = Bang.objects.create(
            user=user,
            shortcut="g",
            url_template="https://google.com?q={query}",
        )

        assert bang in user.bangs.all()
        assert user.bangs.count() == 1

    def test_search_user_related_blocklist(self) -> None:
        """Test accessing related blocklist through user."""
        user = SearchUser.objects.create_user(username="testuser", password="pass")
        blocklist = BlockList.objects.create(user=user)

        assert user.blocklist == blocklist
