import os

SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://myuser:mypassword@postgres:5432/mydb')
SQLALCHEMY_TRACK_MODIFICATIONS = False
