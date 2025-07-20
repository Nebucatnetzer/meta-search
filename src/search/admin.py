from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from search.models import Bang
from search.models import SearchUser

admin.site.register(Bang)
admin.site.register(SearchUser, UserAdmin)
