#!/usr/bin/env python3
"""Quick smoke test - tests one model per adapter (default models only)"""
import asyncio
import logging
import sys
import os
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.config import load_config
from models.model_registry import ModelRegistry
from adapters import create_adapter

# Suppress verbose logging
logging.basicConfig(level=logging.WARNING)

TEST_PROMPT = "Respond with exactly: 'OK'"


async def quick_smoke_test(config_path: str = "config.yaml") -> None:
    """Test only the default model for each adapter."""

    config = load_config(config_path)
    registry = ModelRegistry(config)
    working_dir = os.getcwd()

    print("🚀 Quick smoke test (default models only)...\n")

    results = []
    for adapter_name in sorted(config.adapters.keys()):
        try:
            # Get default model for this adapter
            default_model = registry.get_default(adapter_name)

            if not default_model:
                print(f"⚠️  {adapter_name:12} No default model configured (skipped)")
                continue

            # Test it
            start_time = time.time()
            adapter = create_adapter(adapter_name, config.adapters[adapter_name])
            response = await adapter.invoke(
                model=default_model, prompt=TEST_PROMPT, working_directory=working_dir
            )

            duration = time.time() - start_time
            print(f"✅ {adapter_name:12} {default_model:50} {duration:.2f}s")
            results.append((adapter_name, True, None))

        except Exception as e:
            duration = time.time() - start_time
            print(f"❌ {adapter_name:12} {default_model or 'unknown':50} {duration:.2f}s")
            print(f"   Error: {str(e)[:200]}")
            results.append((adapter_name, False, str(e)))

    # Summary
    successful = sum(1 for _, success, _ in results if success)
    print(f"\n{'='*80}")
    print(f"✅ {successful}/{len(results)} adapters working")

    failed = [(name, err) for name, success, err in results if not success]
    if failed:
        print(f"\nFailed adapters:")
        for name, err in failed:
            print(f"  • {name}: {err[:200]}")

    sys.exit(0 if len(failed) == 0 else 1)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(quick_smoke_test(config_path))
