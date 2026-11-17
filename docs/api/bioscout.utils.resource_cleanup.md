# `bioscout.utils.resource_cleanup`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py)

Utility for managing system resources during recording/analysis.

## Contents

- [`get_running_apps`](#get_running_apps) — Get list of running resource-heavy applications.
- [`get_system_memory_info`](#get_system_memory_info) — Get current system memory usage.
- [`close_application`](#close_application) — Close an application by process ID.
- [`close_applications`](#close_applications) — Close multiple applications.
- [`get_system_status`](#get_system_status) — Get human-readable system status.

### `get_running_apps`

```python
get_running_apps()
```

Get list of running resource-heavy applications.

  
**Returns**

dict  
    {process_name: (friendly_name, pid, memory_mb)}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py#L39)</sub>

### `get_system_memory_info`

```python
get_system_memory_info()
```

Get current system memory usage.

  
**Returns**

dict  
    {  
        'total_mb': total memory,  
        'available_mb': available memory,  
        'used_mb': used memory,  
        'percent': percentage used  
    }

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py#L71)</sub>

### `close_application`

```python
close_application(pid)
```

| input | type | default |
|---|---|---|
| `pid` | – | required |

Close an application by process ID.

  
**Parameters**

pid : int  
    Process ID to close

  
**Returns**

bool  
    True if successful, False otherwise

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py#L102)</sub>

### `close_applications`

```python
close_applications(app_names)
```

| input | type | default |
|---|---|---|
| `app_names` | – | required |

Close multiple applications.

  
**Parameters**

app_names : list  
    List of application friendly names to close

  
**Returns**

dict  
    {app_name: success_bool}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py#L135)</sub>

### `get_system_status`

```python
get_system_status()
```

Get human-readable system status.

  
**Returns**

str  
    Formatted system status message

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/resource_cleanup.py#L162)</sub>
