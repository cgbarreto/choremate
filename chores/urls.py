from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("", views.home, name="home"),
    path("setup/", views.setup, name="setup"),
    path("members/select/", views.select_member, name="select_member"),
    path("settings/", views.settings, name="settings"),
    path("library/", views.library, name="library"),
    path("library/add/", views.chore_create, name="chore_create"),
    path("library/<int:pk>/edit/", views.chore_edit, name="chore_edit"),
    path("library/<int:pk>/toggle/", views.chore_toggle, name="chore_toggle"),
    path("library/catalog/", views.catalog, name="catalog"),
    path("library/catalog/<slug:slug>/add/", views.catalog_add, name="catalog_add"),
    path("occurrences/", views.occurrences, name="occurrences"),
    path("occurrences/<int:pk>/assign/", views.assign_occurrence, name="assign_occurrence"),
    path("week/", views.week, name="week"),
]
