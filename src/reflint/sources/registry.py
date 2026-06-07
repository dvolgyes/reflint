"""Data source registry and management."""

from typing import Any

from loguru import logger

from .base import BaseDataSource, LookupResult, DataSourceError


class DataSourceRegistry:
    """Registry for external data sources."""

    def __init__(self) -> None:
        self._sources: dict[str, BaseDataSource] = {}
        self._sources_by_identifier: dict[str, list[BaseDataSource]] = {}

    def register_source(self, source: BaseDataSource) -> None:
        """Register a data source."""
        if source.name in self._sources:
            logger.warning(f"Data source {source.name} already registered, overwriting")

        self._sources[source.name] = source

        # Index by supported identifiers
        for identifier_type in source.get_supported_identifiers():
            if identifier_type not in self._sources_by_identifier:
                self._sources_by_identifier[identifier_type] = []
            self._sources_by_identifier[identifier_type].append(source)

        logger.debug(f"Registered data source {source.name}")

    def get_source(self, name: str) -> BaseDataSource | None:
        """Get a data source by name."""
        return self._sources.get(name)

    def get_sources_for_identifier(self, identifier_type: str) -> list[BaseDataSource]:
        """Get data sources that support a specific identifier type."""
        sources = self._sources_by_identifier.get(identifier_type, [])
        # Sort by confidence (highest first)
        return sorted(sources, key=lambda s: s.confidence, reverse=True)

    def get_all_sources(self) -> list[BaseDataSource]:
        """Get all registered data sources."""
        return list(self._sources.values())

    def get_source_names(self) -> list[str]:
        """Get names of all registered data sources."""
        return list(self._sources.keys())

    async def lookup_with_fallback(
        self,
        identifier_type: str,
        value: str,
        preferred_sources: list[str] | None = None,
    ) -> list[LookupResult]:
        """Look up identifier with fallback across multiple sources."""
        results: list[LookupResult] = []

        # Get sources for this identifier type
        available_sources = self.get_sources_for_identifier(identifier_type)

        # Filter to preferred sources if specified
        if preferred_sources:
            available_sources = [
                s for s in available_sources if s.name in preferred_sources
            ]

        # Try each source
        for source in available_sources:
            try:
                logger.debug(f"Looking up {identifier_type}:{value} in {source.name}")
                result = await source.lookup_by_identifier(identifier_type, value)
                if result.entry:
                    results.append(result)
                    logger.info(f"Found entry in {source.name}")
                else:
                    logger.debug(f"No entry found in {source.name}")
            except DataSourceError as e:
                logger.warning(f"Error looking up in {source.name}: {e}")
                # Continue with next source
                continue
            except Exception as e:
                logger.error(f"Unexpected error with {source.name}: {e}")
                continue

        return results

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about registered sources."""
        return {
            "total_sources": len(self._sources),
            "sources_by_identifier": {
                id_type: len(sources)
                for id_type, sources in self._sources_by_identifier.items()
            },
            "source_details": [
                {
                    "name": source.name,
                    "confidence": source.confidence,
                    "supported_identifiers": source.get_supported_identifiers(),
                }
                for source in self._sources.values()
            ],
        }


# Global registry instance
_global_registry = DataSourceRegistry()


def get_registry() -> DataSourceRegistry:
    """Get the global data source registry."""
    return _global_registry


def register_source(source: BaseDataSource) -> None:
    """Register a source with the global registry."""
    _global_registry.register_source(source)
