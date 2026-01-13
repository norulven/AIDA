"""Main Aida assistant logic."""

import re
import logging
from typing import TYPE_CHECKING
from PySide6.QtCore import QObject, Signal, Slot, QThread

from src.core.config import AidaConfig
from src.ai.llm import OllamaLLM
from src.speech.stt import WhisperSTT
from src.speech.tts import PiperTTS
from src.speech.wakeword import WakeWordListener
from src.actions.browser import BrowserControllerSync
from src.actions.search import WebSearch
from src.actions.fetch import WebFetcher
from src.actions.files import FileExecutor
from src.actions.rss import RSSFetcher
from src.actions.mail import MailClient
from src.actions.calendar import CalendarClient
from src.actions.home_assistant import HomeAssistantClient
from src.actions.food import add_recipe_to_kitchen, get_inventory_list, get_meal_plan, add_meal_to_plan, get_recipes_list, get_recipe_details, import_recipe_from_url, scan_receipt
from src.vision.camera import Camera
from src.vision.windows import WindowManager

# Configure logging
logger = logging.getLogger("aida.assistant")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_assistant.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

if TYPE_CHECKING:
    from src.memory.manager import MemoryManager
    from src.tasks.manager import TaskManager


class SpeechWorker(QThread):
    """Worker thread for speech recognition."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, stt: WhisperSTT, duration: float = 5.0):
        super().__init__()
        self.stt = stt
        self.duration = duration

    def run(self):
        try:
            text = self.stt.record_and_transcribe(self.duration)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))




class AidaAssistant(QObject):
    """Main Aida assistant controller."""

    # Signals
    response_ready = Signal(str)
    status_changed = Signal(str)
    listening_changed = Signal(bool)
    speech_recognized = Signal(str)
    wake_word_detected = Signal()

    def __init__(self, config: AidaConfig = None):
        super().__init__()

        self.config = config or AidaConfig.load()

        # Initialize components (lazy loading)
        self._llm: OllamaLLM | None = None
        self._stt: WhisperSTT | None = None
        self._tts: PiperTTS | None = None
        self._browser: BrowserControllerSync | None = None
        self._fetcher: WebFetcher | None = None
        self._file_executor: FileExecutor | None = None
        self._rss_fetcher: RSSFetcher | None = None
        self._mail_client: MailClient | None = None
        self._calendar_client: CalendarClient | None = None
        self._ha_client: HomeAssistantClient | None = None
        self._wake_word_listener: WakeWordListener | None = None
        self._camera: Camera | None = None
        self._window_manager: WindowManager | None = None

        self._is_listening = False
        self._in_conversation = False  # Track if we're in an active conversation
        self._speech_worker: SpeechWorker | None = None
        self._memory: "MemoryManager | None" = None
        self._tasks: "TaskManager | None" = None

        # Settings
        self.speak_responses = True  # TTS enabled

    @property
    def llm(self) -> OllamaLLM:
        if self._llm is None:
            self._llm = OllamaLLM(self.config.ollama)
            # Register tools
            self._llm.register_tool(add_recipe_to_kitchen)
            self._llm.register_tool(get_inventory_list)
            self._llm.register_tool(get_meal_plan)
            self._llm.register_tool(add_meal_to_plan)
            self._llm.register_tool(get_recipes_list)
            self._llm.register_tool(get_recipe_details)
            self._llm.register_tool(import_recipe_from_url)
            self._llm.register_tool(scan_receipt)
            
            # Register core tools
            self._llm.register_tool(self.web_search)
            self._llm.register_tool(self.get_latest_news)
        return self._llm

    def web_search(self, query: str) -> str:
        """Søker på internett etter svar på et spørsmål eller informasjon.
        
        Args:
            query: Søketermen eller spørsmålet du vil finne svar på.
        """
        return self._fetch_info(query)

    def get_latest_news(self) -> str:
        """Henter de siste nyhetene fra konfigurerte RSS-feeder eller et generelt nyhetssøk."""
        if self.config.rss.enabled and self.config.rss.feeds:
            return self.rss.fetch_all_feeds(self.config.rss.feeds)
        return self._fetch_info("siste nyheter")

    @property
    def stt(self) -> WhisperSTT:
        if self._stt is None:
            self._stt = WhisperSTT(
                self.config.whisper,
                microphone_device=self.config.audio.microphone_device,
            )
        return self._stt

    @property
    def tts(self) -> PiperTTS:
        if self._tts is None:
            self._tts = PiperTTS(
                self.config.piper,
                speaker_device=self.config.audio.speaker_device,
            )
        return self._tts

    @property
    def browser(self) -> BrowserControllerSync:
        if self._browser is None:
            self._browser = BrowserControllerSync()
        return self._browser

    @property
    def fetcher(self) -> WebFetcher:
        if self._fetcher is None:
            self._fetcher = WebFetcher()
        return self._fetcher

    @property
    def file_executor(self) -> FileExecutor:
        if self._file_executor is None:
            self._file_executor = FileExecutor()
        return self._file_executor

    @property
    def rss(self) -> RSSFetcher:
        if self._rss_fetcher is None:
            self._rss_fetcher = RSSFetcher()
        return self._rss_fetcher

    @property
    def mail(self) -> MailClient:
        if self._mail_client is None:
            self._mail_client = MailClient(self.config.mail)
        return self._mail_client

    @property
    def calendar(self) -> CalendarClient:
        if self._calendar_client is None:
            self._calendar_client = CalendarClient(self.config.mail)
        return self._calendar_client

    @property
    def ha(self) -> HomeAssistantClient:
        if self._ha_client is None:
            self._ha_client = HomeAssistantClient(self.config.ha)
        return self._ha_client

    @property
    def camera(self) -> Camera:
        if self._camera is None:
            self._camera = Camera(self.config.camera)
        return self._camera

    @property
    def window_manager(self) -> WindowManager:
        if self._window_manager is None:
            self._window_manager = WindowManager()
        return self._window_manager

    @property
    def memory(self) -> "MemoryManager":
        """Access memory manager (lazy initialization)."""
        if self._memory is None and self.config.memory.enabled:
            from src.memory.manager import MemoryManager
            self._memory = MemoryManager(
                data_dir=self.config.memory.data_dir,
                cache_dir=self.config.memory.cache_dir
            )
            self._memory.get_or_create_session()
        return self._memory

    @property
    def tasks(self) -> "TaskManager":
        """Access task manager (lazy initialization)."""
        if self._tasks is None and self.config.tasks.enabled:
            from src.tasks.manager import TaskManager
            # Use memory's database if available
            db = self._memory._db if self._memory else None
            if db is None and self.config.memory.enabled:
                # Initialize memory to get database
                _ = self.memory
                db = self._memory._db
            self._tasks = TaskManager(db)
            self._tasks.task_reminder.connect(self._on_task_reminder)
            self._tasks.start_reminder_service()
        return self._tasks

    @Slot(object)
    def _on_task_reminder(self, task) -> None:
        """Handle task reminder."""
        message = f"Reminder: {task.title}"
        if task.due_date:
            message += f", due soon"

        self.status_changed.emit(f"Task reminder: {task.title}")
        self.response_ready.emit(message)

        if self.speak_responses and self.config.tasks.speak_reminders:
            self.speak_async(message)

    @Slot(bool)
    def set_wake_word_enabled(self, enabled: bool) -> None:
        """Enable or disable wake word listening."""
        self.config.wake_word_enabled = enabled
        self.config.save()
        
        if enabled:
            self.start_wake_word_listener()
        else:
            self.stop_wake_word_listener()

    def start_wake_word_listener(self) -> None:
        """Start listening for wake word in background."""
        if not self.config.wake_word_enabled:
            return

        if self._wake_word_listener is not None:
            return

        self._wake_word_listener = WakeWordListener(
            wake_word=self.config.wake_word,
            model_size="base",  # Use base model for better accuracy
            microphone_device=self.config.audio.microphone_device,
        )
        self._wake_word_listener.wake_word_detected.connect(self._on_wake_word)
        self._wake_word_listener.error.connect(self._on_wake_word_error)
        self._wake_word_listener.start()
        self.status_changed.emit(f"Listening for '{self.config.wake_word}'...")

    def stop_wake_word_listener(self) -> None:
        """Stop wake word listener."""
        if self._wake_word_listener:
            self._wake_word_listener.stop()
            self._wake_word_listener = None

    @Slot()
    def _on_wake_word(self) -> None:
        """Handle wake word detection."""
        self.wake_word_detected.emit()
        self._in_conversation = True

        # Pause wake word listener while in conversation
        if self._wake_word_listener:
            self._wake_word_listener.pause()

        # Start listening for command
        self.start_listening()

    @Slot(str)
    def _on_wake_word_error(self, error: str) -> None:
        """Handle wake word listener error."""
        self.status_changed.emit(f"Wake word error: {error}")

    def process_message(self, message: str, speak: bool = True) -> str:
        """Process a user message and return response.
        
        Args:
            message: The user's input text.
            speak: Whether to speak the response aloud (server-side).
        """
        # Ensure we aren't listening while processing/speaking
        self.stop_listening()
        
        logger.info(f"Processing message: '{message}'")
        self.status_changed.emit("Thinking...")

        # Check for conversation end commands
        if self._check_end_conversation(message):
            return self._end_conversation(speak=speak)

        # Get memory context before processing
        if self.config.memory.enabled and self._memory is not None:
            memory_context = self.memory.get_context_for_message(
                message,
                include_semantic=self.config.memory.include_semantic_context,
                max_semantic_results=self.config.memory.max_semantic_results
            )
            self.llm.set_memory_context(memory_context if memory_context else None)

        # Check for task commands first (handles "remind me to...")
        if self.config.tasks.enabled:
            task_response = self._check_task_commands(message)
            if task_response:
                self.status_changed.emit("Ready")
                self.response_ready.emit(task_response)
                if self.speak_responses and speak:
                    self.speak_async(task_response, continue_listening=self._in_conversation)
                return task_response

        # Check for special commands
        action_response = self._check_for_actions(message)
        if action_response:
            response = action_response
        else:
            # Get LLM response
            response = self.llm.chat(message)

        # Store interaction in memory
        if self.config.memory.enabled and self._memory is not None:
            self.memory.add_interaction(message, response)

        self.status_changed.emit("Ready")
        self.response_ready.emit(response)

        # Speak the response (and continue listening after if in conversation)
        if self.speak_responses and speak:
            self.speak_async(response, continue_listening=self._in_conversation)
        elif self._in_conversation and speak:
            # No TTS, start listening immediately
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, self.start_listening)

        return response

    def _check_end_conversation(self, message: str) -> bool:
        """Check if user wants to end the conversation."""
        end_phrases = [
            "goodbye", "bye", "that's all", "thank you", "thanks",
            "end conversation", "stop", "quit", "exit", "done",
            "that will be all", "nevermind", "never mind",
        ]
        message_lower = message.lower().strip()
        return any(phrase in message_lower for phrase in end_phrases)

    def _end_conversation(self, speak: bool = True) -> str:
        """End the current conversation."""
        self._in_conversation = False

        # Resume wake word listener
        if self._wake_word_listener:
            self._wake_word_listener.resume()

        # Clear conversation history for fresh start
        self.llm.clear_history()
        self.llm.set_memory_context(None)

        # Start new memory session for next conversation
        if self.config.memory.enabled and self._memory is not None:
            self.memory.start_session()

        response = "Goodbye! Say 'Aida' when you need me again."
        self.response_ready.emit(response)

        if self.speak_responses and speak:
            self.speak_async(response)

        self.status_changed.emit(f"Listening for '{self.config.wake_word}'...")
        return response

    def _check_task_commands(self, message: str) -> str | None:
        """Check for task management voice commands."""
        from src.tasks.voice_patterns import TaskVoiceParser
        from src.tasks.models import Priority

        parser = TaskVoiceParser()
        cmd = parser.parse(message)

        if cmd is None:
            return None

        if cmd.action == "add":
            task = self.tasks.add_task(
                title=cmd.title,
                priority=cmd.priority,
                due_date=cmd.due_date,
                project=cmd.project,
                reminder=cmd.reminder,
                sync_to_ha=cmd.ha_list,
            )
            response = f"Added task: {task.title}"
            if task.priority == Priority.HIGH:
                response += " (high priority)"
            if task.due_date:
                response += f", due {self.tasks._format_due_date(task.due_date)}"
            if task.ha_list_name:
                response += f". Added to {task.ha_list_name}."
            return response

        elif cmd.action == "complete":
            task = self.tasks.complete_task(title=cmd.title)
            if task:
                return f"Done! Completed: {task.title}"
            return f"I couldn't find a task matching '{cmd.title}'"

        elif cmd.action == "list":
            if cmd.filter_priority:
                tasks = self.tasks.list_tasks(priority=cmd.filter_priority)
                if not tasks:
                    return f"You have no {cmd.filter_priority.value} priority tasks."
            return self.tasks.get_task_summary()

        return None

    def _check_for_actions(self, message: str) -> str | None:
        """Check if the message contains actionable commands."""
        message_lower = message.lower()

        # Read screen text command
        read_screen_patterns = [
            r"read (?:this )?(?:text|window|page|screen|article)",
            r"les (?:dette )?(?:tekst|vindu|side|skjerm|artikkel)",
            r"read what(?:'s| is) on (?:the )?screen",
            r"hva står det",
        ]

        for pattern in read_screen_patterns:
            if re.search(pattern, message_lower):
                return self._read_screen_text()

        # Vision/webcam commands
        vision_patterns = [
            r"what do you see",
            r"hva ser du",
            r"can you see me",
            r"do you see me",
            r"look at me",
            r"se på meg",
            r"describe me",
            r"what am i wearing",
            r"what do i look like",
            r"see me",
            r"use.* camera",
            r"use.* webcam",
            r"take.* photo",
            r"take.* picture",
            r"ser du meg",
            r"beskriv meg",
        ]

        for pattern in vision_patterns:
            if re.search(pattern, message_lower):
                return self._describe_webcam()

        # Screenshot/screen commands
        screen_patterns = [
            r"what(?:'s| is) on (?:my |the )?screen",
            r"hva er på skjermen",
            r"show me (?:my |the )?screen",
            r"describe (?:my |the )?screen",
            r"take a screenshot",
            r"ta et skjermbilde",
        ]

        for pattern in screen_patterns:
            if re.search(pattern, message_lower):
                return self._describe_screen()

        # Window listing commands
        window_list_patterns = [
            r"what (?:windows?|apps?) (?:are |is )?open",
            r"hvilke vinduer er åpne",
            r"list (?:open )?windows",
            r"show (?:open )?windows",
        ]

        for pattern in window_list_patterns:
            if re.search(pattern, message_lower):
                return self._list_windows()

        # Window focus commands
        focus_patterns = [
            r"(?:switch to|focus|open|go to) (.+?) (?:window|app)",
            r"bytt til (.+)",
        ]

        for pattern in focus_patterns:
            match = re.search(pattern, message_lower)
            if match:
                app_name = match.group(1).strip()
                return self._focus_window(app_name)

        # File management commands
        # Organize
        organize_pattern = r"organize (?:my )?(\w+)(?: folder| directory)?"
        match = re.search(organize_pattern, message_lower)
        if match:
            target = match.group(1).strip()
            return self.file_executor.organize_directory(target)

        # Compress
        compress_pattern = r"compress (?:my )?(\w+)(?: folder| directory)?"
        match = re.search(compress_pattern, message_lower)
        if match:
            target = match.group(1).strip()
            return self.file_executor.compress_directory(target)

        # Rename
        rename_pattern = r"rename (?:file )?(.+) to (.+)"
        match = re.search(rename_pattern, message_lower)
        if match:
            old_name = match.group(1).strip()
            new_name = match.group(2).strip()
            return self.file_executor.rename_file(old_name, new_name)
            
        # Save last response
        save_last_pattern = r"save (?:this|that|it) as (?:a )?(?:file|document|note) (?:called|named)? (.+)"
        match = re.search(save_last_pattern, message_lower)
        if match:
            filename = match.group(1).strip()
            return self._save_last_response(filename)

        # Research and save
        research_save_pattern = r"research and save (.+) as (.+)"
        match = re.search(research_save_pattern, message_lower)
        if match:
            topic = match.group(1).strip()
            filename = match.group(2).strip()
            return self._research_and_save(topic, filename)

        # "Get latest news" - use configured RSS feeds
        news_patterns = [
            r"(?:get|fetch|check|read|show)(?: me)?(?: the)? (?:latest |recent )?news",
            r"(?:latest|recent) news",
            r"what(?:'s| is) (?:the )?(?:latest |recent )?news",
            r"(?:hva|vis)(?: er)?(?: siste)? nyhet(?:er|ene)?",
            r"siste nytt",
            r"check my feeds",
            r"read my feeds",
        ]

        for pattern in news_patterns:
            if re.search(pattern, message_lower):
                # Use configured feeds if available
                if self.config.rss.enabled and self.config.rss.feeds:
                    self.status_changed.emit("Fetching news feeds...")
                    return self.rss.fetch_all_feeds(self.config.rss.feeds)
                # Fall through to web search if no feeds configured
                break

        # RSS feed command (specific URL)
        rss_pattern = r"(?:fetch|get|check|åpne) (?:the )?rss (?:feed )?(?:from |at )?(\S+)"
        match = re.search(rss_pattern, message_lower)
        if match:
            url = match.group(1).strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            return self.rss.fetch_feed(url)

        # Mail commands
        check_mail_pattern = r"(?:check|read|show) (?:my )?(?:mail|emails?|inbox)"
        match = re.search(check_mail_pattern, message_lower)
        if match:
            return self._check_emails()

        # Calendar commands
        check_calendar_pattern = r"what(?:'s|s| is) on my (?:calendar|agenda|schedule) (?:for )?today"
        match = re.search(check_calendar_pattern, message_lower)
        if match:
            return self._check_calendar()

        # Home Assistant commands
        if self.config.ha.enabled:
            # List devices
            ha_list_pattern = r"(?:list|show) (?:all )?(?:ha|home assistant) (?:devices|entities)"
            if re.search(ha_list_pattern, message_lower):
                return self._list_ha_devices()

            # Check state/status (Boolean check: "Is X on?")
            # Matches: "Is kitchen light on?", "Is the garage door open?"
            ha_check_bool_pattern = r"^is (?:the )?(.+) (on|off|open|closed|locked|unlocked)\?*$"
            match = re.search(ha_check_bool_pattern, message_lower)
            if match:
                 device = match.group(1).strip()
                 expected_state = match.group(2).strip()
                 return self._check_ha_device_state(device, expected_state)

            # Check general status
            # Matches: "What's the temperature in X", "Check status of X", "How is X"
            ha_status_patterns = [
                r"(?:what(?:'s|\s+is)|check) (?:the )?(?:status|state|temperature|humidity|level) (?:of|for|in|at) (?:the )?(.+)",
                r"(?:what(?:'s|\s+is)|check) (?:the )?(.+) (?:status|state|temperature|humidity|level)",
                r"how is (?:the )?(.+)(?: doing)?\?*$"
            ]
            
            for pattern in ha_status_patterns:
                match = re.search(pattern, message_lower)
                if match:
                     device = match.group(1).strip()
                     return self._check_ha_device_state(device)

            # Control commands
            # Matches: "Turn on X", "Turn X on", "Switch off X"
            ha_control_patterns = [
                r"(?:turn|switch) (on|off) (?:the )?(.+)",
                r"(?:turn|switch) (?:the )?(.+) (on|off)"
            ]
            
            for pattern in ha_control_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    # Group ordering depends on pattern
                    if match.lastindex == 2:
                        # Pattern 1: command (1) device (2) OR Pattern 2: device (1) command (2)
                        if pattern == ha_control_patterns[0]:
                            state = match.group(1).strip()
                            device_name = match.group(2).strip()
                        else:
                            device_name = match.group(1).strip()
                            state = match.group(2).strip()
                        return self._control_ha_device(device_name, state)

        # Fetch/lookup command (without opening browser)
        fetch_patterns = [
            r"(?:fetch|get|retrieve|find) (?:info(?:rmation)? (?:about|on) )?(.+)",
            r"what(?:'s|\s+is|\s+are|\s+s) (.+)",
            r"tell me about (.+)",
            r"explain (.+)",
            r"give me (.+)",
            r"(?:latest|current) news (?:about|on|from) (.+)",
        ]

        for pattern in fetch_patterns:
            match = re.search(pattern, message_lower)
            if match:
                query = match.group(1).strip()
                # Only use fetch for factual queries, let LLM handle conversational
                if len(query.split()) <= 5:  # Short factual queries
                    return self._fetch_info(query)

        # Search command (opens browser)
        search_patterns = [
            r"search (?:for |the web for )?(.+)",
            r"look up (.+)",
            r"google (.+)",
            r"open (?:a )?search for (.+)",
            r"søk (?:etter )?(.+)",
            r"finn (.+)",
        ]

        for pattern in search_patterns:
            match = re.search(pattern, message_lower)
            if match:
                query = match.group(1)
                return self._perform_search(query)

        # Close browser command
        close_browser_patterns = [
            r"close (?:the )?browser",
            r"close (?:the )?window",
            r"exit browser",
            r"lukk browser(?:en)?",
            r"lukk nettleser(?:en)?",
            r"lukk vindu(?:et)?",
            r"steng browser(?:en)?",
        ]

        for pattern in close_browser_patterns:
            if re.search(pattern, message_lower):
                return self._close_browser()

        # Generic Open Browser command (no URL)
        open_browser_patterns = [
            r"open (?:the |my )?browser",
            r"open firefox",
            r"open chrome",
            r"open internet",
            r"åpne (?:nett)?leser(?:en)?",
            r"åpne firefox",
            r"start browser",
        ]

        for pattern in open_browser_patterns:
             if re.fullmatch(pattern, message_lower) or (re.search(pattern, message_lower) and len(message_lower.split()) <= 4):
                 return self._open_url("https://google.com")

        # Open URL command
        url_patterns = [
            r"(?:open|go to|navigate to) (https?://\S+)",
            r"(?:open|go to|navigate to) (.+)",
            r"(?:åpne|gå til|naviger til) (https?://\S+)",
            r"(?:åpne|gå til|naviger til) (.+)",
        ]

        for pattern in url_patterns:
            match = re.search(pattern, message_lower)
            if match:
                target = match.group(1).strip()
                target = self._clean_url(target)
                
                # Check if it looks like a URL
                if "." in target and " " not in target:
                    return self._open_url(target)
                else:
                    # Fallback to search
                    return self._perform_search(target)

        return None

    def _clean_url(self, text: str) -> str:
        """Clean up potential URL from speech text."""
        # Remove trailing punctuation
        text = text.rstrip(".!?")
        
        # Replace spoken dots
        text = text.replace(" dot ", ".").replace(" punktum ", ".")
        text = text.replace(" dot", ".").replace(" punktum", ".")
        
        # Fix spaces around dots (e.g. "vg . no" -> "vg.no")
        text = re.sub(r'\s*\.\s*', '.', text)
        
        # Fix common TLD spaces (e.g. "google com" -> "google.com")
        common_tlds = ["com", "org", "net", "edu", "gov", "no", "se", "dk", "uk", "de"]
        for tld in common_tlds:
             if text.endswith(f" {tld}"):
                 text = text[:-len(tld)-1] + f".{tld}"
        
        return text

    def _fetch_and_summarize(self, query: str) -> str:
        """Fetch information from the web and return a summary string."""
        self.status_changed.emit(f"Fetching info about: {query}")
        try:
            results = self.fetcher.search_duckduckgo(query, num_results=2)
            if not any(r.success for r in results):
                return f"Sorry, I couldn't find information about '{query}'."
            context = self.fetcher.summarize_for_llm(results)
            return context
        except Exception as e:
            return f"Sorry, an error occurred while fetching: {e}"

    def _fetch_info(self, query: str) -> str:
        """Fetch information, then ask LLM to provide a concise summary."""
        context = self._fetch_and_summarize(query)
        if context.startswith("Sorry"):
            return context

        prompt = f"""Based on the information provided below, answer the following question: "{query}"

Information:
{context}

Instructions:
1. If the answer is contained in the information above, provide a concise summary.
2. If the information does NOT contain the answer or is irrelevant, state clearly: "I could not find information about '{query}' in the search results."
3. Do NOT make up facts or use outside knowledge to fill in gaps. Only use the provided information."""
        
        logger.info(f"Sending prompt to LLM (Context length: {len(context)})")
        response = self.llm.chat(prompt)
        return response

    def _close_browser(self) -> str:
        """Close the browser."""
        self.status_changed.emit("Closing browser...")
        try:
            self.browser.stop()
            return "I've closed the browser."
        except Exception as e:
            return f"Sorry, I encountered an error closing the browser: {e}"

    def _perform_search(self, query: str) -> str:
        """Perform a web search in browser."""
        self.status_changed.emit(f"Searching for: {query}")

        try:
            self.browser.search(query)
            return f"I've searched for '{query}' in your browser."
        except Exception as e:
            return f"Sorry, I couldn't perform the search: {e}"

    def _open_url(self, url: str) -> str:
        """Open a URL in the browser."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        self.status_changed.emit(f"Opening: {url}")

        try:
            self.browser.navigate(url)
            return f"I've opened {url} in your browser."
        except Exception as e:
            return f"Sorry, I couldn't open the URL: {e}"

    def _read_screen_text(self) -> str:
        """Capture screen and extract text to read aloud."""
        self.status_changed.emit("Reading screen...")

        try:
            # Capture active window preferably, or desktop
            image_base64 = self.window_manager.capture_window() or self.window_manager.capture_desktop()

            if not image_base64:
                return "Sorry, I couldn't see the screen to read it."

            # Ask vision model to extract text
            prompt = "Read the text in this image. Output ONLY the text content, do not describe the image."
            
            text = self.llm.vision_chat(prompt, [image_base64])
            
            if not text.strip():
                return "I couldn't find any readable text."
                
            return f"Here is what I found: {text}"

        except Exception as e:
            return f"Sorry, I couldn't read the screen: {e}"

    def _check_emails(self) -> str:
        """Fetch and summarize unread emails."""
        self.status_changed.emit("Checking emails...")
        if not self.config.mail.enabled:
            return "Mail integration is not enabled in settings."
        
        try:
            emails = self.mail.get_unread_emails()
            if not emails:
                return "You have no unread emails."
            
            summary = ["You have new emails:"]
            for email_data in emails:
                summary.append(f"From: {email_data['from']}")
                summary.append(f"Subject: {email_data['subject']}")
                summary.append(f"Snippet: {email_data['body_snippet']}")
                summary.append("---")
            return "\n".join(summary)
        except Exception as e:
            return f"Sorry, I couldn't check your emails: {e}"

    def _check_calendar(self) -> str:
        """Fetch and summarize today's calendar events."""
        self.status_changed.emit("Checking calendar...")
        if not self.config.mail.calendar_enabled:
            return "Calendar integration is not enabled in settings."
        
        try:
            events = self.calendar.get_todays_events()
            if not events:
                return "You have no events on your calendar for today."
            
            summary = ["Here's what's on your calendar today:"]
            for event in events:
                time = f"at {event['start_time']}" if event['start_time'] else "(all day)"
                summary.append(f"- {event['summary']} {time}")
            return "\n".join(summary)
        except Exception as e:
            return f"Sorry, I couldn't check your calendar: {e}"

    def _control_ha_device(self, device_name: str, state: str) -> str:
        """Controls a Home Assistant device."""
        self.status_changed.emit(f"Controlling {device_name}...")
        if not self.config.ha.enabled:
            return "Home Assistant integration is not enabled in settings."

        # Find entity by friendly name
        entity_id = self.ha.find_entity_by_name(device_name)
        if not entity_id:
            return f"Sorry, I couldn't find a device named '{device_name}'."
            
        domain = entity_id.split('.')[0]
        service = f"turn_{state}" # turn_on or turn_off
        
        # Check if service is valid for domain
        if domain in ["light", "switch", "fan"]:
            if self.ha.call_service(domain, service, {"entity_id": entity_id}):
                return f"Okay, I've turned {state} the {device_name}."
            else:
                return f"Sorry, I failed to turn {state} the {device_name}."
        else:
            return f"I found the {device_name}, but I don't know how to turn it {state}."

    def _list_ha_devices(self) -> str:
        """Lists available Home Assistant devices."""
        self.status_changed.emit("Listing Home Assistant devices...")
        if not self.config.ha.enabled:
            return "Home Assistant integration is not enabled."

        entities = self.ha.get_all_entities()
        if not entities:
            return "I couldn't find any entities or couldn't connect to Home Assistant."

        # Filter for interesting domains
        interesting_domains = ["light", "switch", "sensor", "binary_sensor", "climate", "lock", "cover", "media_player"]
        filtered = [e for e in entities if e.get('domain') in interesting_domains]
        
        if not filtered:
             return "I connected, but found no interesting devices to control."

        # Group by domain
        summary = ["Here are some devices I found:"]
        by_domain = {}
        for e in filtered:
            d = e.get('domain')
            if d not in by_domain:
                by_domain[d] = []
            name = e.get('attributes', {}).get('friendly_name', e['entity_id'])
            by_domain[d].append(name)

        for d, names in by_domain.items():
            # Limit to 5 per domain to avoid spamming
            names_display = ", ".join(names[:5])
            if len(names) > 5:
                names_display += f", and {len(names)-5} more"
            summary.append(f"{d.title()}s: {names_display}")

        return "\n".join(summary)

    def _check_ha_device_state(self, device_name: str, expected_state: str | None = None) -> str:
        """Checks the state of a Home Assistant device."""
        self.status_changed.emit(f"Checking {device_name}...")
        if not self.config.ha.enabled:
            return "Home Assistant integration is not enabled."

        entity_id = self.ha.find_entity_by_name(device_name)
        if not entity_id:
            return f"Sorry, I couldn't find a device named '{device_name}'."

        state_data = self.ha.get_device_state(entity_id)
        if not state_data:
            return f"I found {device_name} ({entity_id}), but couldn't read its state."

        state = state_data.get('state')
        attributes = state_data.get('attributes', {})
        unit = attributes.get('unit_of_measurement', '')
        friendly_name = attributes.get('friendly_name', device_name)

        # Format the answer
        state_str = f"{state}{' ' + unit if unit else ''}"
        
        if expected_state:
            # Normalize for comparison
            is_match = state.lower() == expected_state.lower()
            if is_match:
                return f"Yes, the {friendly_name} is {state_str}."
            else:
                return f"No, the {friendly_name} is actually {state_str}."
        
        return f"The {friendly_name} is currently {state_str}."

    def _save_last_response(self, filename: str) -> str:
        """Saves the last assistant response to a file."""
        self.status_changed.emit("Saving...")
        
        # Find last assistant message
        last_response = ""
        for i in range(len(self.conversation_history) - 1, -1, -1):
            if self.conversation_history[i].role == "assistant":
                last_response = self.conversation_history[i].content
                break
        
        if not last_response:
            return "There's nothing for me to save yet."
            
        return self.file_executor.save_text_to_document(last_response, filename)

    def _research_and_save(self, topic: str, filename: str) -> str:
        """Researches a topic and saves the findings to a file."""
        self.status_changed.emit(f"Researching {topic}...")
        
        # Get the summarized context
        context = self._fetch_and_summarize(topic)
        if context.startswith("Sorry"):
            return context # Return error message

        # Format for saving
        content_to_save = f"# Research on: {topic.title()}\n\n"
        content_to_save += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        content_to_save += "---\n\n"
        content_to_save += context
        
        return self.file_executor.save_text_to_document(content_to_save, filename)

    def _describe_webcam(self) -> str:
        """Capture webcam image and describe it with vision LLM."""
        self.status_changed.emit("Looking through webcam...")

        try:
            self.camera.open()
            image_base64 = self.camera.get_frame_base64()
            self.camera.close()

            if not image_base64:
                return "Sorry, I couldn't capture an image from the webcam."

            # Ask vision model to describe
            response = self.llm.vision_chat(
                "Describe what you see in this image. Be concise.",
                [image_base64]
            )
            return response

        except Exception as e:
            return f"Sorry, I couldn't access the webcam: {e}"

    def _describe_screen(self) -> str:
        """Capture screenshot and describe it with vision LLM."""
        self.status_changed.emit("Looking at your screen...")

        try:
            image_base64 = self.window_manager.capture_desktop()

            if not image_base64:
                return "Sorry, I couldn't capture a screenshot. Make sure maim is installed."

            # Ask vision model to describe
            response = self.llm.vision_chat(
                "Describe what's on this screen. What applications and content do you see?",
                [image_base64]
            )
            return response

        except Exception as e:
            return f"Sorry, I couldn't capture the screen: {e}"

    def _list_windows(self) -> str:
        """List all open windows."""
        self.status_changed.emit("Checking open windows...")

        if not self.window_manager.is_available():
            return "Sorry, window management is not available. Make sure xdotool is installed."

        windows = self.window_manager.list_windows()
        return self.window_manager.format_window_list(windows)

    def _focus_window(self, app_name: str) -> str:
        """Focus on a window by name."""
        self.status_changed.emit(f"Switching to {app_name}...")

        if not self.window_manager.is_available():
            return "Sorry, window management is not available. Make sure xdotool is installed."

        if self.window_manager.focus_window(app_name):
            return f"I've switched to {app_name}."
        else:
            return f"Sorry, I couldn't find a window matching '{app_name}'."

    @Slot()
    def toggle_listening(self) -> None:
        """Toggle voice listening on/off."""
        if self._is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self) -> None:
        """Start listening for voice input."""
        if self._is_listening:
            return

        self._is_listening = True
        self.listening_changed.emit(True)
        self.status_changed.emit("Listening...")

        # Start speech recognition in background thread
        self._speech_worker = SpeechWorker(self.stt, duration=5.0)
        self._speech_worker.finished.connect(self._on_speech_recognized)
        self._speech_worker.error.connect(self._on_speech_error)
        self._speech_worker.start()

    def stop_listening(self) -> None:
        """Stop listening for voice input."""
        self._is_listening = False
        self.listening_changed.emit(False)
        self.status_changed.emit("Ready")

    @Slot(str)
    def _on_speech_recognized(self, text: str) -> None:
        """Handle recognized speech."""
        self._is_listening = False
        self.listening_changed.emit(False)

        if text.strip():
            self.speech_recognized.emit(text)
            self.process_message(text)
        else:
            self.status_changed.emit("No speech detected")
            # If in conversation, keep listening
            if self._in_conversation:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, self.start_listening)

    @Slot(str)
    def _on_speech_error(self, error: str) -> None:
        """Handle speech recognition error."""
        self._is_listening = False
        self.listening_changed.emit(False)
        self.status_changed.emit(f"Error: {error}")

    def speak(self, text: str) -> None:
        """Speak the given text (blocking)."""
        self.status_changed.emit("Speaking...")
        try:
            self.tts.speak(text)
        except Exception as e:
            self.status_changed.emit(f"TTS Error: {e}")
        finally:
            self.status_changed.emit("Ready")

    def speak_async(self, text: str, continue_listening: bool = False) -> None:
        """Speak the given text (non-blocking).

        Args:
            text: Text to speak
            continue_listening: If True, start listening for next input after speaking
        """
        import threading
        import time

        # Mute wake word listener BEFORE speaking to prevent hearing own voice
        if self._wake_word_listener:
            self._wake_word_listener.mute()

        def _speak_and_unmute():
            try:
                # Emit speaking status (thread-safe)
                self.status_changed.emit("Speaking...")
                
                # Wait for mute to take effect and any current recording to be discarded
                time.sleep(0.5)
                self.tts.speak(text)
            except Exception as e:
                print(f"TTS Error: {e}")
                self.status_changed.emit(f"Error: {e}")
            finally:
                # Wait for audio to fully stop and any echo to dissipate
                time.sleep(1.5)

                # If in conversation, start listening AFTER TTS is done
                if continue_listening and self._in_conversation:
                    # Status will be updated to "Listening..." by start_listening
                    # Use QTimer from main thread for thread safety
                    from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(
                        self, "_delayed_start_listening",
                        Qt.ConnectionType.QueuedConnection
                    )
                else:
                    self.status_changed.emit("Ready")
                    # Unmute wake word listener after speaking
                    if self._wake_word_listener:
                        self._wake_word_listener.unmute()

        thread = threading.Thread(target=_speak_and_unmute, daemon=True)
        thread.start()

    @Slot()
    def _delayed_start_listening(self) -> None:
        """Start listening after TTS completes (called from main thread)."""
        if self._in_conversation:
            self.start_listening()

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_wake_word_listener()
        if self._browser:
            self._browser.stop()
        if self._tasks:
            self._tasks.cleanup()
        if self._memory:
            self._memory.cleanup()
