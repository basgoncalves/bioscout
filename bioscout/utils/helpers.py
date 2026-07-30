"""
Helper functions for batch processing pipeline
"""

import os
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def setup_logging(log_dir):
    """
    Set up logging configuration for the batch pipeline.

    Args:
        log_dir: Directory for log files

    Returns:
        logger: Configured logger instance
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"batch_{timestamp}.log"

    # Create a unique logger for this batch run
    logger_name = f"batch_{timestamp}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Clear any existing handlers to avoid duplicates
    logger.handlers = []

    # File handler (only timestamped file)
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def plot_motion_results(trial_name, data_file, title, ylabel, results_dir, logger):
    """
    Plot motion analysis results from OpenSim output file.

    Args:
        trial_name: Name of the trial
        data_file: Path to the data file (.mot or .sto)
        title: Plot title
        ylabel: Y-axis label
        results_dir: Directory to save the plot
        logger: Logger instance
    """
    if not HAS_MATPLOTLIB:
        logger.warning(f"Matplotlib not available, skipping plot for {trial_name}")
        return

    try:
        # Load data
        if not os.path.exists(data_file):
            logger.warning(f"Data file not found: {data_file}")
            return

        # Read OpenSim file (skip first 6 rows for headers)
        df = pd.read_csv(data_file, sep='\t', skiprows=6)

        # Create plot
        fig, ax = plt.subplots(figsize=(14, 8))

        # Plot all columns except time
        if 'time' in df.columns:
            time_col = 'time'
        elif 'Time' in df.columns:
            time_col = 'Time'
        else:
            time_col = df.columns[0]

        for col in df.columns:
            if col.lower() != time_col.lower():
                ax.plot(df[time_col], df[col], label=col, alpha=0.7)

        ax.set_xlabel('Time (s)', fontsize=12, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
        ax.set_title(f"{title} - {trial_name}", fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3)

        # Save plot
        plot_file = os.path.join(results_dir, f"{trial_name}_{title.replace(' ', '_').lower()}.png")
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Saved plot: {plot_file}")

    except Exception as e:
        logger.warning(f"Could not create plot for {trial_name}: {e}")


def check_cpu_temperature():
    """
    Check the CPU temperature and log a warning if it exceeds 80°C.
    """
    try:
        import psutil
        if not hasattr(psutil, 'sensors_temperatures'):
            logging.warning("CPU temperature monitoring not available on this system")
            return None
        
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        cpu_temps = temps.get('coretemp', [])
        if not cpu_temps:
            return None

        max_temp = max([t.current for t in cpu_temps])
        if max_temp > 80:
            logging.warning(f"High CPU temperature detected: {max_temp}°C")
        return max_temp
    except Exception as e:
        logging.warning(f"Could not check CPU temperature: {e}")
        return None
    
if __name__ == "__main__":
    import argparse

    # List all available functions
    available_functions = {
        "setup_logging": ("Set up logging configuration", setup_logging),
        "plot_motion_results": ("Plot motion analysis results", plot_motion_results),
        "check_cpu_temperature": ("Check CPU temperature", check_cpu_temperature),
    }

    print("Available functions:")
    for i, (name, (description, _)) in enumerate(available_functions.items(), 1):
        print(f"{i}. {name}: {description}")

    choice = input("\nSelect function by name (or 'exit' to quit): ").strip().lower()

    if choice == "exit":
        print("Exiting...")
    elif choice == "setup_logging":
        log_dir = input("Enter log directory (default: ./logs): ").strip() or "./logs"
        logger = setup_logging(log_dir)
        logger.info("Logging setup complete")
    elif choice == "check_cpu_temperature":
        temp = check_cpu_temperature()
        if temp is not None:
            print(f"Max CPU temperature: {temp}°C")
    else:
        print("Invalid selection")

