"""
Integration Tests - Real Database, No Mocks

This package contains tests that verify the system works with REAL services.
Unlike unit tests which mock dependencies, these tests:

- Connect to actual Neo4j database
- Make real API calls
- Verify end-to-end functionality

REQUIREMENTS:
    - INTEGRATION_TEST_DB=true environment variable
    - Running Neo4j instance
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables

RUN:
    pytest tests/test_integration/ -v
"""
