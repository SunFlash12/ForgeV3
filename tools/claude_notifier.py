#!/usr/bin/env python3
"""
Claude Code Notification Script
Plays a sound when Claude Code finishes working or needs input.

Run this in PyCharm or configure as a Claude Code hook.

Usage:
  1. Run directly: python claude_notifier.py
  2. Or configure in ~/.claude/settings.json (see below)

Hook Configuration (~/.claude/settings.json):
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Stop|Task",
        "hooks": [{"type": "command", "command": "python /path/to/claude_notifier.py"}]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "python /path/to/claude_notifier.py"}]
      }
    ]
  }
}
"""

import subprocess
import sys
import os

def play_notification():
    """Play a notification sound using available system methods."""

    # Method 1: Try paplay (PulseAudio) with system sounds
    sound_files = [
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "/usr/share/sounds/freedesktop/stereo/message.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
        "/usr/share/sounds/gnome/default/alerts/drip.ogg",
        "/usr/share/sounds/ubuntu/stereo/message.ogg",
    ]

    for sound in sound_files:
        if os.path.exists(sound):
            try:
                subprocess.run(["paplay", sound], check=True, timeout=5)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue

    # Method 2: Try aplay with beep
    try:
        subprocess.run(["aplay", "-q", "/usr/share/sounds/alsa/Front_Center.wav"],
                      check=True, timeout=5, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 3: Try speaker-test for a quick beep
    try:
        subprocess.run(["speaker-test", "-t", "sine", "-f", "1000", "-l", "1"],
                      timeout=0.3, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 4: Terminal bell (works in most terminals)
    print("\a", end="", flush=True)
    return True


def send_desktop_notification(title="Claude Code", message="Ready for input"):
    """Send a desktop notification if notify-send is available."""
    try:
        subprocess.run(["notify-send", "-u", "normal", "-t", "3000", title, message],
                      check=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main():
    """Main entry point - plays sound and shows notification."""
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Claude Code needs attention"

    # Play sound
    play_notification()

    # Show desktop notification
    send_desktop_notification("Claude Code", message)

    print(f"🔔 {message}")


if __name__ == "__main__":
    main()
