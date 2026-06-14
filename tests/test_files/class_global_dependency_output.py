import os

# Global variables that classes depend on
DATABASE_CONFIG = {"database": "test_db", "host": "localhost", "port": 5432}

API_ENDPOINTS = ["/api/users", "/api/posts", "/api/comments"]

DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"


class APIClient:
    """API client that uses global endpoints."""

    def __init__(self):
        self.endpoints = API_ENDPOINTS.copy()
        self.base_url = "https://api.example.com"

    def get_endpoints(self):
        """Get all available endpoints."""
        return [f"{self.base_url}{endpoint}" for endpoint in self.endpoints]

    def is_debug_mode(self):
        """Check if debug mode is enabled."""
        return DEBUG_MODE

    def make_request(self, endpoint):
        """Make a request to an endpoint."""
        if endpoint in self.endpoints:
            return f"GET {self.base_url}{endpoint}"
        return None


class ConfigManager:
    """Manages application configuration."""

    def __init__(self):
        self.database_config = DATABASE_CONFIG
        self.api_endpoints = API_ENDPOINTS
        self.debug_mode = DEBUG_MODE

    def add_endpoint(self, endpoint):
        """Add a new endpoint."""
        global API_ENDPOINTS
        if endpoint not in API_ENDPOINTS:
            API_ENDPOINTS.append(endpoint)
            self.api_endpoints = API_ENDPOINTS

    def get_all_config(self):
        """Get all configuration."""
        return {"database": self.database_config, "debug": self.debug_mode, "endpoints": self.api_endpoints}

    def update_database_config(self, new_config):
        """Update database configuration."""
        global DATABASE_CONFIG
        DATABASE_CONFIG.update(new_config)
        self.database_config = DATABASE_CONFIG


class DatabaseManager:
    """Manages database connections using global config."""

    def __init__(self):
        self.host = DATABASE_CONFIG["host"]
        self.port = DATABASE_CONFIG["port"]
        self.database = DATABASE_CONFIG["database"]

    def connect(self):
        """Connect to database."""
        return f"Connected to {self.host}:{self.port}/{self.database}"

    def get_config(self):
        """Get database configuration."""
        return DATABASE_CONFIG.copy()

    def is_debug_mode(self):
        """Check if debug mode is enabled."""
        return DEBUG_MODE
