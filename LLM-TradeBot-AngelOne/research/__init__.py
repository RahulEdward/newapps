"""
Research Package - Strategy Research and Development Toolkit

Contains:
- data_explorer: Data exploration and analysis tools
- backtester: Strategy backtesting framework
- workflow: Complete strategy development workflow
"""

from .data_explorer import DataExplorer
from .backtester import Backtester

__all__ = ['DataExplorer', 'Backtester']
