"""
URL mappings for the recipe API
"""

from django.urls import path, include
from rest_framework import routers
from recipe import views


router = routers.DefaultRouter()
router.register(r'recipes', views.RecipeViewSet) # CRUD /recipe

app_name = 'recipe'

urlpatterns = [
    path('', include(router.urls)),
]