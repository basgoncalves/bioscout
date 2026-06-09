"""Utility for managing system resources during recording/analysis."""

import subprocess
import sys
import psutil
from pathlib import Path

# Common applications that consume significant resources
RESOURCE_HEAVY_APPS = {
    # Browsers
    'chrome.exe': 'Google Chrome',
    'firefox.exe': 'Mozilla Firefox',
    'msedge.exe': 'Microsoft Edge',
    'opera.exe': 'Opera Browser',

    # Media
    'spotify.exe': 'Spotify',
    'vlc.exe': 'VLC Media Player',
    'iTunes.exe': 'iTunes',
    'discord.exe': 'Discord',

    # Office
    'EXCEL.EXE': 'Microsoft Excel',
    'WINWORD.EXE': 'Microsoft Word',
    'POWERPNT.EXE': 'PowerPoint',
    'Outlook.exe': 'Microsoft Outlook',

    # Other
    'slack.exe': 'Slack',
    'zoom.exe': 'Zoom',
    'teams.exe': 'Microsoft Teams',
    'skype.exe': 'Skype',
    'docker.exe': 'Docker',
    'VirtualBox.exe': 'VirtualBox',
    'vmplayer.exe': 'VMware Player',
}


def get_running_apps():
    """Get list of running resource-heavy applications.

    Returns
    -------
    dict
        {process_name: (friendly_name, pid, memory_mb)}
    """
    running_apps = {}

    try:
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                proc_name = proc.info['name'].lower()

                # Check if this is a resource-heavy app
                for exec_name, friendly_name in RESOURCE_HEAVY_APPS.items():
                    if proc_name == exec_name.lower():
                        memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
                        running_apps[friendly_name] = (
                            proc.info['pid'],
                            memory_mb
                        )
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Error scanning processes: {e}")

    return running_apps


def get_system_memory_info():
    """Get current system memory usage.

    Returns
    -------
    dict
        {
            'total_mb': total memory,
            'available_mb': available memory,
            'used_mb': used memory,
            'percent': percentage used
        }
    """
    try:
        memory = psutil.virtual_memory()
        return {
            'total_mb': memory.total / (1024 * 1024),
            'available_mb': memory.available / (1024 * 1024),
            'used_mb': memory.used / (1024 * 1024),
            'percent': memory.percent,
        }
    except Exception as e:
        print(f"Error getting memory info: {e}")
        return {
            'total_mb': 0,
            'available_mb': 0,
            'used_mb': 0,
            'percent': 0,
        }


def close_application(pid):
    """Close an application by process ID.

    Parameters
    ----------
    pid : int
        Process ID to close

    Returns
    -------
    bool
        True if successful, False otherwise
    """
    try:
        if sys.platform == 'win32':
            # Windows: use taskkill
            subprocess.run(
                ['taskkill', '/PID', str(pid), '/F'],
                check=True,
                capture_output=True
            )
        else:
            # Linux/Mac: use kill
            import signal
            import os
            os.kill(pid, signal.SIGTERM)

        return True
    except Exception as e:
        print(f"Error closing process {pid}: {e}")
        return False


def close_applications(app_names):
    """Close multiple applications.

    Parameters
    ----------
    app_names : list
        List of application friendly names to close

    Returns
    -------
    dict
        {app_name: success_bool}
    """
    running_apps = get_running_apps()
    results = {}

    for app_name in app_names:
        if app_name in running_apps:
            pid, memory_mb = running_apps[app_name]
            success = close_application(pid)
            results[app_name] = success
        else:
            results[app_name] = False

    return results


def get_system_status():
    """Get human-readable system status.

    Returns
    -------
    str
        Formatted system status message
    """
    memory = get_system_memory_info()

    status = (
        f"System Memory:\n"
        f"  Total: {memory['total_mb']:.0f} MB\n"
        f"  Available: {memory['available_mb']:.0f} MB\n"
        f"  Used: {memory['used_mb']:.0f} MB ({memory['percent']:.1f}%)"
    )

    running = get_running_apps()
    if running:
        status += f"\n\nRunning Resource-Heavy Apps ({len(running)}):\n"
        for app_name, (pid, memory_mb) in sorted(
            running.items(),
            key=lambda x: x[1][1],
            reverse=True
        ):
            status += f"  {app_name}: {memory_mb:.1f} MB\n"
    else:
        status += "\n\nNo resource-heavy apps detected."

    return status


if __name__ == '__main__':
    # Test the module
    print("System Resource Status:")
    print("=" * 50)
    print(get_system_status())
