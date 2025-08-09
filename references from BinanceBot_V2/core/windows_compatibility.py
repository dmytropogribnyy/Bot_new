#!/usr/bin/env python3
"""
Windows Compatibility Module
Simple error handling for Windows compatibility issues
"""

import platform

# Check if we're on Windows
IS_WINDOWS = platform.system() == "Windows"


def is_windows_compatibility_error(error_msg: str) -> bool:
    """Check if error is related to Windows compatibility"""
    if not IS_WINDOWS:
        return False

    windows_errors = [
        "module 'sys' has no attribute 'builtin_module_names'",
        "module 'sys' has no attribute 'maxsize'",
        "module 'sys' has no attribute 'version_info'",
        "module 'sys' has no attribute 'path'",
        "'warnings'",
    ]

    return any(err in str(error_msg) for err in windows_errors)


def handle_windows_compatibility_error(error: Exception, component: str = "UNKNOWN") -> str:
    """Handle Windows compatibility errors gracefully"""
    if is_windows_compatibility_error(str(error)):
        return f"Windows compatibility issue in {component}: {error}"
    return str(error)
