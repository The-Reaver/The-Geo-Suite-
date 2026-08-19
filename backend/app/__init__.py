"""Backend application package.

This package holds the FastAPI application for the platform. It exposes
the app factory in main.py, the environment-driven settings in config.py,
route modules under routes, and shared service clients under services.

Every secret loads from environment files through config.py. No module in
this package reads a key from source code. The app runs on placeholder
values so you can start it before you paste live keys.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"