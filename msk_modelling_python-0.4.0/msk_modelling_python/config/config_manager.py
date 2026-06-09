"""Configuration management system for the Powerlifting Model Analysis App."""

import yaml
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
import copy


@dataclass
class ConfigSection:
    """Base class for configuration sections."""
    pass


class ConfigManager:
    """Manages application configuration from YAML files."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file. If None, uses default_config.yaml
        """
        self.app_dir = Path(__file__).parent.parent
        self.config_dir = self.app_dir / "config"
        self.user_config_dir = Path.home() / ".powerlifting_app" / "configs"
        self.user_config_dir.mkdir(parents=True, exist_ok=True)

        if config_path is None:
            self.config_path = self.config_dir / "default_config.yaml"
        else:
            self.config_path = Path(config_path)

        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse configuration file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "analysis.inverse_kinematics")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "analysis.inverse_kinematics")
            value: Value to set
        """
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.

        Args:
            section: Section name (e.g., "analysis")

        Returns:
            Dictionary of configuration values for the section
        """
        return copy.deepcopy(self.config.get(section, {}))

    def update_section(self, section: str, updates: Dict[str, Any]) -> None:
        """
        Update an entire configuration section.

        Args:
            section: Section name
            updates: Dictionary of updates to apply
        """
        if section not in self.config:
            self.config[section] = {}

        self.config[section].update(updates)

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Save configuration to YAML file.

        Args:
            output_path: Path to save configuration. If None, overwrites loaded file.
        """
        if output_path is None:
            output_path = self.config_path
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)

    def save_user_config(self, name: str) -> str:
        """
        Save current configuration as a named user configuration.

        Args:
            name: Name for the configuration

        Returns:
            Path to saved configuration
        """
        # Ensure name has .yaml extension
        if not name.endswith('.yaml'):
            name += '.yaml'

        config_path = self.user_config_dir / name
        self.save(str(config_path))
        return str(config_path)

    def load_user_config(self, name: str) -> None:
        """
        Load a user configuration.

        Args:
            name: Name of the configuration to load
        """
        if not name.endswith('.yaml'):
            name += '.yaml'

        config_path = self.user_config_dir / name
        if not config_path.exists():
            raise FileNotFoundError(f"User configuration not found: {config_path}")

        self.config_path = config_path
        self._load_config()

    def list_user_configs(self) -> list:
        """
        List all available user configurations.

        Returns:
            List of configuration names
        """
        if not self.user_config_dir.exists():
            return []

        configs = [f.stem for f in self.user_config_dir.glob('*.yaml')]
        return sorted(configs)

    def delete_user_config(self, name: str) -> None:
        """
        Delete a user configuration.

        Args:
            name: Name of the configuration to delete
        """
        if not name.endswith('.yaml'):
            name += '.yaml'

        config_path = self.user_config_dir / name
        if config_path.exists():
            config_path.unlink()

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.config_path = self.config_dir / "default_config.yaml"
        self._load_config()

    def to_dict(self) -> Dict[str, Any]:
        """
        Get entire configuration as dictionary.

        Returns:
            Dictionary of configuration
        """
        return copy.deepcopy(self.config)

    def validate(self) -> tuple[bool, list]:
        """
        Validate configuration structure.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required sections
        required_sections = ['analysis', 'processing', 'gui']
        for section in required_sections:
            if section not in self.config:
                errors.append(f"Missing required section: {section}")

        # Check analysis parameters
        if 'analysis' in self.config:
            analysis = self.config['analysis']
            # Add specific validation rules as needed
            if 'muscle_force_scale_factor' in analysis:
                if not isinstance(analysis['muscle_force_scale_factor'], (int, float)):
                    errors.append("muscle_force_scale_factor must be a number")
                elif analysis['muscle_force_scale_factor'] <= 0:
                    errors.append("muscle_force_scale_factor must be positive")

        return len(errors) == 0, errors

    def __repr__(self) -> str:
        return f"ConfigManager(path={self.config_path})"
