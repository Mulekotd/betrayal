import math

from external.pplay.window import Window


def get_screen():
    screen = Window.get_screen()

    if screen is None:
        raise RuntimeError("Window screen is not initialized.")

    return screen


def get_window() -> Window:
    window = Window.get_instance()

    if window is None:
        raise RuntimeError("Window instance is not initialized.")

    return window


def load_image(image_path, alpha=True):
    return get_window().load_image(image_path, alpha=alpha)


def create_surface(width: int, height: int, alpha: bool = False):
    return get_window().create_surface(width, height, alpha=alpha)


def scale_surface(surface, width: int, height: int, smooth: bool = False):
    return get_window().scale_surface(surface, width, height, smooth=smooth)


def rotate_surface(surface, angle_deg: float):
    return get_window().rotate_surface(surface, angle_deg)


def flip_surface(surface, flip_x: bool = False, flip_y: bool = False):
    return get_window().flip_surface(surface, flip_x=flip_x, flip_y=flip_y)


def draw_rect(color, rect, width: int = 0, border_radius: int = 0, target=None):
    if hasattr(rect, "left") and hasattr(rect, "top") and hasattr(rect, "width") and hasattr(rect, "height"):
        rect = (rect.left, rect.top, rect.width, rect.height)

    return get_window().draw_rect(color, rect, width=width, border_radius=border_radius, target=target)


def draw_circle(color, center, radius: int, width: int = 0, target=None):
    return get_window().draw_circle(color, center, radius, width=width, target=target)


def draw_line(color, start_pos, end_pos, width: int = 1, target=None):
    return get_window().draw_line(color, start_pos, end_pos, width=width, target=target)


def draw_arc(color, rect, start_angle: float, end_angle: float, width: int = 1, target=None):
    if hasattr(rect, "left") and hasattr(rect, "top") and hasattr(rect, "width") and hasattr(rect, "height"):
        rect = (rect.left, rect.top, rect.width, rect.height)

    x, y, w, h = rect
    radius = max(1.0, min(w, h) * 0.5)
    cx = x + w * 0.5
    cy = y + h * 0.5

    arc_span = end_angle - start_angle
    steps = max(8, int(abs(arc_span) * radius * 0.12))

    prev_x = cx + math.cos(start_angle) * radius
    prev_y = cy + math.sin(start_angle) * radius

    for step in range(1, steps + 1):
        t = step / steps
        angle = start_angle + arc_span * t

        next_x = cx + math.cos(angle) * radius
        next_y = cy + math.sin(angle) * radius

        draw_line(color, (prev_x, prev_y), (next_x, next_y), width=width, target=target)

        prev_x, prev_y = next_x, next_y


def blit_surface(surface, pos, target=None):
    return get_window().blit_surface(surface, pos, target=target)


def create_mask_surface(surface, setcolor, unsetcolor):
    width = surface.get_width()
    height = surface.get_height()
    mask_surface = create_surface(width, height, alpha=True)

    for y in range(height):
        for x in range(width):
            if surface.get_at((x, y))[3] > 0: mask_surface.set_at((x, y), setcolor)
            else: mask_surface.set_at((x, y), unsetcolor)

    return mask_surface


def set_icon(icon_path):
    return get_window().set_icon(icon_path)


def set_mouse_visible(visible: bool):
    return get_window().set_mouse_visible(visible)
