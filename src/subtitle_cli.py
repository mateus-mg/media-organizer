#!/usr/bin/env python3
"""
CLI helpers for Subtitle Downloader

Reusable functions for subtitle-related CLI commands.
Media Organization System - Subtitle Automation Module
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from src.subtitle_config import SubtitleConfig, get_config
from src.subtitle_downloader import SubtitleDownloader, OpenSubtitlesClient
from src.persistence import OrganizationDatabase
from src.log_config import (
    get_logger,
    log_info,
    log_success,
    log_error,
    log_warning,
    log_stats,
)


console = Console()


# ============================================================================
# MANUAL DOWNLOAD
# ============================================================================

def run_manual_download(
    media_type: Optional[str] = None,
    language: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run manual subtitle download
    
    Args:
        media_type: Filter by media type (movie, tv, etc.)
        language: Specific language to download
        dry_run: Show what would be done
        
    Returns:
        Statistics dictionary
    """
    console.print("\n[bold cyan]Manual Subtitle Download[/bold cyan]\n")
    
    # Initialize components
    config = get_config()
    
    if not config.is_configured:
        console.print("[red]✗ OpenSubtitles API not configured[/red]")
        console.print("Please set credentials in .env:")
        console.print("  - OPENSUBTITLES_API_KEY")
        console.print("  - OPENSUBTITLES_USERNAME")
        console.print("  - OPENSUBTITLES_PASSWORD")
        return {'error': 'Not configured'}
    
    database = OrganizationDatabase(config.database_path)
    logger = get_logger(name="SubtitleCLI")
    downloader = SubtitleDownloader(config, database, logger)
    
    # Authenticate
    console.print("Authenticating with OpenSubtitles...")
    if not downloader.ensure_authenticated():
        console.print("[red]✗ Authentication failed[/red]")
        return {'error': 'Authentication failed'}
    
    console.print("[green]✓ Authenticated successfully[/green]\n")
    
    # Check remaining downloads
    remaining = downloader.client.get_remaining_downloads()
    console.print(f"Downloads remaining today: [yellow]{remaining}/{config.download_limit}[/yellow]\n")
    
    if remaining <= 0:
        console.print("[red]✗ No downloads remaining for today[/red]")
        console.print("Limit resets at midnight.")
        return {'error': 'Rate limit reached'}
    
    # Get files to process
    if media_type:
        console.print(f"Filtering by media type: [cyan]{media_type}[/cyan]")
        files = downloader.get_files_without_subtitles(media_type=media_type)
    else:
        files = downloader.get_files_without_subtitles()
    
    console.print(f"Found [yellow]{len(files)}[/yellow] files without subtitles\n")
    
    if not files:
        console.print("[green]✓ All files have subtitles![/green]")
        return {'subtitles_downloaded': 0, 'files_processed': 0}
    
    # Process files
    stats = {
        'files_processed': 0,
        'subtitles_downloaded': 0,
        'subtitles_skipped': 0,
    }
    
    for i, file_info in enumerate(files, 1):
        if remaining <= 0:
            console.print("\n[red]✗ Rate limit reached[/red]")
            break
        
        metadata = file_info.get('metadata', {})
        title = metadata.get('title', 'Unknown')
        media_type = metadata.get('media_type', 'unknown')
        organized_path = Path(file_info.get('organized_path', ''))
        
        console.print(f"[{i}/{len(files)}] {title} ({media_type})")
        
        if not organized_path.exists():
            console.print(f"  [yellow]⚠ File not found: {organized_path}[/yellow]")
            stats['subtitles_skipped'] += 1
            continue
        
        # Download subtitle
        success = downloader.download_for_file(file_info, organized_path)
        
        if success:
            console.print(f"  [green]✓ Subtitle downloaded[/green]")
            stats['subtitles_downloaded'] += 1
            remaining -= 1
        else:
            console.print(f"  [yellow]⚠ Skipped (no subtitle found)[/yellow]")
            stats['subtitles_skipped'] += 1
        
        stats['files_processed'] += 1
        
        # Small delay
        import time
        time.sleep(0.5)
    
    # Show summary
    console.print("\n" + "=" * 50)
    console.print("[bold]Download Summary[/bold]")
    console.print("=" * 50)
    console.print(f"Files processed:       {stats['files_processed']}")
    console.print(f"Subtitles downloaded:  [green]{stats['subtitles_downloaded']}[/green]")
    console.print(f"Subtitles skipped:     [yellow]{stats['subtitles_skipped']}[/yellow]")
    console.print(f"Downloads remaining:   [cyan]{remaining}[/cyan]")
    console.print("=" * 50)
    
    # Cleanup
    database.close()
    
    return stats


# ============================================================================
# SUBTITLE STATUS
# ============================================================================

def show_subtitle_status(
    show_missing: bool = False,
    show_all: bool = False,
    show_languages: bool = False
) -> Dict[str, Any]:
    """
    Show subtitle statistics
    
    Args:
        show_missing: Only show files without subtitles
        show_all: Show all files with details
        show_languages: Show language breakdown
        
    Returns:
        Statistics dictionary
    """
    console.print("\n[bold cyan]Subtitle Status[/bold cyan]\n")
    
    config = get_config()
    database = OrganizationDatabase(config.database_path)
    
    # Get statistics
    stats = database.get_subtitle_statistics()
    
    # Main statistics table
    table = Table(title="Subtitle Coverage Statistics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Files", str(stats.get('total_files', 0)))
    table.add_row("With Subtitles", f"[green]{stats.get('with_subtitles', 0)}[/green]")
    table.add_row("Without Subtitles", f"[yellow]{stats.get('without_subtitles', 0)}[/yellow]")
    
    coverage = stats.get('coverage_percent', 0)
    coverage_str = f"{coverage:.1f}%"
    if coverage >= 80:
        coverage_str = f"[green]{coverage_str}[/green]"
    elif coverage >= 50:
        coverage_str = f"[yellow]{coverage_str}[/yellow]"
    else:
        coverage_str = f"[red]{coverage_str}[/red]"
    
    table.add_row("Coverage", coverage_str)
    
    console.print(table)
    
    # Language breakdown
    if show_languages and stats.get('languages'):
        console.print("\n[bold]Subtitle Languages[/bold]\n")
        
        lang_table = Table(show_header=True)
        lang_table.add_column("Language", style="cyan")
        lang_table.add_column("Count", style="green")
        
        for lang, count in sorted(stats.get('languages', {}).items(), key=lambda x: x[1], reverse=True):
            lang_table.add_row(lang.upper(), str(count))
        
        console.print(lang_table)
    
    # Files missing subtitles
    if show_missing:
        console.print("\n[bold]Files Missing Subtitles[/bold]\n")
        
        # Get files by priority
        priority_order = ['movie', 'tv', 'dorama', 'anime']
        total_missing = 0
        
        for media_type in priority_order:
            files = database.get_files_without_subtitles(media_type=media_type)
            
            if files:
                console.print(f"\n[cyan]{media_type.upper()}s ({len(files)} files)[/cyan]")
                
                # Show first 10
                for file_info in files[:10]:
                    metadata = file_info.get('metadata', {})
                    title = metadata.get('title', 'Unknown')
                    year = metadata.get('year', '')
                    
                    console.print(f"  • {title} ({year})")
                
                if len(files) > 10:
                    console.print(f"  ... and {len(files) - 10} more")
                
                total_missing += len(files)
        
        if total_missing == 0:
            console.print("[green]✓ All files have subtitles![/green]")
        else:
            console.print(f"\n[yellow]Total: {total_missing} files missing subtitles[/yellow]")
    
    # Show all files
    if show_all:
        console.print("\n[bold]All Files with Subtitles[/bold]\n")
        
        all_media = database.get_all_media()
        
        for media in all_media:
            metadata = media.get('metadata', {})
            subtitles = media.get('subtitles', [])
            
            title = metadata.get('title', 'Unknown')
            media_type = metadata.get('media_type', 'unknown')
            
            if subtitles:
                langs = ', '.join([sub.get('language', 'unknown').upper() for sub in subtitles])
                console.print(f"✓ {title} ({media_type}) - Languages: [green]{langs}[/green]")
            else:
                console.print(f"✗ {title} ({media_type}) - [yellow]No subtitles[/yellow]")
    
    # Cleanup
    database.close()
    
    return stats


# ============================================================================
# SETUP WIZARD
# ============================================================================

def setup_subtitle_config() -> bool:
    """
    Interactive setup wizard for OpenSubtitles
    
    Returns:
        True if setup successful
    """
    console.print("\n[bold cyan]OpenSubtitles Setup Wizard[/bold cyan]\n")
    console.print("This will help you configure OpenSubtitles API credentials.\n")
    
    # Get API key
    console.print("Step 1: Get your API credentials")
    console.print("  1. Visit: https://www.opensubtitles.com/en/consumers")
    console.print("  2. Create an account or login")
    console.print("  3. Go to API section and generate a key\n")
    
    api_key = Prompt.ask("Enter your API Key", password=True)
    username = Prompt.ask("Enter your Username")
    password = Prompt.ask("Enter your Password", password=True)
    
    # Test credentials
    console.print("\nTesting credentials...")
    
    config = SubtitleConfig()
    config.api_key = api_key
    config.api_username = username
    config.api_password = password
    
    client = OpenSubtitlesClient(config)
    
    if client.login():
        console.print("[green]✓ Authentication successful![/green]")
        
        # Get user info
        user_info = client.get_user_info()
        if user_info:
            user = user_info.get('user', {})
            console.print(f"  Logged in as: [cyan]{user.get('username', 'Unknown')}[/cyan]")
        
        # Save to .env
        console.print("\nSaving configuration...")
        
        env_file = Path(".env")
        if env_file.exists():
            # Read existing .env
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Update or add credentials
            import re
            
            if 'OPENSUBTITLES_API_KEY=' in content:
                content = re.sub(
                    r'OPENSUBTITLES_API_KEY=.*',
                    f'OPENSUBTITLES_API_KEY="{api_key}"',
                    content
                )
            else:
                content += f'\nOPENSUBTITLES_API_KEY="{api_key}"'
            
            if 'OPENSUBTITLES_USERNAME=' in content:
                content = re.sub(
                    r'OPENSUBTITLES_USERNAME=.*',
                    f'OPENSUBTITLES_USERNAME="{username}"',
                    content
                )
            else:
                content += f'\nOPENSUBTITLES_USERNAME="{username}"'
            
            if 'OPENSUBTITLES_PASSWORD=' in content:
                content = re.sub(
                    r'OPENSUBTITLES_PASSWORD=.*',
                    f'OPENSUBTITLES_PASSWORD="{password}"',
                    content
                )
            else:
                content += f'\nOPENSUBTITLES_PASSWORD="{password}"'
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            console.print("[green]✓ Configuration saved to .env[/green]")
        else:
            console.print("[yellow]⚠ .env file not found. Please create it manually.[/yellow]")
            console.print("Add these lines to your .env file:")
            console.print(f"  OPENSUBTITLES_API_KEY=\"{api_key}\"")
            console.print(f"  OPENSUBTITLES_USERNAME=\"{username}\"")
            console.print(f"  OPENSUBTITLES_PASSWORD=\"{password}\"")
        
        console.print("\n[green]✓ Setup complete![/green]")
        console.print("You can now use the subtitle downloader.\n")
        
        return True
    else:
        console.print("[red]✗ Authentication failed[/red]")
        console.print("Please check your credentials and try again.")
        return False


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

def test_subtitle_config() -> bool:
    """
    Test OpenSubtitles configuration
    
    Returns:
        True if configuration valid
    """
    console.print("\n[bold cyan]Testing OpenSubtitles Configuration[/bold cyan]\n")
    
    config = get_config()
    
    # Check configuration
    console.print("Checking configuration...")
    
    if not config.is_configured:
        console.print("[red]✗ API credentials not configured[/red]")
        console.print("Run: ./run.sh subtitle-config --setup")
        return False
    
    console.print(f"  API Key: [green]Set[/green]")
    console.print(f"  Username: [green]{config.api_username}[/green]")
    console.print(f"  Languages: [cyan]{', '.join(config.preferred_languages)}[/cyan]")
    console.print(f"  Download limit: [yellow]{config.download_limit}/day[/yellow]")
    
    # Test authentication
    console.print("\nTesting authentication...")
    
    client = OpenSubtitlesClient(config)
    
    if client.login():
        console.print("[green]✓ Authentication successful[/green]")
        
        # Get user info
        user_info = client.get_user_info()
        if user_info:
            user = user_info.get('user', {})
            console.print(f"  Logged in as: [cyan]{user.get('username', 'Unknown')}[/cyan]")
        
        # Check remaining downloads
        remaining = client.get_remaining_downloads()
        console.print(f"  Downloads remaining: [yellow]{remaining}/{config.download_limit}[/yellow]")
        
        console.print("\n[green]✓ Configuration is valid![/green]")
        return True
    else:
        console.print("[red]✗ Authentication failed[/red]")
        console.print("Please check your credentials.")
        return False


# ============================================================================
# DAEMON CONTROL
# ============================================================================

def start_subtitle_daemon() -> bool:
    """
    Start subtitle daemon
    
    Returns:
        True if started successfully
    """
    console.print("\n[bold cyan]Starting Subtitle Daemon...[/bold cyan]\n")
    
    result = subprocess.run(
        ['./subtitle-daemon.sh', 'start'],
        capture_output=True,
        text=True
    )
    
    console.print(result.stdout)
    
    if result.returncode != 0:
        console.print(f"[red]{result.stderr}[/red]")
        return False
    
    return True


def stop_subtitle_daemon() -> bool:
    """
    Stop subtitle daemon
    
    Returns:
        True if stopped successfully
    """
    console.print("\n[bold cyan]Stopping Subtitle Daemon...[/bold cyan]\n")
    
    result = subprocess.run(
        ['./subtitle-daemon.sh', 'stop'],
        capture_output=True,
        text=True
    )
    
    console.print(result.stdout)
    
    if result.returncode != 0:
        console.print(f"[red]{result.stderr}[/red]")
        return False
    
    return True


def restart_subtitle_daemon() -> bool:
    """
    Restart subtitle daemon
    
    Returns:
        True if restarted successfully
    """
    console.print("\n[bold cyan]Restarting Subtitle Daemon...[/bold cyan]\n")
    
    result = subprocess.run(
        ['./subtitle-daemon.sh', 'restart'],
        capture_output=True,
        text=True
    )
    
    console.print(result.stdout)
    
    if result.returncode != 0:
        console.print(f"[red]{result.stderr}[/red]")
        return False
    
    return True


def show_daemon_status() -> bool:
    """
    Show subtitle daemon status
    
    Returns:
        True if daemon is running
    """
    console.print("\n[bold cyan]Subtitle Daemon Status[/bold cyan]\n")
    
    result = subprocess.run(
        ['./subtitle-daemon.sh', 'status'],
        capture_output=True,
        text=True
    )
    
    console.print(result.stdout)
    
    return result.returncode == 0
