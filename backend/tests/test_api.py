"""
API Tests
Test API endpoints
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_api_health(client: AsyncClient):
    """Test API health endpoint"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test that protected endpoints require auth"""
    response = await client.get("/api/v1/jira/story/TEST-123")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123",
            "name": "Test User",
            "role": "qa"
        }
    )
    # May fail if user exists, that's ok
    assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_generate_ac_requires_input(client: AsyncClient, auth_headers: dict):
    """Test that generation requires issue_id or story_text"""
    response = await client.post(
        "/api/v1/generate/acceptance-criteria",
        headers=auth_headers,
        json={}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_providers(client: AsyncClient, auth_headers: dict):
    """Test getting available LLM providers"""
    response = await client.get(
        "/api/v1/generate/providers",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "available_providers" in data
    assert "supported_providers" in data
