"""Shared path constants for the MorphLab project."""

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.abspath(os.environ.get('AIMS_MODELS_DIR', os.path.join(ROOT_DIR, "models")))
INSIGHTFACE_ROOT = os.path.join(MODELS_DIR, 'insightface')
