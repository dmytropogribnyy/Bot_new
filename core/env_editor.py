#!/usr/bin/env python3
"""Environment variable editor utility"""

from pathlib import Path

try:
    from dotenv import dotenv_values, load_dotenv, set_key, unset_key
except Exception:  # graceful optional dependency
    load_dotenv = None
    dotenv_values = None

    def set_key(*_args, **_kwargs):  # type: ignore
        raise RuntimeError("python-dotenv is required for EnvEditor operations")

    def unset_key(*_args, **_kwargs):  # type: ignore
        raise RuntimeError("python-dotenv is required for EnvEditor operations")


class EnvEditor:
    """Utility for managing .env file"""

    def __init__(self, env_path: Path | None = None):
        if env_path is None:
            self.env_path = Path(__file__).parent.parent / ".env"
        else:
            self.env_path = env_path

        # Create if not exists
        if not self.env_path.exists():
            self.env_path.touch()

        # Load current env
        if load_dotenv is not None:
            try:
                load_dotenv(dotenv_path=self.env_path)
            except Exception:
                pass

    def set(self, key: str, value: str) -> bool:
        """Set or update an environment variable"""
        try:
            set_key(str(self.env_path), key, value)
            return True
        except Exception as e:
            print(f"Error setting {key}: {e}")
            return False

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get an environment variable value"""
        if dotenv_values is None:
            return default
        values = dotenv_values(str(self.env_path))
        return values.get(key, default)

    def delete(self, key: str) -> bool:
        """Delete an environment variable"""
        try:
            unset_key(str(self.env_path), key)
            return True
        except Exception as e:
            print(f"Error deleting {key}: {e}")
            return False

    def get_all(self) -> dict[str, str]:
        """Get all environment variables"""
        if dotenv_values is None:
            return {}
        return dotenv_values(str(self.env_path))  # type: ignore[return-value]

    def exists(self, key: str) -> bool:
        """Check if a key exists"""
        return key in self.get_all()

    def sync_from_example(self) -> int:
        """Sync missing keys from .env.example"""
        example_path = self.env_path.parent / ".env.example"
        if dotenv_values is None or not example_path.exists():
            return 0

        example_vars = dotenv_values(str(example_path))
        current_vars = self.get_all()

        added = 0
        for key in example_vars:
            if key not in current_vars:
                if self.set(key, example_vars[key]):
                    added += 1
                    print(f"Added {key} from .env.example")

        return added


# Convenience functions
def update_env_var(key: str, value: str) -> bool:
    """Quick update of env var"""
    editor = EnvEditor()
    return editor.set(key, value)


def read_env_var(key: str, default: str | None = None) -> str | None:
    """Quick read of env var"""
    editor = EnvEditor()
    return editor.get(key, default)
