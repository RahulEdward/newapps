"""
Property Test: No Chinese Characters in Codebase
=================================================

**Property 21: No Chinese Characters in Codebase**
**Validates: Requirements 14.1-14.8**

This test verifies that all source files in the codebase have been
converted from Chinese to English, excluding:
- i18n.js (internationalization file that intentionally contains Chinese translations)
- venv/ (virtual environment with third-party packages)
- __pycache__/ (compiled Python files)
- .pyc files (compiled Python files)

Author: AI Trader Team
Date: 2026-01-06
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
import pytest


# Chinese character Unicode range
CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')

# Files/directories to exclude from checking
EXCLUDED_PATTERNS = [
    'i18n.js',           # Internationalization file (intentionally has Chinese)
    'venv/',             # Virtual environment
    '__pycache__/',      # Compiled Python
    '.pyc',              # Compiled Python files
    '.git/',             # Git directory
    'node_modules/',     # Node modules
    '.hypothesis/',      # Hypothesis test data
    '.pytest_cache/',    # Pytest cache
]

# File extensions to check
CHECKED_EXTENSIONS = [
    '.py',      # Python source
    '.js',      # JavaScript
    '.html',    # HTML
    '.css',     # CSS
    '.yaml',    # YAML config
    '.yml',     # YAML config
    '.md',      # Markdown
    '.sh',      # Shell scripts
    '.txt',     # Text files
    '.json',    # JSON (excluding package-lock.json)
]


def should_check_file(filepath: str) -> bool:
    """
    Determine if a file should be checked for Chinese characters.
    
    Args:
        filepath: Path to the file
        
    Returns:
        True if file should be checked, False otherwise
    """
    # Check if file matches any excluded pattern
    for pattern in EXCLUDED_PATTERNS:
        if pattern in filepath:
            return False
    
    # Skip package-lock.json (too large, auto-generated)
    if 'package-lock.json' in filepath:
        return False
    
    # Check if file has a checked extension
    for ext in CHECKED_EXTENSIONS:
        if filepath.endswith(ext):
            return True
    
    return False


def find_chinese_in_file(filepath: str) -> List[Tuple[int, str]]:
    """
    Find all lines containing Chinese characters in a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        List of (line_number, line_content) tuples for lines with Chinese
    """
    chinese_lines = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if CHINESE_PATTERN.search(line):
                    chinese_lines.append((line_num, line.strip()[:100]))  # Truncate long lines
    except Exception as e:
        # Skip files that can't be read
        pass
    
    return chinese_lines


def get_all_source_files(root_dir: str) -> List[str]:
    """
    Get all source files in the project directory.
    
    Args:
        root_dir: Root directory to search
        
    Returns:
        List of file paths
    """
    source_files = []
    
    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(
            excl.rstrip('/') == d for excl in EXCLUDED_PATTERNS if excl.endswith('/')
        )]
        
        for filename in files:
            filepath = os.path.join(root, filename)
            if should_check_file(filepath):
                source_files.append(filepath)
    
    return source_files


class TestNoChinese:
    """Test suite for verifying no Chinese characters in codebase."""
    
    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        # Navigate from tests/ to project root
        current_dir = Path(__file__).parent
        return str(current_dir.parent)
    
    def test_no_chinese_in_python_files(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Verify that all Python files have no Chinese characters.
        """
        python_files = [f for f in get_all_source_files(project_root) if f.endswith('.py')]
        
        files_with_chinese = []
        for filepath in python_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = "Found Chinese characters in Python files:\n"
            for filepath, lines in files_with_chinese:
                error_msg += f"\n{filepath}:\n"
                for line_num, content in lines[:5]:  # Show first 5 lines
                    error_msg += f"  Line {line_num}: {content}\n"
            pytest.fail(error_msg)
    
    def test_no_chinese_in_javascript_files(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Verify that all JavaScript files (except i18n.js) have no Chinese characters.
        """
        js_files = [f for f in get_all_source_files(project_root) 
                    if f.endswith('.js') and 'i18n.js' not in f]
        
        files_with_chinese = []
        for filepath in js_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = "Found Chinese characters in JavaScript files:\n"
            for filepath, lines in files_with_chinese:
                error_msg += f"\n{filepath}:\n"
                for line_num, content in lines[:5]:
                    error_msg += f"  Line {line_num}: {content}\n"
            pytest.fail(error_msg)
    
    def test_no_chinese_in_html_files(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Verify that all HTML files have no Chinese characters.
        """
        html_files = [f for f in get_all_source_files(project_root) if f.endswith('.html')]
        
        files_with_chinese = []
        for filepath in html_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = "Found Chinese characters in HTML files:\n"
            for filepath, lines in files_with_chinese:
                error_msg += f"\n{filepath}:\n"
                for line_num, content in lines[:5]:
                    error_msg += f"  Line {line_num}: {content}\n"
            pytest.fail(error_msg)
    
    def test_no_chinese_in_config_files(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Verify that all config files (YAML, etc.) have no Chinese characters.
        """
        config_files = [f for f in get_all_source_files(project_root) 
                        if f.endswith(('.yaml', '.yml'))]
        
        files_with_chinese = []
        for filepath in config_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = "Found Chinese characters in config files:\n"
            for filepath, lines in files_with_chinese:
                error_msg += f"\n{filepath}:\n"
                for line_num, content in lines[:5]:
                    error_msg += f"  Line {line_num}: {content}\n"
            pytest.fail(error_msg)
    
    def test_no_chinese_in_shell_scripts(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Verify that all shell scripts have no Chinese characters.
        """
        shell_files = [f for f in get_all_source_files(project_root) if f.endswith('.sh')]
        
        files_with_chinese = []
        for filepath in shell_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = "Found Chinese characters in shell scripts:\n"
            for filepath, lines in files_with_chinese:
                error_msg += f"\n{filepath}:\n"
                for line_num, content in lines[:5]:
                    error_msg += f"  Line {line_num}: {content}\n"
            pytest.fail(error_msg)
    
    def test_i18n_file_exists_with_chinese(self, project_root):
        """
        Verify that i18n.js exists and contains Chinese translations.
        This is expected behavior - the file should have Chinese for internationalization.
        """
        i18n_path = os.path.join(project_root, 'web', 'i18n.js')
        
        assert os.path.exists(i18n_path), "i18n.js should exist for internationalization"
        
        chinese_lines = find_chinese_in_file(i18n_path)
        assert len(chinese_lines) > 0, "i18n.js should contain Chinese translations"
    
    def test_comprehensive_no_chinese_scan(self, project_root):
        """
        **Feature: llm-tradebot-angelone, Property 21: No Chinese Characters**
        
        Comprehensive scan of all source files for Chinese characters.
        This is the main property test that validates Requirements 14.1-14.8.
        """
        all_files = get_all_source_files(project_root)
        
        files_with_chinese = []
        for filepath in all_files:
            chinese_lines = find_chinese_in_file(filepath)
            if chinese_lines:
                files_with_chinese.append((filepath, chinese_lines))
        
        if files_with_chinese:
            error_msg = f"Found Chinese characters in {len(files_with_chinese)} files:\n"
            for filepath, lines in files_with_chinese:
                rel_path = os.path.relpath(filepath, project_root)
                error_msg += f"\n{rel_path}:\n"
                for line_num, content in lines[:3]:  # Show first 3 lines per file
                    error_msg += f"  Line {line_num}: {content}\n"
                if len(lines) > 3:
                    error_msg += f"  ... and {len(lines) - 3} more lines\n"
            pytest.fail(error_msg)
        
        # If we get here, no Chinese characters found (excluding i18n.js)
        print(f"\n✅ Scanned {len(all_files)} files - no Chinese characters found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
