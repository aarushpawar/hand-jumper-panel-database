#!/usr/bin/env python
"""
Panel Database CLI

Unified command-line interface for database operations.
"""

import sys
import click
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))


@click.group()
@click.version_option(version='2.0.0')
def cli():
    """Panel Database CLI - Manage webtoon panel database."""
    pass


@cli.command()
def info():
    """Show system information."""
    import sys
    click.echo("\n📦 System Information")
    click.echo("=" * 60)
    click.echo(f"  Python: {sys.version.split()[0]}")
    click.echo(f"  Database version: 2.0")

    # Check dependencies
    click.echo(f"\n📚 Core Dependencies:")
    deps = [
        ('cv2', 'Image processing (OpenCV)'),
        ('numpy', 'Numerical operations'),
        ('PIL', 'Image handling (Pillow)'),
    ]

    for module, description in deps:
        try:
            __import__(module)
            click.echo(f"  ✅ {description}")
        except ImportError:
            click.echo(f"  ❌ {description} - NOT INSTALLED")


if __name__ == '__main__':
    cli()
