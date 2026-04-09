from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('secret-admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    path('', RedirectView.as_view(url='/secret-admin/', permanent=False)),
]