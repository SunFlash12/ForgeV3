#!/usr/bin/env python3
"""
Forge Cascade V2 - Health Check Script

This script performs a comprehensive health check of the Forge system,
including database connectivity, API availability, and component status.
"""

import asyncio
import sys
from datetime import datetime

import httpx

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from forge.config import get_settings
from forge.database.client import Neo4jClient


async def check_neo4j(settings) -> dict:
    """Check Neo4j database connectivity."""
    print("Checking Neo4j...")
    
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    
    try:
        await client.connect()
        
        # Test query
        result = await client.execute_query("RETURN 1 as test")
        
        # Get node counts
        counts = await client.execute_query("""
            MATCH (u:User) WITH count(u) as users
            MATCH (c:Capsule) WITH users, count(c) as capsules
            MATCH (p:Proposal) WITH users, capsules, count(p) as proposals
            MATCH (o:Overlay) WITH users, capsules, proposals, count(o) as overlays
            RETURN users, capsules, proposals, overlays
        """)
        
        stats = counts[0] if counts else {}
        
        await client.disconnect()
        
        return {
            "status": "healthy",
            "connected": True,
            "stats": {
                "users": stats.get("users", 0),
                "capsules": stats.get("capsules", 0),
                "proposals": stats.get("proposals", 0),
                "overlays": stats.get("overlays", 0),
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


async def check_api(api_url: str) -> dict:
    """Check API availability."""
    print("Checking API...")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{api_url}/api/v1/system/health")
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy",
                    "available": True,
                    "response": data,
                }
            else:
                return {
                    "status": "degraded",
                    "available": True,
                    "status_code": response.status_code,
                }
    except httpx.ConnectError:
        return {
            "status": "unhealthy",
            "available": False,
            "error": "Connection refused",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "available": False,
            "error": str(e),
        }


async def check_redis(redis_url: str) -> dict:
    """Check Redis connectivity."""
    print("Checking Redis...")
    
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(redis_url)
        await client.ping()
        info = await client.info("server")
        await client.close()
        
        return {
            "status": "healthy",
            "connected": True,
            "version": info.get("redis_version", "unknown"),
        }
    except ImportError:
        return {
            "status": "skipped",
            "reason": "redis package not installed",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


def print_result(component: str, result: dict):
    """Print formatted result."""
    status = result.get("status", "unknown")
    
    if status == "healthy":
        icon = "✅"
    elif status == "degraded":
        icon = "⚠️"
    elif status == "skipped":
        icon = "⏭️"
    else:
        icon = "❌"
    
    print(f"\n{icon} {component}: {status.upper()}")
    
    for key, value in result.items():
        if key != "status":
            if isinstance(value, dict):
                print(f"   {key}:")
                for k, v in value.items():
                    print(f"      {k}: {v}")
            else:
                print(f"   {key}: {value}")


async def main():
    """Run health checks."""
    print("=" * 60)
    print("Forge Cascade V2 - Health Check")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    settings = get_settings()
    
    # Check Neo4j
    neo4j_result = await check_neo4j(settings)
    print_result("Neo4j Database", neo4j_result)
    
    # Check API (if running)
    api_url = f"http://{settings.api_host}:{settings.api_port}"
    api_result = await check_api(api_url)
    print_result("Forge API", api_result)
    
    # Check Redis (optional)
    redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379/0')
    redis_result = await check_redis(redis_url)
    print_result("Redis Cache", redis_result)
    
    # Overall status
    print("\n" + "=" * 60)
    
    all_healthy = all(
        r.get("status") in ("healthy", "skipped")
        for r in [neo4j_result, api_result, redis_result]
    )
    
    if all_healthy:
        print("Overall Status: ✅ HEALTHY")
        return 0
    else:
        print("Overall Status: ❌ UNHEALTHY")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
