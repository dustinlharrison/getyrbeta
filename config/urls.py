from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^account_info/', include('account_info.urls')),
    url(r'^$', TemplateView.as_view(template_name='core/welcome.html'), name='welcome'),
    url(r'^auth/', include('authentication.urls')),
    url(r'^trips/', include('trips.urls')),

    # User management
    url(r'^accounts/', include('allauth.urls')),

    # Django Admin, use {% url 'admin:index' %}
    url(settings.ADMIN_URL, admin.site.urls),
]
if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
