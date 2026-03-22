def load_user_profile(user_id: str) -> dict:
    """
    Return a mock user profile for the given user id.
    """
    return {
        "user_id": user_id,
        "name": "Alice",
        "role": "admin",
        "active": True,
    }


def format_user_label(profile: dict) -> str:
    """
    Build a short label for display.
    """
    return f"{profile['name']} ({profile['role']})"
