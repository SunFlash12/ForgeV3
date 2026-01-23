#!/usr/bin/env python3
"""
Notification tool - sends push notifications when Claude finishes or needs input.

Usage:
    python tools/notify.py              # Default notification
    python tools/notify.py --done       # Task completed notification
    python tools/notify.py --input      # Input needed notification
    python tools/notify.py --error      # Error occurred notification

Setup:
    1. Install ntfy app on your phone (iOS/Android)
    2. Subscribe to your topic in the app
    3. Set NTFY_TOPIC environment variable or edit NTFY_TOPIC below
"""

import sys
import platform
import os
import urllib.request
import urllib.error

# Configure your ntfy topic here (or set NTFY_TOPIC environment variable)
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "claude-notify-forge")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

def send_push_notification(sound_type: str = "default", custom_message: str = None):
    """Send a push notification via ntfy.sh."""

    titles = {
        "default": "Claude Code",
        "done": "Task Completed",
        "input": "Input Needed",
        "error": "Error Occurred",
    }

    messages = {
        "default": "Notification from Claude Code",
        "done": "Claude has finished the task!",
        "input": "Claude needs your input",
        "error": "An error occurred in Claude Code",
    }

    # ntfy priority levels: 1=min, 2=low, 3=default, 4=high, 5=urgent
    priorities = {
        "default": "3",
        "done": "4",
        "input": "5",
        "error": "5",
    }

    # ntfy tags (emojis)
    tags = {
        "default": "robot",
        "done": "white_check_mark,tada",
        "input": "hourglass,question",
        "error": "x,warning",
    }

    title = titles.get(sound_type, titles["default"])
    message = custom_message or messages.get(sound_type, messages["default"])
    priority = priorities.get(sound_type, "3")
    tag = tags.get(sound_type, "robot")

    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"

    try:
        req = urllib.request.Request(url, data=message.encode('utf-8'))
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        req.add_header("Tags", tag)

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
    except urllib.error.URLError as e:
        print(f"[WARN] Push notification failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Push notification failed: {e}", file=sys.stderr)

    return False


def play_sound(sound_type: str = "default"):
    """Play a notification sound based on the type (fallback)."""
    system = platform.system()

    if system == "Windows":
        import winsound

        # Use Windows system sounds (more reliable than PC speaker beeps)
        system_sounds = {
            "default": "SystemDefault",
            "done": "SystemExclamation",      # Happy notification
            "input": "SystemQuestion",         # Attention/question
            "error": "SystemHand",             # Error/critical
        }

        sound_alias = system_sounds.get(sound_type, "SystemDefault")
        try:
            winsound.PlaySound(sound_alias, winsound.SND_ALIAS | winsound.SND_ASYNC)
        except RuntimeError:
            # Fallback to MessageBeep if PlaySound fails
            beep_types = {
                "default": winsound.MB_OK,
                "done": winsound.MB_ICONEXCLAMATION,
                "input": winsound.MB_ICONQUESTION,
                "error": winsound.MB_ICONHAND,
            }
            winsound.MessageBeep(beep_types.get(sound_type, winsound.MB_OK))

    elif system == "Darwin":  # macOS
        import subprocess

        sounds = {
            "default": "Ping",
            "done": "Glass",
            "input": "Purr",
            "error": "Basso",
        }
        sound_name = sounds.get(sound_type, "Ping")
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound_name}.aiff"],
                      capture_output=True)

    else:  # Linux
        import subprocess

        # Try paplay (PulseAudio) first, then fall back to beep
        try:
            sounds = {
                "default": "/usr/share/sounds/freedesktop/stereo/message.oga",
                "done": "/usr/share/sounds/freedesktop/stereo/complete.oga",
                "input": "/usr/share/sounds/freedesktop/stereo/dialog-information.oga",
                "error": "/usr/share/sounds/freedesktop/stereo/dialog-error.oga",
            }
            sound_file = sounds.get(sound_type, sounds["default"])
            subprocess.run(["paplay", sound_file], capture_output=True)
        except FileNotFoundError:
            # Fallback to terminal bell
            print("\a", end="", flush=True)


def main():
    sound_type = "default"
    custom_message = None

    # Parse arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i].lower().replace("--", "").replace("-", "")
        if arg in ["done", "complete", "finished", "success"]:
            sound_type = "done"
        elif arg in ["input", "prompt", "attention", "wait"]:
            sound_type = "input"
        elif arg in ["error", "fail", "failed"]:
            sound_type = "error"
        elif arg in ["message", "msg", "m"] and i + 1 < len(args):
            i += 1
            custom_message = args[i]
        elif not arg.startswith("-") and custom_message is None:
            # Treat non-flag arguments as custom message
            custom_message = args[i]
        i += 1

    # Send push notification (primary method)
    push_sent = send_push_notification(sound_type, custom_message)

    # Try to play sound as well (might work in some environments)
    try:
        play_sound(sound_type)
    except Exception:
        pass  # Sound is optional

    # Print status message
    status_messages = {
        "default": "[NOTIFY] Notification sent",
        "done": "[DONE] Task completed!",
        "input": "[INPUT] Input needed",
        "error": "[ERROR] Error occurred",
    }
    status = status_messages.get(sound_type, status_messages["default"])

    if push_sent:
        print(f"{status} (push sent to {NTFY_TOPIC})")
    else:
        print(f"{status} (push failed, check NTFY_TOPIC)")


if __name__ == "__main__":
    main()
