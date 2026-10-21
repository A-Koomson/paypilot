import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def csrf_client():
    """Client that enforces Django's CSRF middleware the way a real browser would."""
    client = APIClient()
    client.handler.enforce_csrf_checks = True
    return client
