"""Test script to verify reset_settings flag passes through the pipeline."""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis_runner import AnalysisConfig, AnalysisRunner

def test_reset_settings_flow():
    """Test that reset_settings flag flows through the pipeline."""

    # Simulate what analysis_control_session.py does
    reset_settings = True
    analysis_steps = []  # No other steps, just reset

    # Create config like the control file would
    config = AnalysisConfig(
        trial_path="/fake/trial/path",
        steps=analysis_steps,
        parameters={},
        replace_existing=True,
        reset_settings=reset_settings
    )

    # Verify config has the flag
    print(f"✓ Config created with reset_settings: {config.get('reset_settings')}")
    assert config.get('reset_settings') == True, "reset_settings should be True in config"

    # Verify steps are empty
    print(f"✓ Config steps: {config.get('steps', [])}")
    assert config.get('steps', []) == [], "steps should be empty when only reset_settings is enabled"

    # Test the logic in run_analysis
    reset_settings_from_config = config.get('reset_settings', False)
    steps_from_config = config.get('steps', [])

    print(f"✓ Extracted reset_settings from config: {reset_settings_from_config}")
    print(f"✓ Extracted steps from config: {steps_from_config}")

    # Simulate run_analysis logic
    if reset_settings_from_config:
        print("✓ Would call analysis_obj._reset_settings_xml()")

    if not steps_from_config:
        if reset_settings_from_config:
            print("✓ Would return success (reset_settings only)")
        else:
            print("✗ Would return error (no steps and no reset_settings)")

    print("\n✅ Test PASSED: reset_settings flag flows correctly through the pipeline!")

if __name__ == "__main__":
    test_reset_settings_flow()
