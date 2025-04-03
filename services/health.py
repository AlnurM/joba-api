from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from core.config import get_settings
from core.exceptions import ServiceUnavailableError
from datetime import datetime, timezone, timedelta
import asyncio

logger = logging.getLogger(__name__)
settings = get_settings()

class HealthService:
    def __init__(self):
        self._startup_time = datetime.now(timezone.utc)
        self._last_check_time: Dict[str, datetime] = {}
        self._check_intervals = {
            'database': 5  # Check DB every 5 seconds
        }
        self._cache: Dict[str, Any] = {}
        self._client = None

    async def _check_database(self) -> Dict[str, Any]:
        """
        Check database connectivity with proper timeout handling and connection pooling
        """
        client = None
        try:
            # Create a new client with explicit timeouts
            client = AsyncIOMotorClient(
                settings.MONGO_URL,
                serverSelectionTimeoutMS=2000,  # 2 seconds for server selection
                connectTimeoutMS=2000,          # 2 seconds for connection
                socketTimeoutMS=2000            # 2 seconds for socket operations
            )

            # Wrap database operations in a timeout
            async with asyncio.timeout(3):  # 3 second overall timeout
                # Check basic connectivity
                await client.admin.command('ping')
                
                # Check write permission by attempting to write to a test collection
                test_db = client[settings.DATABASE_NAME]
                test_collection = test_db.health_check
                
                # Write test with timestamp
                timestamp = datetime.now(timezone.utc)
                await test_collection.insert_one({
                    'timestamp': timestamp,
                    'type': 'health_check'
                })
                
                # Clean up old health checks (keep last 10 minutes)
                await test_collection.delete_many({
                    'timestamp': {
                        '$lt': timestamp - timedelta(minutes=10)
                    },
                    'type': 'health_check'
                })

                return {
                    'status': 'healthy',
                    'latency_ms': round((datetime.now(timezone.utc) - timestamp).total_seconds() * 1000, 2)
                }

        except asyncio.TimeoutError:
            logger.error('Database health check timed out')
            raise ServiceUnavailableError('Database health check timed out')
        except Exception as e:
            logger.error(f'Database health check failed: {str(e)}')
            raise ServiceUnavailableError(f'Database error: {str(e)}')
        finally:
            if client:
                try:
                    await client.close()
                except Exception as e:
                    logger.error(f'Error closing database client: {str(e)}')

    async def _should_refresh_check(self, component: str) -> bool:
        """
        Determine if a component needs to be rechecked based on its interval
        """
        last_check = self._last_check_time.get(component)
        if not last_check:
            return True
            
        interval = self._check_intervals.get(component, 60)  # Default 60s
        return (datetime.now(timezone.utc) - last_check).total_seconds() > interval

    async def check_health(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check with caching
        """
        try:
            response = {
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'uptime_seconds': round((datetime.now(timezone.utc) - self._startup_time).total_seconds(), 2),
                'components': {}
            }

            # Database health check with caching
            if await self._should_refresh_check('database'):
                self._cache['database'] = await self._check_database()
                self._last_check_time['database'] = datetime.now(timezone.utc)
            
            response['components']['database'] = self._cache.get('database', {
                'status': 'unknown'
            })

            # Determine overall status
            if any(component.get('status') != 'healthy' 
                  for component in response['components'].values()):
                response['status'] = 'degraded'

            return response

        except Exception as e:
            logger.error(f'Health check failed: {str(e)}')
            return {
                'status': 'unhealthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
                'components': {
                    'database': {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                }
            } 