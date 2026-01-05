"""Window management and screenshot capture for Aida."""

import base64
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Window:
    """Represents an open window."""

    id: str
    name: str
    pid: int | None = None
    is_active: bool = False


class WindowManager:
    """Manage windows and capture screenshots."""

    def __init__(self):
        self._has_spectacle = self._check_tool("spectacle")
        self._has_xdotool = self._check_tool("xdotool")
        self._has_maim = self._check_tool("maim")
        self._has_scrot = self._check_tool("scrot")

    def _check_tool(self, tool: str) -> bool:
        """Check if a system tool is available."""
        try:
            subprocess.run(
                ["which", tool],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def list_windows(self) -> list[Window]:
        """List all open windows."""
        if not self._has_xdotool:
            return []

        windows = []
        try:
            # Get all window IDs
            result = subprocess.run(
                ["xdotool", "search", "--name", "."],
                capture_output=True,
                text=True,
            )

            # Get active window ID
            active_result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
            )
            active_id = active_result.stdout.strip()

            for wid in result.stdout.strip().split("\n"):
                if not wid:
                    continue

                # Get window name
                name_result = subprocess.run(
                    ["xdotool", "getwindowname", wid],
                    capture_output=True,
                    text=True,
                )
                name = name_result.stdout.strip()

                # Skip empty names and desktop
                if not name or name in ("Desktop", "Plasma"):
                    continue

                # Get PID
                pid = None
                try:
                    pid_result = subprocess.run(
                        ["xdotool", "getwindowpid", wid],
                        capture_output=True,
                        text=True,
                    )
                    pid = int(pid_result.stdout.strip())
                except (ValueError, subprocess.CalledProcessError):
                    pass

                windows.append(Window(
                    id=wid,
                    name=name,
                    pid=pid,
                    is_active=(wid == active_id),
                ))

        except subprocess.CalledProcessError:
            pass

        return windows

    def get_active_window(self) -> Window | None:
        """Get the currently focused window."""
        if not self._has_xdotool:
            return None

        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                check=True,
            )
            wid = result.stdout.strip()

            name_result = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True,
                text=True,
            )

            return Window(
                id=wid,
                name=name_result.stdout.strip(),
                is_active=True,
            )
        except subprocess.CalledProcessError:
            return None

    def focus_window(self, window_name: str) -> bool:
        """Focus a window by name (partial match)."""
        if not self._has_xdotool:
            return False

        try:
            # Search for window by name
            result = subprocess.run(
                ["xdotool", "search", "--name", window_name],
                capture_output=True,
                text=True,
            )

            window_ids = result.stdout.strip().split("\n")
            if window_ids and window_ids[0]:
                subprocess.run(
                    ["xdotool", "windowactivate", window_ids[0]],
                    check=True,
                )
                return True
            return False
        except subprocess.CalledProcessError:
            return False

    def capture_desktop(self) -> str | None:
        """Capture full desktop screenshot, return as base64."""
        output_path = Path(f"/tmp/aida_desktop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

        try:
            if self._has_spectacle:
                subprocess.run(
                    ["spectacle", "-b", "-n", "-o", str(output_path)],
                    check=True,
                    capture_output=True,
                )
            elif self._has_maim:
                subprocess.run(
                    ["maim", str(output_path)],
                    check=True,
                    capture_output=True,
                )
            elif self._has_scrot:
                subprocess.run(
                    ["scrot", str(output_path)],
                    check=True,
                    capture_output=True,
                )
            else:
                return None

            # Read and encode as base64
            with open(output_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Clean up temp file
            output_path.unlink()

            return image_data

        except subprocess.CalledProcessError:
            return None

    def capture_window(self, window_id: str | None = None) -> str | None:
        """Capture a specific window or active window, return as base64."""
        output_path = Path(f"/tmp/aida_window_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

        try:
            if window_id is None:
                # Get active window
                if self._has_xdotool:
                    result = subprocess.run(
                        ["xdotool", "getactivewindow"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    window_id = result.stdout.strip()
                else:
                    # Fallback if we don't know the ID (spectacle -a captures active)
                    pass

            if self._has_spectacle:
                # Spectacle -a captures active window
                subprocess.run(
                    ["spectacle", "-b", "-n", "-a", "-o", str(output_path)],
                    check=True,
                    capture_output=True,
                )
            elif self._has_maim:
                if not window_id:
                     return None
                subprocess.run(
                    ["maim", "-i", window_id, str(output_path)],
                    check=True,
                    capture_output=True,
                )
            else:
                return None

            # Read and encode as base64
            with open(output_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Clean up temp file
            output_path.unlink()

            return image_data

        except subprocess.CalledProcessError:
            return None

    def format_window_list(self, windows: list[Window]) -> str:
        """Format window list as readable text."""
        if not windows:
            return "No windows open."

        lines = ["Open windows:"]
        for w in windows:
            active = " (active)" if w.is_active else ""
            lines.append(f"  - {w.name}{active}")

        return "\n".join(lines)

    def is_available(self) -> bool:
        """Check if window management is available."""
        return self._has_xdotool
