"""
Contrast Helper
===============
Works out a text color that passes, because this is math and shouldn't be
left to the model to guess.

Dependencies:
    - none
"""


# ── Color Math ──

def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb: tuple[int, int, int]) -> float:
    """Relative luminance, using the WCAG formula."""
    channels = []
    for channel in rgb:
        c = channel / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


# ── Suggestion ──

def suggest_text_color(fg: str, bg: str, target: float) -> str | None:
    """
    Move the text color toward black or white until it just passes, so it
    stays as close to the original color as it can.

    Returns:
    --------
    A hex color, or None if neither black nor white reaches the target
    """
    start = hex_to_rgb(fg)
    background = hex_to_rgb(bg)

    # small margin so rounding can't put us right under the line
    goal = target + 0.05
    options = []
    for end in ((0, 0, 0), (255, 255, 255)):
        if contrast_ratio(end, background) < goal:
            continue
        for step in range(1, 101):
            t = step / 100
            mixed = tuple(round(s + (e - s) * t) for s, e in zip(start, end))
            if contrast_ratio(mixed, background) >= goal:
                options.append((step, mixed))
                break

    if not options:
        return None
    _, best = min(options)
    return "#{:02x}{:02x}{:02x}".format(*best)
