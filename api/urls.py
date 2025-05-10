# api/urls.py
from django.urls import path
from .views import generate_midi_mashups

urlpatterns = [
    path('generate-midi-mashups/', generate_midi_mashups),
]
