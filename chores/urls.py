from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("", views.home, name="home"),
    path("setup/", views.setup, name="setup"),
    path("members/select/", views.select_member, name="select_member"),
    path("settings/", views.settings, name="settings"),
]
