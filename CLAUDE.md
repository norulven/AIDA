# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
# Activate virtual environment and run
source .venv/bin/activate && python -m src.main

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run single test
pytest tests/test_config.py -v

# Lint
ruff check src/
```

## Prerequisites

- **Ollama** must be running (default: http://localhost:11434) with:
  - `dolphin-llama3:8b` for text chat
  - `llava:7b` for vision (webcam, screenshots)
- **Piper TTS** voice model must be at `~/.local/share/piper/en_US-amy-medium.onnx`
- **PulseAudio** for audio playback (`paplay`)
- Correct microphone set as default (`pactl set-default-source <device>`)
- **xdotool** and **maim** for window management and screenshots

## Architecture

### Process Isolation

The wake word detection runs in a **separate process** (not thread) to avoid conflicts between faster-whisper and Qt's audio subsystems. Communication uses `multiprocessing.Queue` for events and `multiprocessing.Value` for instant mute control.

### Audio Pipeline

1. **Wake word** (`src/speech/wakeword.py`): Records at 48kHz, resamples to 16kHz for Whisper. Uses callback-based streaming that can abort within 100ms when muted.
2. **STT** (`src/speech/stt.py`): Uses faster-whisper with configurable model size.
3. **TTS** (`src/speech/tts.py`): Pipes `piper-tts` output directly to `paplay` to avoid Python audio library conflicts with Qt.

### Echo Prevention

When Aida speaks, the wake word listener must be muted to prevent self-triggering:
- `speak_async()` sets mute flag before speaking
- Wake word process checks flag every 100ms during recording via callback
- STT listening only starts AFTER TTS completes (not in parallel)
- 1.5 second delay after TTS before resuming listening

### Conversation Flow

1. Wake word detected ("aida") -> enters conversation mode
2. Wake word listener paused, STT starts
3. User speaks -> LLM responds -> TTS speaks
4. After TTS completes, STT resumes listening
5. User says "goodbye"/"bye"/"thanks" -> exits conversation, resumes wake word

### Qt Signal Flow

```
AidaApp (src/main.py)
├── MainWindow.message_sent -> AidaAssistant.process_message
├── AidaAssistant.response_ready -> MainWindow.add_message
├── AidaAssistant.wake_word_detected -> show window, start listening
└── TrayIcon signals for window toggle and quit
```

### Vision Capabilities

- **Webcam**: "What do you see?" / "Hva ser du?" captures webcam and describes with llava
- **Screenshots**: "What's on my screen?" / "Hva er på skjermen?" captures desktop
- **Window listing**: "What windows are open?" / "Hvilke vinduer er åpne?"
- **Window focus**: "Switch to Firefox" / "Bytt til Firefox"

Vision uses `llava:7b` model via `llm.vision_chat()` for single-turn image analysis.

### Key Classes

- `AidaAssistant` (`src/core/assistant.py`): Central controller, orchestrates all components with lazy loading
- `WakeWordListener` (`src/speech/wakeword.py`): QObject wrapper around multiprocessing-based detector
- `OllamaLLM` (`src/ai/llm.py`): Maintains conversation history, supports vision via `vision_chat()`
- `WebFetcher` (`src/actions/fetch.py`): Searches DuckDuckGo and extracts page content for LLM context
- `Camera` (`src/vision/camera.py`): OpenCV webcam capture with base64 encoding
- `WindowManager` (`src/vision/windows.py`): xdotool/maim wrapper for window management and screenshots

## Configuration

Config stored at `~/.config/aida/config.json`. Dataclass-based config in `src/core/config.py` with defaults:
- Ollama model: `dolphin-llama3:8b`
- Vision model: `llava:7b`
- Whisper model: `base`
- Wake word: `aida`
- Piper voice: `en_US-amy-medium`
