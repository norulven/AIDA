# Aida - AI Desktop Assistant for Linux

![Aida Screenshot](aida/screenshots/Screenshot_20260105_171110.png)

**Aida** is a versatile AI desktop assistant designed for Linux, with a focus on KDE Plasma. She provides a voice-activated interface to control your desktop, access information, and automate tasks, running primarily on local resources.

Aida is built with Python and PySide6, leveraging local AI models via Ollama and `faster-whisper` for a private and customizable experience.

## Gallery

| Main Window | Settings Dialog (General) | Settings Dialog (Mail & Calendar) | Settings Dialog (Home Assistant) |
|---|---|---|---|
| ![Main Window](aida/screenshots/Screenshot_20260105_171110.png) | ![Settings General](aida/screenshots/Screenshot_20260105_171211.png) | ![Settings Mail Calendar](aida/screenshots/Screenshot_20260105_171247.png) | ![Settings Home Assistant](aida/screenshots/Screenshot_20260105_171341.png) |

## ✨ Features

- **Voice & Text Interface:** Interact via voice (wake word "Aida") or a modern chat window.
- **Local First AI:**
    - **LLM:** Powered by any model running in **Ollama** (e.g., Llama3, Mistral).
    - **STT:** Local, real-time speech-to-text using **`faster-whisper`**.
    - **TTS:** High-quality, natural-sounding offline text-to-speech with **PiperTTS**, or online with **Microsoft Edge TTS**.
- **Web Intelligence:**
    - **Browser Automation:** Opens pages, performs searches, and fetches information using Playwright.
    - **Web Fetching:** Can read and summarize content from web pages and RSS feeds.
- **System & Desktop Integration:**
    - **Screen Awareness:** Can see and read the content of your active window using vision models.
    - **File Management:** Organize, rename, compress, and create documents in your home directory.
    - **Tray Icon:** Lives in your system tray for easy access.
- **Smart Home & Services:**
    - **Home Assistant:** Control your smart devices (lights, switches) with voice commands.
    - **Mail & Calendar (IMAP/CalDAV):** Check unread emails and view today's calendar events from providers like Gmail.
- **Customizable:** A comprehensive settings dialog allows you to configure models, devices, and integrations.

## 🚀 Getting Started

### Prerequisites

You'll need a working Python environment and a few system dependencies. Aida is designed for Linux and tested on KDE Plasma.

- **Python 3.11+**
- **Ollama:** A running instance of [Ollama](https://ollama.com/) with your desired models pulled (e.g., `ollama pull llama3`, `ollama pull llava`).
- **System Tools:**
    - `spectacle`: For screenshots on KDE.
    - `mpv`: For audio playback (used by Edge TTS).
    - `xdotool` (Optional): For window management features.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/aida.git
    cd aida
    ```

2.  **Run the setup script:**
    The `run.sh` script will create a Python virtual environment, install all dependencies, and launch the application.
    ```bash
    ./run.sh
    ```
    The first time you run this, it will download necessary AI models and libraries, which may take some time.

## 🔧 Configuration

After the first launch, Aida creates a configuration file at `~/.config/aida/config.json`.

You can configure Aida through the **Settings** dialog (accessible from the tray icon). Here you can:
- Select your Ollama models.
- Choose your microphone and speakers.
- Set up **Mail**, **Calendar**, and **Home Assistant** integrations by providing credentials and URLs.
- Enable/disable the wake word listener.

**Important Notes:**
- **Gmail:** For Gmail integration, you must generate an **App Password** as Google no longer allows direct password logins for less secure apps.
- **Home Assistant:** You need to generate a **Long-Lived Access Token** from your Home Assistant profile page.

## 🗣️ Usage

- **Wake Word:** Say "Aida" to activate listening.
- **Mic Button:** Click the microphone icon in the main window or tray to toggle listening.
- **Text Input:** Type commands directly into the chat box.

### Example Commands

- **Web:**
    - "Open vg.no"
    - "Search for the weather in Oslo"
    - "Fetch RSS feed from https://www.nrk.no/toppsaker.rss"
- **System:**
    - "Read this screen"
    - "Organize my Downloads folder"
    - "Save this conversation as a file called 'My Ideas'"
- **Home Assistant:**
    - "Turn on the living room light"
    - "Turn off the fan"
- **Mail & Calendar:**
    - "Check my email"
    - "What's on my calendar today?"

## 🤝 Contributing

Contributions are welcome! If you'd like to add new features or fix bugs, please feel free to fork the repository and submit a pull request.

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.