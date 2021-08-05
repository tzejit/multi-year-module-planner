from django.urls import path
from . import views

app_name = "mods"
urlpatterns = [
    path("", views.index, name="index")
]