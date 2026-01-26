"""Type stubs for zxcvbn password strength library."""

from typing import TypedDict

class CrackTimesDisplay(TypedDict):
    online_throttling_100_per_hour: str
    online_no_throttling_10_per_second: str
    offline_slow_hashing_1e4_per_second: str
    offline_fast_hashing_1e10_per_second: str

class CrackTimesSeconds(TypedDict):
    online_throttling_100_per_hour: float
    online_no_throttling_10_per_second: float
    offline_slow_hashing_1e4_per_second: float
    offline_fast_hashing_1e10_per_second: float

class Feedback(TypedDict):
    warning: str
    suggestions: list[str]

class MatchSequence(TypedDict, total=False):
    pattern: str
    token: str
    i: int
    j: int
    guesses: float
    guesses_log10: float
    dictionary_name: str
    rank: int
    reversed: bool
    l33t: bool
    sub_display: str
    base_guesses: float
    uppercase_variations: float
    l33t_variations: float
    graph: str
    turns: int
    shifted_count: int
    repeat_count: int
    base_token: str
    base_matches: list["MatchSequence"]
    regex_name: str
    regex_match: list[str]
    separator: str
    year: int
    month: int
    day: int

class ZxcvbnResult(TypedDict):
    password: str
    guesses: float
    guesses_log10: float
    crack_times_seconds: CrackTimesSeconds
    crack_times_display: CrackTimesDisplay
    score: int  # 0-4
    feedback: Feedback
    sequence: list[MatchSequence]
    calc_time: float

def zxcvbn(
    password: str,
    user_inputs: list[str] | None = None,
) -> ZxcvbnResult:
    """
    Evaluate password strength.

    Args:
        password: The password to evaluate
        user_inputs: Optional list of strings to penalize if found in password

    Returns:
        ZxcvbnResult with score 0-4 (0=weak, 4=strong)
    """
    ...
