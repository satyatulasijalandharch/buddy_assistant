import speech_recognition as sr
import asyncio
import edge_tts
from ollama_helper import OllamaAPI
import signal
import os
from pygame import mixer
import threading
import logging
from exceptions import AudioError, AIError, SpeechRecognitionError
import keyboard
import time  # Add this import

VOICE = "en-US-ChristopherNeural"

# Initialize mixer globally
mixer.init()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add these at the top level after imports
exit_flag = threading.Event()


def monitor_exit_key():
    """Monitor for ESC key in a separate thread"""
    while not exit_flag.is_set():
        if keyboard.is_pressed("esc"):
            print("\nExit command detected...")
            exit_flag.set()
        time.sleep(0.1)  # Reduce CPU usage


def audio_finished():
    while mixer.music.get_busy():
        threading.Event().wait(0.1)


async def speak(text):
    temp_file = "temp_speech.mp3"
    try:
        logger.info("Generating speech...")
        print(f"Assistant: {text}")
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(temp_file)

        if not os.path.exists(temp_file):
            raise AudioError("Speech file was not generated")

        try:
            mixer.music.load(temp_file)
            mixer.music.play()

            audio_thread = threading.Thread(target=audio_finished)
            audio_thread.start()

            # Add timeout for audio playback
            timeout = len(text.split()) * 0.5  # Rough estimate of speech duration
            start_time = asyncio.get_event_loop().time()

            while audio_thread.is_alive():
                await asyncio.sleep(0.1)
                if (
                    asyncio.get_event_loop().time() - start_time > timeout + 5
                ):  # 5 second buffer
                    raise AudioError("Audio playback timeout")

        except Exception as e:
            raise AudioError(f"Audio playback failed: {str(e)}")
        finally:
            if mixer.music.get_busy():
                mixer.music.stop()
            mixer.music.unload()

    except Exception as e:
        logger.error(f"Speech generation error: {str(e)}")
        # Fallback to just printing if speech fails
        print(f"Assistant (text only): {text}")
    finally:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file: {str(e)}")


def listen_and_recognize(recognizer, source, language="en-US"):
    while not exit_flag.is_set():  # Add exit flag check
        try:
            print("\nListening... (Press ESC to exit)")
            try:
                # Reduced timeout to make it more responsive
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=10)
                if exit_flag.is_set():  # Check if exit was requested
                    return "exit"

                print("Processing speech...")

                text = recognizer.recognize_google(audio, language=language)
                if text.strip():  # Check if we got non-empty speech
                    return text

            except sr.WaitTimeoutError:
                if exit_flag.is_set():  # Check if exit was requested
                    return "exit"
                # Instead of raising error, just continue listening
                print("No speech detected, still listening...")
                continue

            except sr.UnknownValueError:
                print("Could not understand audio, please try again...")
                continue

            except sr.RequestError as e:
                raise SpeechRecognitionError(
                    f"Speech recognition service error: {str(e)}"
                )

        except KeyboardInterrupt:
            raise  # Re-raise to allow clean exit

        except Exception as e:
            if not isinstance(e, SpeechRecognitionError):
                logger.error(f"Unexpected error in speech recognition: {str(e)}")
                print("Had some trouble there, still listening...")
                continue
            raise

    return "exit"  # Return exit command if we break out of loop


def initialize_ai():
    return OllamaAPI()


def process_ai_response(ai_helper, text):
    try:
        # Add contextual hints for different types of interactions
        if "how are you" in text.lower():
            prompt = "The user is asking how you are. Respond warmly as Buddy and ask them back."
        elif any(word in text.lower() for word in ["help", "can you", "how to"]):
            prompt = f"The user needs assistance. As Buddy, provide a helpful and detailed response to: {text}"
        elif any(word in text.lower() for word in ["thanks", "thank you"]):
            prompt = "The user is thanking you. Respond graciously and show enthusiasm to help more."
        else:
            prompt = f"Engage warmly with the user as Buddy and respond to: {text}"

        response = ai_helper.generate_response(prompt)
        return response
    except Exception as e:
        return f"AI Error: {str(e)}"


async def cleanup():
    try:
        mixer.music.stop()
        mixer.quit()
        # Clean up temporary files
        if os.path.exists("temp_speech.mp3"):
            os.remove("temp_speech.mp3")
    except Exception:
        pass


def check_exit_command():
    return exit_flag.is_set()


async def perform_exit():
    print("\nExiting program...")
    await speak("Goodbye! Press Enter to close the program.")
    exit_flag.set()
    await cleanup()


async def main():
    recognizer = sr.Recognizer()
    ai_helper = initialize_ai()
    consecutive_errors = 0
    max_consecutive_errors = 3

    print("Press ESC key at any time to exit")

    # Start keyboard monitoring in separate thread
    exit_monitor = threading.Thread(target=monitor_exit_key)
    exit_monitor.daemon = True  # Thread will close with main program
    exit_monitor.start()

    try:
        # Setup signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda signum, frame: asyncio.create_task(cleanup()))

        with sr.Microphone() as source:
            print("Adjusting for ambient noise... Please wait...")
            try:
                recognizer.adjust_for_ambient_noise(source, duration=2)
            except Exception as e:
                logger.warning(f"Noise adjustment failed: {str(e)}")

            recognizer.energy_threshold = 4000
            await speak(
                "Hi! I'm Buddy, your friendly AI assistant. What can I help you with today?"
            )

            while not exit_flag.is_set():  # Changed while True to check exit_flag
                try:
                    text = listen_and_recognize(recognizer, source)
                    if (
                        exit_flag.is_set()
                    ):  # Check if exit was requested during listening
                        break

                    print(f"You said: {text}")
                    consecutive_errors = 0  # Reset error counter on success

                    if text.lower() in ["exit", "quit", "stop", "goodbye"]:
                        await speak("Thanks for chatting! Have a great day!")
                        break
                    else:
                        ai_response = process_ai_response(ai_helper, text)
                        await speak(ai_response)

                except KeyboardInterrupt:
                    await speak("Goodbye! Have a great day!")
                    break
                except (SpeechRecognitionError, AIError, AudioError) as e:
                    logger.error(str(e))
                    consecutive_errors += 1

                    if consecutive_errors >= max_consecutive_errors:
                        await speak(
                            "I'm having a bit of trouble understanding. Let's take a quick break!"
                        )
                        consecutive_errors = 0
                    else:
                        await speak("Could you say that again please?")
                except Exception as e:
                    logger.error(f"Unexpected error: {str(e)}")
                    await speak("Oops! Something went wrong. Let's try that again!")

    finally:
        exit_flag.set()  # Ensure exit flag is set
        await cleanup()
        input("Press Enter to close...")  # Give user time to read final message


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
