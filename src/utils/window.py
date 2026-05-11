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


def blit_surface(surface, pos, target=None):
    return get_window().blit_surface(surface, pos, target=target)


def set_icon(icon_path):
    return get_window().set_icon(icon_path)


def set_mouse_visible(visible: bool):
    return get_window().set_mouse_visible(visible)
