"""
Tests for the recipes API
"""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    Ingredient,
    Recipe,
)
from recipe.serializers import IngredientSerializer

INGREDIENT_URL = reverse('recipe:ingredient-list')


def create_user(email='user@example.com', password='pass123'):
    """ Create and return a new user. """
    return get_user_model().objects.create_user(email, password)


def detail_url(ingredient_id):
    """ Create and return a ingredient detail URL """
    return reverse('recipe:ingredient-detail', args=[ingredient_id])


class PublicIngredientsApiTests(TestCase):
    """ Test the public features of the Ingredients API """

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """ Test auth is required to call API """

        res = self.client.get(INGREDIENT_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTests(TestCase):
    """ Tests the private ingredients API """
    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """ Test retriving list of ingredients """
        Ingredient.objects.create(user=self.user, name="Kale")
        Ingredient.objects.create(user=self.user, name="Vanilla")

        res = self.client.get(INGREDIENT_URL)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_ingredients_limited_to_user(self):
        """ Test list of ingredients is limited to auth user """
        user2 = create_user(email='user2@example.com')

        Ingredient.objects.create(user=user2, name="Salt")
        auth_user_ing = Ingredient.objects.create(
            user=self.user,
            name="Pepper",
        )

        res = self.client.get(INGREDIENT_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], auth_user_ing.name)
        self.assertEqual(res.data[0]['id'], auth_user_ing.id)

    def test_update_ingredient(self):
        """ Test updating a ingredient """
        ingredient = Ingredient.objects.create(user=self.user, name="Pepper")

        payload = {'name': 'Sugar'}
        url = detail_url(ingredient.id)

        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.name, payload['name'])

    def test_delete_ingredient(self):
        """ Test deleting a ingredient """
        ingredient = Ingredient.objects.create(user=self.user, name="Pepper")

        url = detail_url(ingredient.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        ingredients = Ingredient.objects.filter(user=self.user)
        self.assertFalse(ingredients.exists())

    def test_filter_ingredients_assigned_to_recipes(self):
        """ Test listing ingredients by those assigned to recipes """
        ing1 = Ingredient.objects.create(user=self.user, name="Apples")
        ing2 = Ingredient.objects.create(user=self.user, name="Turkey")

        recipe = Recipe.objects.create(
            title="Apple Crumble",
            time_minutes=5,
            price=Decimal('4.50'),
            user=self.user,
        )
        recipe.ingredients.add(ing1)

        res = self.client.get(INGREDIENT_URL, {'assigned_only': 1})

        s1 = IngredientSerializer(ing1)
        s2 = IngredientSerializer(ing2)

        print(s1)

        print(res.data)

        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filter_ingredients_unique(self):
        """ Test listing ingredients returns a unique list """
        ing = Ingredient.objects.create(user=self.user, name="Eggs")
        Ingredient.objects.create(user=self.user, name="Turkey")

        recipe1 = Recipe.objects.create(
            title="Eggs Crumble",
            time_minutes=60,
            price=Decimal('4.50'),
            user=self.user,
        )

        recipe2 = Recipe.objects.create(
            title="Herb Eggs",
            time_minutes=20,
            price=Decimal('3.50'),
            user=self.user,
        )
        recipe1.ingredients.add(ing)
        recipe2.ingredients.add(ing)

        res = self.client.get(INGREDIENT_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
