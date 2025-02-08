class BuddyError(Exception):
    """Base exception class for Buddy application"""

    pass


class AudioError(BuddyError):
    """Raised when there's an error with audio operations"""

    pass


class AIError(BuddyError):
    """Raised when there's an error with AI operations"""

    pass


class SpeechRecognitionError(BuddyError):
    """Raised when there's an error with speech recognition"""

    pass
