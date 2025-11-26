"""Server entrypoint for LLM Council API."""
import sys
import os

# Add the backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app

__all__ = ['app']
