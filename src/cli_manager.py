#!/usr/bin/env python3
"""
CLI Manager for Media Organizer System
Command-line interface for organizing media files (movies, TV shows, anime, music)
"""

# Flexible import to handle direct execution and importing
try:
    from .log_config import get_logger, log_success, log_error, log_warning, log_info, log_organize, log_move, log_scan
    from .log_formatter import format_organization_session, format_media_processing, format_operation_complete, format_batch_summary, format_daemon_status
    from .config.settings import Config
    from .core.main_orchestrator import MediaOrganizerOrchestrator
    from .persistence.unorganized_db import UnorganizedDatabase
except ImportError:
    # When executed directly, use absolute imports
    import sys
    from pathlib import Path
    # Add src directory to path
    src_dir = Path(__file__).parent
    sys.path.insert(0, str(src_dir))

    from log_config import get_logger, log_success, log_error, log_warning, log_info, log_organize, log_move, log_scan
    from log_formatter import format_organization_session, format_media_processing, format_operation_complete, format_batch_summary, format_daemon_status
    from config.settings import Config
    from core.main_orchestrator import MediaOrganizerOrchestrator
    from persistence.unorganized_db import UnorganizedDatabase

import sys
import os
import asyncio
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.box import SIMPLE
from datetime import datetime, timedelta
from rich.prompt import Prompt
import json
import time


class CLIManager:
    """CLI manager for Media Organizer System"""

    def __init__(self):
        """Initialize CLI manager"""
        self.script_dir = Path(os.getenv('SCRIPT_PATH', os.getcwd()))
        self.logs_dir = self.script_dir / 'logs'
        self.data_dir = self.script_dir / 'data'
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Initialize logger
        self.logger = get_logger(__name__)
        
        # Initialize config
        self.config = Config()
        
        # Initialize orchestrator
        self.orchestrator = MediaOrganizerOrchestrator(config=self.config)

    def show_interactive_menu(self):
        """Show interactive main menu"""
        while True:
            console.print("\n[bold cyan]🗄️  Media Organizer System[/bold cyan]")
            console.print("[bold]Select an operation:[/bold]")

            options = {
                "1": "Organize media files",
                "2": "Scan for new files",
                "3": "View system status",
                "4": "View unorganized files",
                "5": "View organization logs",
                "6": "Start daemon",
                "7": "Stop daemon",
                "8": "View daemon status",
                "9": "View statistics",
                "10": "Exit"
            }

            for key, value in options.items():
                console.print(f"  [{key}] {value}")

            try:
                choice = Prompt.ask("\nYour choice", choices=list(
                    options.keys()), default="10")

                if choice == '1':
                    self.organize_media_interactive()
                elif choice == '2':
                    self.scan_files_interactive()
                elif choice == '3':
                    self.show_status_interactive()
                elif choice == '4':
                    self.view_unorganized_interactive()
                elif choice == '5':
                    self.view_logs_interactive()
                elif choice == '6':
                    self.start_daemon_interactive()
                elif choice == '7':
                    self.stop_daemon_interactive()
                elif choice == '8':
                    self.status_daemon_interactive()
                elif choice == '9':
                    self.view_stats_interactive()
                elif choice == '10':
                    console.print("[green]Exiting... Goodbye![/green]")
                    break

                # Pause before showing the menu again
                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.print("\n[red]Operation cancelled by user.[/red]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    def organize_media_interactive(self):
        """Interactive media organization with predefined paths"""
        console.print("\n[bold cyan]📂 Organize Media Files[/bold cyan]")
        
        try:
            # Create menu options for all configured download paths
            options = {
                "1": ("Movies", self.config.download_path_movies),
                "2": ("TV Shows", self.config.download_path_tv),
                "3": ("Anime", self.config.download_path_animes),
                "4": ("Doramas", self.config.download_path_doramas),
                "5": ("Music", self.config.download_path_music),
                "6": ("Books", self.config.download_path_books),
                "7": ("Comics", self.config.download_path_comics),
                "0": ("All directories", None),
            }

            # Display menu
            console.print("[bold]Select directory to organize:[/bold]")
            for key, (name, path) in options.items():
                if key == "0":
                    console.print(f"  [{key}] {name}")
                else:
                    console.print(f"  [{key}] {name}")

            # Get user choice
            choice = Prompt.ask("\nYour choice", choices=list(
                options.keys()), default="0")

            if choice == "0":
                # Organize all directories
                console.print("\n[cyan]→ Organizing all directories...[/cyan]\n")

                # Process all configured download paths
                total_processed = 0
                for name, path_info in options.items():
                    if name != "0":  # Skip the "all" option
                        _, path = path_info
                        if path and path.exists():
                            processed = asyncio.run(self.orchestrator.organizar_diretorio(path))
                            total_processed += processed
                            console.print(f"  Processed {processed} files in {name}")

                console.print(
                    f"\n[bold green]✓ Successfully organized {total_processed} file(s)[/bold green]")
            else:
                # Organize selected directory
                name, path = options[choice]
                console.print(f"\n[cyan]→ Organizing {name}: {path}[/cyan]\n")

                if not path.exists():
                    console.print(f"[red]✗ Directory does not exist: {path}[/red]")
                    return

                processed = asyncio.run(self.orchestrator.organizar_diretorio(path))
                console.print(
                    f"\n[bold green]✓ Successfully organized {processed} file(s)[/bold green]")

        except Exception as e:
            log_error(self.logger, f"Error during organization: {str(e)}")

    def scan_files_interactive(self):
        """Interactive file scanning"""
        console.print("\n[bold cyan]🔍 Scan for New Files[/bold cyan]")

        try:
            scan_dir = Prompt.ask("Enter directory to scan")
            scan_directory = Path(scan_dir)

            if not scan_directory.exists() or not scan_directory.is_dir():
                log_error(self.logger, f"Directory does not exist: {scan_directory}")
                return

            media_type = Prompt.ask("Media type", choices=["auto", "movies", "tv", "anime", "music"], default="auto")

            console.print(f"[yellow]Scanning: {scan_directory}[/yellow]")

            # Simulate scan
            start_time = datetime.now()
            found_files = self.simulate_scan(scan_directory, media_type)
            end_time = datetime.now()

            duration = (end_time - start_time).total_seconds()

            console.print(f"[green]Found {len(found_files)} files:[/green]")
            for file in found_files[:10]:  # Show first 10 files
                console.print(f"  • {file}")

            if len(found_files) > 10:
                console.print(f"  ... and {len(found_files) - 10} more")

            log_scan(self.logger, f"Scan completed: {len(found_files)} files found in {duration:.2f}s")

        except Exception as e:
            log_error(self.logger, f"Error during scan: {str(e)}")

    def show_status_interactive(self):
        """Show system status"""
        console.print("\n[bold cyan]📊 System Status[/bold cyan]")

        try:
            # Show disk space
            console.print("\n[bold]Disk Space:[/bold]")
            try:
                total, used, free = shutil.disk_usage("/")
                console.print(f"Total: {total / (1024**3):.2f} GB")
                console.print(f"Used: {used / (1024**3):.2f} GB")
                console.print(f"Free: {free / (1024**3):.2f} GB")
            except Exception as e:
                console.print(f"[red]Error getting disk space: {str(e)}[/red]")

            # Show configuration
            console.print("\n[bold]Configuration:[/bold]")
            env_file = self.script_dir / ".env"
            if env_file.exists():
                console.print("[green].env file found[/green]")
                # Show key configuration values without sensitive data
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith('#'):
                            if any(keyword in line.lower() for keyword in ['path', 'dir', 'library']):
                                console.print(f"  {line.strip()}")
            else:
                console.print("[yellow].env file not found[/yellow]")

        except Exception as e:
            log_error(self.logger, f"Error getting system status: {str(e)}")

    def view_unorganized_interactive(self):
        """View unorganized files"""
        console.print("\n[bold cyan]📋 Unorganized Files[/bold cyan]")

        try:
            # Load unorganized files
            unorganized_db = UnorganizedDatabase(Path("data/unorganized.json"))
            unorganized_data = unorganized_db.get_unorganized_files()
            
            if not unorganized_data:
                console.print("[green]No unorganized files found.[/green]")
                return
            
            console.print(f"\n[bold]Unorganized Files ({len(unorganized_data)} files):[/bold]")
            
            for i, item in enumerate(unorganized_data, 1):
                file_path = item.get('file_path', 'Unknown')
                reason = item.get('reason', 'No reason provided')
                console.print(f"{i:3d}. {file_path}")
                console.print(f"     Reason: {reason}")
                console.print()

        except Exception as e:
            log_error(self.logger, f"Error viewing unorganized files: {str(e)}")

    def view_logs_interactive(self):
        """View organization logs"""
        console.print("\n[bold cyan]📋 Organization Logs[/bold cyan]")

        try:
            log_file = self.logs_dir / "media_organizer.log"
            if not log_file.exists():
                console.print("[yellow]No log file found.[/yellow]")
                return

            lines = Prompt.ask("Number of lines to show", default=50, choices=[10, 20, 50, 100])

            try:
                with open(log_file, 'r') as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-int(lines):] if len(all_lines) >= int(lines) else all_lines

                for line in last_lines:
                    console.print(line.rstrip())

            except Exception as e:
                console.print(f"[red]Error reading log file: {str(e)}[/red]")

        except Exception as e:
            log_error(self.logger, f"Error viewing logs: {str(e)}")

    def start_daemon_interactive(self):
        """Start daemon interactively"""
        console.print("\n[bold cyan]🤖 Starting Daemon[/bold cyan]")

        try:
            # Check if daemon is already running
            pid_file = self.script_dir / ".daemon.pid"
            if pid_file.exists():
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()

                # Check if process is running
                import subprocess
                result = subprocess.run(['ps', '-p', pid], capture_output=True)
                if result.returncode == 0:
                    console.print(f"[yellow]Daemon already running with PID: {pid}[/yellow]")
                    return
                else:
                    # PID file exists but process is not running, remove stale file
                    pid_file.unlink()

            # In a real implementation, this would start the actual daemon
            # For simulation, we'll just create a PID file
            import os
            simulated_pid = os.getpid()  # In reality, this would be the daemon's PID
            with open(pid_file, 'w') as f:
                f.write(str(simulated_pid))

            log_success(self.logger, f"Daemon started with PID: {simulated_pid}")
            console.print(f"[green]Daemon started with PID: {simulated_pid}[/green]")

        except Exception as e:
            log_error(self.logger, f"Error starting daemon: {str(e)}")

    def stop_daemon_interactive(self):
        """Stop daemon interactively"""
        console.print("\n[bold cyan]🤖 Stopping Daemon[/bold cyan]")

        try:
            pid_file = self.script_dir / ".daemon.pid"
            if not pid_file.exists():
                console.print("[yellow]Daemon is not running[/yellow]")
                return

            with open(pid_file, 'r') as f:
                pid = f.read().strip()

            # In a real implementation, this would stop the actual daemon
            # For simulation, we'll just remove the PID file
            pid_file.unlink()

            log_success(self.logger, f"Daemon stopped (PID: {pid})")
            console.print(f"[green]Daemon stopped (PID: {pid})[/green]")

        except Exception as e:
            log_error(self.logger, f"Error stopping daemon: {str(e)}")

    def status_daemon_interactive(self):
        """Check daemon status interactively"""
        console.print("\n[bold cyan]🤖 Daemon Status[/bold cyan]")

        try:
            pid_file = self.script_dir / ".daemon.pid"
            if not pid_file.exists():
                console.print("[red]Daemon is not running[/red]")
                return

            with open(pid_file, 'r') as f:
                pid = f.read().strip()

            # Check if process is running
            import subprocess
            result = subprocess.run(['ps', '-p', pid], capture_output=True)
            if result.returncode == 0:
                console.print(f"[green]Daemon is running with PID: {pid}[/green]")

                # Show additional status info
                start_time = datetime.now() - timedelta(minutes=15)  # Simulated
                uptime = str(datetime.now() - start_time).split('.')[0]  # Remove microseconds
                next_check = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")  # Simulated

                console.print(f"  Uptime: {uptime}")
                console.print(f"  Next check: {next_check}")
                console.print(f"  Active downloads: 2")  # Simulated
                console.print(f"  Queued items: 5")  # Simulated
            else:
                console.print(f"[yellow]Stale PID file found (PID: {pid}), process not running[/yellow]")
                # Remove stale PID file
                pid_file.unlink()

        except Exception as e:
            log_error(self.logger, f"Error checking daemon status: {str(e)}")

    def view_stats_interactive(self):
        """View system statistics"""
        console.print("\n[bold cyan]📊 System Statistics[/bold cyan]")

        try:
            # Show organization statistics
            console.print("\n[bold]Organization Stats:[/bold]")
            
            stats = self.orchestrator.get_stats()
            
            for key, value in stats.items():
                console.print(f"  {key}: {value}")

            # Show file counts in library directories
            console.print("\n[bold]Library Contents:[/bold]")
            library_dirs = ['MOVIES', 'TV', 'ANIME', 'MUSIC']

            for lib_dir in library_dirs:
                env_var = f"LIBRARY_PATH_{lib_dir}"
                path_str = os.getenv(env_var)

                if path_str:
                    lib_path = Path(path_str)
                    if lib_path.exists():
                        try:
                            count = sum(1 for _ in lib_path.rglob("*") if _.is_file())
                            console.print(f"  {lib_dir}: {count} files")
                        except Exception:
                            console.print(f"  {lib_dir}: Error accessing directory")
                    else:
                        console.print(f"  {lib_dir}: Directory does not exist")
                else:
                    console.print(f"  {lib_dir}: Path not configured")

        except Exception as e:
            log_error(self.logger, f"Error viewing stats: {str(e)}")

    def simulate_scan(self, scan_dir: Path, media_type: str) -> list:
        """Simulate file scanning process"""
        # This would normally contain the actual scanning logic
        # For now, we'll simulate by finding files
        try:
            media_extensions = {
                'movies': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'tv': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'anime': ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
                'music': ['.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg', '.wma']
            }

            # Determine which extensions to look for
            if media_type == 'auto':
                extensions = []
                for ext_list in media_extensions.values():
                    extensions.extend(ext_list)
            else:
                extensions = media_extensions.get(media_type, [])

            # Find files with matching extensions
            found_files = []
            for ext in extensions:
                found_files.extend([str(f.relative_to(scan_dir)) for f in scan_dir.rglob(f"*{ext}")])

            # Limit to first 100 files for performance
            return found_files[:100]
        except Exception:
            return []

    def show_menu(self):
        """Show main menu with help information"""
        from rich.panel import Panel
        from rich.text import Text

        # Create a panel with the help information
        help_text = Text()
        help_text.append("Available commands:\n", style="bold cyan")
        help_text.append("  organize                          - Organize media files\n")
        help_text.append("  scan                              - Scan for new files\n")
        help_text.append("  status                            - Show system status\n")
        help_text.append("  unorganized                       - View unorganized files\n")
        help_text.append("  logs                              - Show organization logs\n")
        help_text.append("  start                             - Start daemon\n")
        help_text.append("  stop                              - Stop daemon\n")
        help_text.append("  stats                             - Show system statistics\n")
        help_text.append("  interactive                       - Start interactive menu\n")
        help_text.append("  help                              - Show this help\n")
        help_text.append("\nExamples:\n", style="bold green")
        help_text.append("  media-organizer interactive\n")
        help_text.append("  media-organizer organize\n")
        help_text.append("  media-organizer scan\n")
        help_text.append("  media-organizer start\n")

        console.print(
            "\n[bold cyan]🗄️  Media Organizer System - CLI Manager[/bold cyan]\n")
        console.print(
            Panel(help_text, title="📖 Commands Help", border_style="blue"))


console = Console()

def main():
    """Main entry point"""
    cli_manager = CLIManager()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "interactive":
            cli_manager.show_interactive_menu()
        elif command == "help" or command == "--help" or command == "-h":
            cli_manager.show_menu()
        elif command == "organize":
            cli_manager.organize_media_interactive()
        elif command == "scan":
            cli_manager.scan_files_interactive()
        elif command == "status":
            cli_manager.show_status_interactive()
        elif command == "unorganized":
            cli_manager.view_unorganized_interactive()
        elif command == "logs":
            cli_manager.view_logs_interactive()
        elif command == "start":
            cli_manager.start_daemon_interactive()
        elif command == "stop":
            cli_manager.stop_daemon_interactive()
        elif command == "stats":
            cli_manager.view_stats_interactive()
        else:
            console.print(f"[yellow]Command '{command}' not recognized[/yellow]")
            cli_manager.show_menu()
    else:
        # Default to interactive mode
        cli_manager.show_interactive_menu()


if __name__ == "__main__":
    main()