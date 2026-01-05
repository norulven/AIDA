"""Edge TTS integration (Microsoft Azure/Windows voices)."""

import asyncio
import subprocess
import tempfile
import os
import edge_tts
import logging

# Configure logging
logger = logging.getLogger("aida.edge_tts")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_tts.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class EdgeTTS:
    """Text-to-speech using Microsoft Edge's online service."""

    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.voice = voice
        logger.info(f"Initialized EdgeTTS with voice: {voice}")

    def speak(self, text: str) -> None:
        """Speak text using Edge TTS and play via mpv."""
        if not text.strip():
            return

        logger.info(f"Speaking: {text}")
        try:
            # Generate audio to temp file
            # We run the async function in a sync wrapper
            asyncio.run(self._generate_and_play(text))
        except Exception as e:
            logger.error(f"EdgeTTS Error: {e}")

    async def _generate_and_play(self, text: str) -> None:
        """Generate audio file and play it."""
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            # Save to file
            await communicate.save(temp_path)
            
            # Play with mpv
            # --no-terminal: suppress output
            # --force-window=no: audio only
            subprocess.run(
                ["mpv", "--no-terminal", "--force-window=no", temp_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Generation/Playback failed: {e}")
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            raise e

    def list_voices(self) -> list[dict]:
        """List available voices."""
        try:
            voices = asyncio.run(edge_tts.list_voices())
            return voices
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
