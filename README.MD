* Run lint inside docker container
docker-compose run --rm app sh -c "python manage.py wait_for_db && flake8"
