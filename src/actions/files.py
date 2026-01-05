"""File management operations for Aida."""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Configure logging
logger = logging.getLogger("aida.files")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_files.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class FileExecutor:
    """Handles file system operations safely."""

    def __init__(self):
        self.home_dir = Path.home()
        # file categories for organization
        self.categories = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md"],
            "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
            "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"],
            "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"],
            "Code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".h", ".json", ".xml", ".sh"],
            "Installers": [".deb", ".rpm", ".iso", ".appimage", ".exe", ".msi"],
        }

    def _is_safe_path(self, path: Path) -> bool:
        """Ensure path is within home directory."""
        try:
            # Resolve resolves symlinks and absolute path
            path = path.resolve()
            return str(path).startswith(str(self.home_dir))
        except Exception:
            return False

    def organize_directory(self, dir_name: str) -> str:
        """Organize files in a directory by type."""
        # Handle common names map to actual paths
        common_dirs = {
            "downloads": self.home_dir / "Downloads",
            "documents": self.home_dir / "Documents",
            "desktop": self.home_dir / "Desktop",
            "pictures": self.home_dir / "Pictures",
            "videos": self.home_dir / "Videos",
            "music": self.home_dir / "Music",
            "home": self.home_dir,
        }
        
        target_path = common_dirs.get(dir_name.lower(), self.home_dir / dir_name)
        
        if not target_path.exists():
            return f"Directory '{dir_name}' not found."
            
        if not self._is_safe_path(target_path):
            return "Operation denied: Can only modify files inside your home directory."

        logger.info(f"Organizing directory: {target_path}")
        
        moved_count = 0
        try:
            for item in target_path.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    category = "Others"
                    
                    for cat, extensions in self.categories.items():
                        if ext in extensions:
                            category = cat
                            break
                    
                    # Don't move if it's unknown/misc to avoid mess, 
                    # or strictly organize everything? Let's organize known types.
                    if category == "Others":
                        continue

                    # Create category folder
                    cat_dir = target_path / category
                    cat_dir.mkdir(exist_ok=True)
                    
                    # Move file
                    new_path = cat_dir / item.name
                    
                    # Handle duplicates
                    if new_path.exists():
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_path = cat_dir / f"{item.stem}_{timestamp}{item.suffix}"
                        
                    shutil.move(str(item), str(new_path))
                    moved_count += 1
                    logger.info(f"Moved {item.name} to {category}/")
            
            return f"Organized {dir_name}: Moved {moved_count} files into folders."

        except Exception as e:
            logger.error(f"Error organizing {target_path}: {e}")
            return f"Error organizing directory: {e}"

    def compress_directory(self, dir_name: str) -> str:
        """Compress a directory into a zip file."""
        common_dirs = {
            "downloads": self.home_dir / "Downloads",
            "documents": self.home_dir / "Documents",
            "desktop": self.home_dir / "Desktop",
        }
        
        target_path = common_dirs.get(dir_name.lower(), self.home_dir / dir_name)
        
        if not target_path.exists():
            return f"Directory '{dir_name}' not found."
            
        if not self._is_safe_path(target_path):
            return "Operation denied: Unsafe path."

        timestamp = datetime.now().strftime("%Y%m%d")
        archive_name = f"{target_path.name}_backup_{timestamp}"
        output_path = target_path.parent / archive_name
        
        logger.info(f"Compressing {target_path} to {output_path}.zip")
        
        try:
            shutil.make_archive(str(output_path), 'zip', str(target_path))
            return f"Created archive: {archive_name}.zip in {target_path.parent.name}"
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return f"Compression failed: {e}"

    def rename_file(self, old_name: str, new_name: str, dir_context: str = "Downloads") -> str:
        """Rename a file in a specific directory."""
        # Defaulting to Downloads if not specified for safety context, 
        # or we try to find the file.
        # This is tricky via voice. Let's look in Downloads/Desktop/Home
        
        search_dirs = [
            self.home_dir / "Downloads",
            self.home_dir / "Desktop",
            self.home_dir / "Documents",
            self.home_dir
        ]
        
        target_file = None
        
        # Try to find the file
        for d in search_dirs:
            potential = d / old_name
            if potential.exists() and potential.is_file():
                target_file = potential
                break
        
        if not target_file:
            return f"Could not find file '{old_name}' in Downloads, Desktop, or Documents."
            
        if not self._is_safe_path(target_file):
            return "Operation denied."
            
        new_path = target_file.parent / new_name
        
        try:
            target_file.rename(new_path)
            logger.info(f"Renamed {target_file} to {new_path}")
            return f"Renamed '{old_name}' to '{new_name}'."
        except Exception as e:
            return f"Rename failed: {e}"

    def save_text_to_document(self, content: str, filename: str) -> str:
        """Saves text content to a file in the user's Documents folder."""
        docs_path = self.home_dir / "Documents"
        docs_path.mkdir(exist_ok=True)
        
        # Sanitize filename
        if not filename.endswith((".txt", ".md")):
            filename += ".md" # Default to Markdown for better formatting
        
        output_path = docs_path / filename

        # Handle duplicates
        if output_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(filename)
            output_path = docs_path / f"{base}_{timestamp}{ext}"

        logger.info(f"Saving new document: {output_path}")

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return f"I've saved the document as '{output_path.name}' in your Documents folder."
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return f"Sorry, I couldn't save the document: {e}"
