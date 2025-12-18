DEFAULT_HABITS = [
    "Walk 20+ min",
    "Sunlight 10 min",
    "Protein target met",
    "Stretching 5 min",
    "Water 2L",
    "No late-night snack",
    "Read 10 min",
    "Meditation 5 min",
]

def habit_score(completed: dict) -> float:
    # completed: {"Walk 20+ min": True, ...}
    if not completed:
        return 0.0
    total = len(completed)
    done = sum(1 for v in completed.values() if v)
    return done / max(1, total)
