from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from search.models import Bang
from search.models import BlockedDomain
from search.models import BlockList
from search.models import SearchUser

admin.site.register(Bang)
admin.site.register(BlockedDomain)
admin.site.register(BlockList)
admin.site.register(SearchUser, UserAdmin)
