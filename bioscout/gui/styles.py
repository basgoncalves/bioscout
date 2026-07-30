"""GUI styling and theme configuration."""

import customtkinter as ctk

# Define color scheme
COLORS = {
    'dark': {
        'bg_primary': '#1e1e1e',
        'bg_secondary': '#2d2d2d',
        'bg_tertiary': '#3d3d3d',
        'fg_primary': '#ffffff',
        'fg_secondary': '#b0b0b0',
        'accent': '#0084ff',
        'accent_hover': '#0066cc',
        'success': '#28a745',
        'warning': '#ffc107',
        'error': '#dc3545',
        'border': '#404040',
    },
    'light': {
        'bg_primary': '#f5f5f5',
        'bg_secondary': '#ffffff',
        'bg_tertiary': '#e8e8e8',
        'fg_primary': '#000000',
        'fg_secondary': '#666666',
        'accent': '#0084ff',
        'accent_hover': '#0066cc',
        'success': '#28a745',
        'warning': '#ffc107',
        'error': '#dc3545',
        'border': '#cccccc',
    }
}


class AppTheme:
    """Application theme manager."""

    def __init__(self, theme: str = 'dark'):
        """
        Initialize theme.

        Args:
            theme: Theme name ('dark' or 'light')
        """
        self.theme = theme
        self.colors = COLORS.get(theme, COLORS['dark'])
        self._configure_ctk_theme()

    def _configure_ctk_theme(self) -> None:
        """Configure CustomTkinter appearance."""
        ctk.set_appearance_mode(self.theme.capitalize())
        ctk.set_default_color_theme("blue")

    def get_color(self, color_name: str) -> str:
        """
        Get color value.

        Args:
            color_name: Name of the color

        Returns:
            Hex color value
        """
        return self.colors.get(color_name, self.colors['fg_primary'])

    def set_theme(self, theme: str) -> None:
        """
        Change theme.

        Args:
            theme: Theme name ('dark' or 'light')
        """
        self.theme = theme
        self.colors = COLORS.get(theme, COLORS['dark'])
        self._configure_ctk_theme()


class WidgetStyles:
    """Widget style configuration."""

    @staticmethod
    def get_frame_style() -> dict:
        """Get standard frame style."""
        return {
            'corner_radius': 8,
            'border_width': 1,
            'border_color': COLORS['dark']['border']
        }

    @staticmethod
    def get_button_style() -> dict:
        """Get standard button style."""
        return {
            'corner_radius': 6,
            'border_width': 0,
            'font': ('Segoe UI', 11)
        }

    @staticmethod
    def get_entry_style() -> dict:
        """Get standard entry style."""
        return {
            'corner_radius': 6,
            'border_width': 1,
            'font': ('Segoe UI', 10)
        }

    @staticmethod
    def get_label_style() -> dict:
        """Get standard label style."""
        return {
            'font': ('Segoe UI', 10)
        }

    @staticmethod
    def get_title_style() -> dict:
        """Get title style."""
        return {
            'font': ('Segoe UI', 14, 'bold')
        }

    @staticmethod
    def get_subtitle_style() -> dict:
        """Get subtitle style."""
        return {
            'font': ('Segoe UI', 12, 'bold')
        }


# Create global theme instance
theme = AppTheme('dark')
