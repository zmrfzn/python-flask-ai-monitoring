"""Weather cache implementation with TTL support."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

import newrelic.agent


logger = logging.getLogger("tools.cache")


@dataclass
class WeatherCacheEntry:
    """Cache entry for weather data with TTL."""

    data: str
    timestamp: datetime
    city: str


class WeatherCache:
    """Simple TTL-based cache for weather data."""

    def __init__(self, ttl_minutes: int = 10):
        """
        Initialize the weather cache.

        Args:
            ttl_minutes: Time-to-live for cache entries in minutes (default: 10)
        """
        self._cache: Dict[str, WeatherCacheEntry] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._hits = 0
        self._misses = 0

    @newrelic.agent.function_trace()
    def get(self, city: str) -> Optional[str]:
        """
        Get cached weather data for a city if not expired.

        Args:
            city: City name (case-insensitive)

        Returns:
            Cached weather data if available and not expired, None otherwise
        """
        city_key = city.lower()

        if city_key in self._cache:
            entry = self._cache[city_key]
            age = datetime.now() - entry.timestamp

            if age < self._ttl:
                self._hits += 1

                # Record cache hit metrics
                stats = self.get_stats()
                newrelic.agent.record_custom_metric("Custom/Cache/Hits", self._hits)
                newrelic.agent.record_custom_metric(
                    "Custom/Cache/HitRate", stats["hit_rate_percent"]
                )
                newrelic.agent.record_custom_metric(
                    "Custom/Cache/Size", len(self._cache)
                )
                newrelic.agent.record_custom_metric(
                    "Custom/Cache/EntryAge", int(age.total_seconds())
                )

                logger.debug(
                    "[weather_cache] hit",
                    extra={
                        "city": city,
                        "age_seconds": int(age.total_seconds()),
                        "ttl_seconds": int(self._ttl.total_seconds()),
                    },
                )
                return entry.data
            else:
                # Expired entry
                newrelic.agent.record_custom_metric("Custom/Cache/Expired", 1)

                logger.debug(
                    "[weather_cache] expired",
                    extra={"city": city, "age_seconds": int(age.total_seconds())},
                )
                del self._cache[city_key]

        self._misses += 1

        # Record cache miss metrics
        stats = self.get_stats()
        newrelic.agent.record_custom_metric("Custom/Cache/Misses", self._misses)
        newrelic.agent.record_custom_metric(
            "Custom/Cache/HitRate", stats["hit_rate_percent"]
        )
        newrelic.agent.record_custom_metric("Custom/Cache/Size", len(self._cache))

        logger.debug("[weather_cache] miss", extra={"city": city})
        return None

    @newrelic.agent.function_trace()
    def set(self, city: str, data: str) -> None:
        """
        Store weather data in cache.

        Args:
            city: City name
            data: Weather data to cache
        """
        city_key = city.lower()
        self._cache[city_key] = WeatherCacheEntry(
            data=data, timestamp=datetime.now(), city=city
        )

        # Record cache size metric
        newrelic.agent.record_custom_metric("Custom/Cache/Size", len(self._cache))
        newrelic.agent.record_custom_metric("Custom/Cache/Writes", 1)

        logger.debug(
            "[weather_cache] set", extra={"city": city, "cache_size": len(self._cache)}
        )

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("[weather_cache] cleared")

    def get_stats(self) -> Dict[str, float]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, size, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "hits": float(self._hits),
            "misses": float(self._misses),
            "size": float(len(self._cache)),
            "hit_rate_percent": round(hit_rate, 2),
        }
