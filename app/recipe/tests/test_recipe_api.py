"""
Tests for the recipe API
"""

from decimal import Decimal
import tempfile
import os

from PIL import Image

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    Recipe,
    Tag,
    Ingredient,
)
from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailsSerializer,
)

RECIPE_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """ Create and return a recipe detail URL """
    return reverse('recipe:recipe-detail', args=[recipe_id])


def image_upload_url(recipe_id):
    """ Create and return a image upload URL """
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def create_recipe(user, **params):
    """ Create and return a sample recipe """
    defaults = {
        'title': 'Sample recipe title',
        'time_minutes': 22,
        'price': Decimal('5.24'),
        'description': 'Sample recipe description',
        'link': 'http://example.com/recipe.pdf',
    }
    defaults.update(params)
    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


def create_user(**params):
    """ Create and return a new user. """
    return get_user_model().objects.create_user(**params)


class PublicRecipeApiTests(TestCase):
    """ Test the public features of the recipe API """

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """ Test auth is required to call API """

        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """ Test the private features of the recipe API """

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email='user@example.com',
            password='password123',
        )
        self.client.force_authenticate(self.user)

    def test_retrive_recipes(self):
        """ Test retriving a list of recipes """
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        # id is incremental, returning reverse order  3,2,1
        recipes = Recipe.objects.all().order_by('-id')

        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """ Test list of recipes is limited to auth user """
        other_user = create_user(email='other@example.com', password='pass123')
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPE_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """ Test get recipe detail """
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailsSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """ Test create recipe """
        payload = {
            'title': 'sample rec',
            'time_minutes': 30,
            'price': Decimal('3.44'),
        }
        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])

        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """ Test partial update of a recipe """
        original_link = 'http://example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user,
            title='sample title',
            link=original_link,
        )

        payload = {'title': 'new title'}
        url = detail_url(recipe.id)
        response = self.client.patch(url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()

        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        """ Test full update of a recipe """
        recipe = create_recipe(
            user=self.user,
            title='sample title',
            link='http://example.com/recipe.pdf',
        )

        payload = {
            'title': 'new title',
            'link': 'http://example.com/new-recipe.pdf',
            'description': 'new description',
            'time_minutes': 10,
            'price': Decimal('2.22'),
        }

        url = detail_url(recipe.id)
        response = self.client.put(url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()

        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_update_user_returns_error(self):
        """ Test changing the recipe user results is an error """
        new_user = create_user(email='user2@example.com', password='password')
        recipe = create_recipe(user=self.user)

        payload = {'user': new_user.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()

        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """ Test deleting the recipe  """
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_delete_other_users_recipe_error(self):
        """ Test trying to delete other users recipe gives error """
        new_user = create_user(email='user2@example.com', password='password')
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """ Test creating recipe with new tags. """
        payload = {
            'title': 'Test Title',
            'time_minutes': 20,
            'price': Decimal('2.99'),
            'tags': [{'name': 'Thai'}, {'name': 'Dinner'}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]

        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_tags(self):
        """ Test creating recipe with existing tags. """
        tag_indian = Tag.objects.create(user=self.user, name='Indian')

        payload = {
            'title': 'Test Title',
            'time_minutes': 20,
            'price': Decimal('2.99'),
            'tags': [{'name': 'Indian'}, {'name': 'Dinner'}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]

        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """ Test creating tag when updating a recipe """
        recipe = create_recipe(user=self.user)

        payload = {'tags': [{'name': 'Dinner'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='Dinner')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """ Test assigning an existing tag when updating a recipe """
        tag_breakfast = Tag.objects.create(user=self.user, name='Breakfast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name='Lunch')
        payload = {'tags': [{'name': 'Lunch'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """ Test clearing a recipies tags """
        tag = Tag.objects.create(user=self.user, name='Dessert')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    # INGREDIENTS
    def test_create_recipe_with_new_ingredients(self):
        """ Test creating recipe with new ingredients. """
        payload = {
            'title': 'Test Title',
            'time_minutes': 20,
            'price': Decimal('2.99'),
            'ingredients': [{'name': 'Thai'}, {'name': 'Dinner'}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]

        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_ingredients(self):
        """ Test creating recipe with existing ingredients. """
        ingredient_pepper = Ingredient.objects.create(
            user=self.user,
            name='Pepper'
        )

        payload = {
            'title': 'Test Title',
            'time_minutes': 20,
            'price': Decimal('2.99'),
            'ingredients': [{'name': 'Pepper'}, {'name': 'Salt'}]
        }

        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]

        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(ingredient_pepper, recipe.ingredients.all())
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_update(self):
        """ Test creating ingredient when updating a recipe """
        recipe = create_recipe(user=self.user)

        payload = {'ingredients': [{'name': 'Suggar'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(
            user=self.user,
            name='Suggar',
        )
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """ Test assigning an existing ingredient when updating a recipe """
        ingredient_pepper = Ingredient.objects.create(
            user=self.user,
            name='Pepper'
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient_pepper)

        ingredient_suggar = Ingredient.objects.create(
            user=self.user,
            name='Suggar'
        )
        payload = {'ingredients': [{'name': 'Suggar'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient_suggar, recipe.ingredients.all())
        self.assertNotIn(ingredient_pepper, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """ Test clearing a recipies ingredients """
        ingredient = Ingredient.objects.create(user=self.user, name='Milk')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {'ingredients': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_tags(self):
        """ Test filtering recipes by tags """
        r1 = create_recipe(user=self.user, title='Thai Vegetable Curry')
        r2 = create_recipe(user=self.user, title='Aubugine with Tahini')

        tag1 = Tag.objects.create(user=self.user, name='Vegan')
        tag2 = Tag.objects.create(user=self.user, name='Vegetarian')

        r1.tags.add(tag1)
        r2.tags.add(tag2)

        r3 = create_recipe(user=self.user, title='Fish and chips')

        params = {'tags': f'{tag1.id},{tag2.id}'}
        res = self.client.get(RECIPE_URL, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)

        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)

    def test_filter_by_ingredients(self):
        """ Test filtering recipes by ingredients """
        r1 = create_recipe(user=self.user, title='Posh beans on toast')
        r2 = create_recipe(user=self.user, title='Chicken Cascciatore')

        in1 = Ingredient.objects.create(user=self.user, name='Feta Cheese')
        in2 = Ingredient.objects.create(user=self.user, name='Chicken')

        r1.ingredients.add(in1)
        r2.ingredients.add(in2)

        r3 = create_recipe(user=self.user, title='Red Lentil Daal')

        params = {'ingredients': f'{in1.id},{in2.id}'}
        res = self.client.get(RECIPE_URL, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)

        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)


# FILE UPLOAD TESTS
class ImageUploadTests(TestCase):
    """ Tests for image upload API """

    # It runs before every test
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email='user@example.com',
            password='testpas',
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    # It runs after every test
    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """ Test uploading an image to a recipe """
        # Create upload img url
        url = image_upload_url(self.recipe.id)

        #  Create temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            # RGB 10px-10px img
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {'image': image_file}
            res = self.client.post(url, payload, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """ Test uploading invalid image """
        url = image_upload_url(self.recipe.id)
        payload = {'image': 'invalidpath'}
        res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
