import os
import sys

# Ensure the project root is in the python path
sys.path.insert(0, os.path.dirname(__file__))

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartstore.settings')

from smartstore.wsgi import application