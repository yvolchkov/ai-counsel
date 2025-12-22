#!/usr/bin/env python3
"""Health check script to test all enabled models in config.yaml"""
import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.config import load_config, Config
from models.model_registry import ModelRegistry
from adapters import create_adapter

# Suppress verbose logging during health checks
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# Simple test prompt that should work with any model
TEST_PROMPT = "Respond with exactly: 'OK'"


async def test_model(
    adapter_name: str, model_id: str, config: Config, working_dir: str
) -> Dict[str, any]:
    """
    Test a single model by invoking it with a simple prompt.

    Returns:
        dict with keys: adapter, model, success, response, error, duration
    """
    start_time = time.time()
    result = {
        "adapter": adapter_name,
        "model": model_id,
        "success": False,
        "response": None,
        "error": None,
        "duration": 0.0,
    }

    try:
        # Create adapter
        adapter = create_adapter(adapter_name, config.adapters[adapter_name])

        # Invoke with simple prompt
        response = await adapter.invoke(
            model=model_id, prompt=TEST_PROMPT, working_directory=working_dir
        )

        result["success"] = True
        result["response"] = response[:100] if response else None  # Truncate response
        result["duration"] = time.time() - start_time

    except Exception as e:
        result["error"] = str(e)
        result["duration"] = time.time() - start_time

    return result


async def health_check_all_models(
    config_path: str = "config.yaml", adapter_filter: Optional[str] = None
) -> None:
    """Run health checks on all enabled models in config.

    Args:
        config_path: Path to config.yaml file
        adapter_filter: If provided, only test models for this adapter
    """

    # Load config
    config = load_config(config_path)
    registry = ModelRegistry(config)

    # Get current working directory for tools
    working_dir = os.getcwd()

    # Collect all enabled models by adapter
    all_tests = []
    adapters_to_test = {}

    # Determine which adapters to test
    adapter_names = config.adapters.keys()
    if adapter_filter:
        if adapter_filter not in config.adapters:
            print(f"❌ Unknown adapter: {adapter_filter}")
            print(f"   Available adapters: {', '.join(sorted(config.adapters.keys()))}")
            sys.exit(1)
        adapter_names = [adapter_filter]

    for adapter_name in adapter_names:
        enabled_models = registry.list_for_adapter(adapter_name)
        if enabled_models:
            adapters_to_test[adapter_name] = [entry.id for entry in enabled_models]
            for model_id in adapters_to_test[adapter_name]:
                all_tests.append((adapter_name, model_id))

    if not all_tests:
        print("❌ No enabled models found in config.yaml")
        sys.exit(1)

    print(f"🔍 Testing {len(all_tests)} enabled models across {len(adapters_to_test)} adapters...\n")

    # Run tests concurrently (but with some limits to avoid overwhelming APIs)
    results = []
    for adapter_name, model_id in all_tests:
        result = await test_model(adapter_name, model_id, config, working_dir)
        results.append(result)

        # Show progress
        status = "✅" if result["success"] else "❌"
        duration = f"{result['duration']:.2f}s"
        print(f"{status} {adapter_name:12} {model_id:50} {duration}")

        if result["error"]:
            print(f"   Error: {result['error'][:200]}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed:     {len(failed)}/{len(results)}")

    if failed:
        print("\nFailed models:")
        for r in failed:
            print(f"  • {r['adapter']}/{r['model']}")
            print(f"    Error: {r['error'][:200]}")

    # Group by adapter
    print("\nBy adapter:")
    for adapter_name in sorted(adapters_to_test.keys()):
        adapter_results = [r for r in results if r["adapter"] == adapter_name]
        adapter_success = [r for r in adapter_results if r["success"]]
        print(f"  {adapter_name:12} {len(adapter_success)}/{len(adapter_results)} working")

    # Exit code
    sys.exit(0 if len(failed) == 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Health check script to test all enabled models in config.yaml"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--adapter",
        "-a",
        default=None,
        help="Only test models for this adapter (e.g., openai, claude, codex)",
    )
    args = parser.parse_args()
    asyncio.run(health_check_all_models(args.config, args.adapter))
