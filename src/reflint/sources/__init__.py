"""External data source integrations."""

from .base import BaseDataSource, DataSourceError, SourceMetadata
from .registry import DataSourceRegistry, get_registry
from .reliability import SourceReliabilityRegistry, get_reliability_registry
from .fuzzy_matching import FuzzyMatcher, get_fuzzy_matcher

__all__ = [
    "BaseDataSource",
    "DataSourceError",
    "DataSourceRegistry",
    "FuzzyMatcher",
    "SourceMetadata",
    "SourceReliabilityRegistry",
    "get_fuzzy_matcher",
    "get_registry",
    "get_reliability_registry",
]
