#!/usr/bin/env python3
"""
Notification tool - plays a sound when Claude finishes or needs input.

Usage:
    python tools/notify.py              # Default notification
    python tools/notify.py --done       # Task completed sound
    python tools/notify.py --input      # Input needed sound
    python tools/notify.py --error      # Error occurred sound
"""

import sys
import platform

def play_sound(sound_type: str = "default"):
    """Play a notification sound based on the type."""
    system = platform.system()

    if system == "Windows":
        import winsound

        sounds = {
            "default": (800, 200),      # Medium beep
            "done": [(523, 150), (659, 150), (784, 300)],  # C-E-G chord (happy)
            "input": [(880, 300), (880, 300)],  # Double high beep (attention)
            "error": [(400, 500)],      # Low beep (error)
        }

        beeps = sounds.get(sound_type, sounds["default"])
        if isinstance(beeps, tuple):
            beeps = [beeps]

        for freq, duration in beeps:
            winsound.Beep(freq, duration)

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

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().replace("--", "").replace("-", "")
        if arg in ["done", "complete", "finished", "success"]:
            sound_type = "done"
        elif arg in ["input", "prompt", "attention", "wait"]:
            sound_type = "input"
        elif arg in ["error", "fail", "failed"]:
            sound_type = "error"

    play_sound(sound_type)

    # Print status message
    messages = {
        "default": "[NOTIFY] Notification",
        "done": "[DONE] Task completed!",
        "input": "[INPUT] Input needed",
        "error": "[ERROR] Error occurred",
    }
    print(messages.get(sound_type, messages["default"]))


if __name__ == "__main__":
    main()
