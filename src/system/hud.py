from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.rect import Rect
from src.utils.services import FontLibrary
from src.utils.window import (
    blit_surface,
    draw_rect,
    get_screen,
    load_image,
    scale_surface
)

def _load(path: Path, w: int | None = None, h: int | None = None) -> Any | None:
    if not path.exists():
        return None

    surf = load_image(str(path), alpha=True)
    if surf is None:
        return None

    if w is not None and h is not None:
        surf = scale_surface(surf, w, h, smooth=False)
    elif w is not None:
        ratio = w / surf.get_width()
        surf = scale_surface(surf, w, int(surf.get_height() * ratio), smooth=False)
    elif h is not None:
        ratio = h / surf.get_height()
        surf = scale_surface(surf, int(surf.get_width() * ratio), h, smooth=False)

    return surf

class HUDColors:
    HUD_TEXT = (245, 245, 235)

    HP_BG = (20,  10,  10)
    HP_FILL = (200, 50,  50)
    HP_FILL_LOW = (230, 100, 30)
    HP_BORDER = (80,  30,  30)
    HP_TEXT = HUD_TEXT

    XP_BG = (10,  10,  24)
    XP_FILL = (50,  120, 255)
    XP_BORDER = (30,  60,  120)
    XP_TEXT = HUD_TEXT

    KILLS_TEXT = HUD_TEXT

    TIMER_BG = (10,  10,  20,  160)
    TIMER_TEXT = HUD_TEXT
    TIMER_SHADOW = (0, 0, 0)

    WEAPON_BG = (18,  22,  28)
    WEAPON_BORDER = (70,  80,  90)
    WEAPON_SEL_BOR = (235, 210, 120)
    WEAPON_INNER = (8, 10, 14)

class HUD:
    def __init__(
        self,
        viewport_width:  int,
        viewport_height: int,
        fonts:           FontLibrary,
        images_dir:      Path,
        padding:         int = 0
    ) -> None:
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.padding = max(0, int(padding))

        self.font_hud = fonts.mini(30)
        self.font_xp = fonts.mini(22)
        self.font_small = fonts.mini(18)

        self.hp_bar_w = 190
        self.hp_bar_h = 20

        self.xp_bar_h = 20
        self.xp_bar_x = 0
        self.xp_bar_y = viewport_height - self.xp_bar_h

        self.weapon_order = ["fire", "ice", "wind"]
        self.weapon_slot_size = 64
        self.weapon_icon_pad = 10
        self.weapon_gap = 8

        icon_inner = max(1, self.weapon_slot_size - self.weapon_icon_pad * 2)
        self.weapon_icons: dict[str, Any | None] = {
            key: _load(images_dir / fname, icon_inner, icon_inner)
            for key, fname in {
                "fire": "fire_sword.png",
                "ice":  "ice_sword.png",
                "wind": "wind_sword.png"
            }.items()
        }

        self.hp_bar_x = self.padding + 8
        self.hp_bar_y = self.padding + 8

    def draw(
        self,
        player:          object,
        total_kills:     int,
        selected_weapon: str | None = None,
        run_time:        float = 0.0,
        fps_value:       float | None = None
    ) -> None:
        self._draw_hp_bar(player)
        self._draw_xp_bar(player)
        self._draw_weapon_bar(selected_weapon)
        self._draw_timer(run_time)
        self._draw_kills_counter(total_kills)
        if fps_value is not None:
            self._draw_fps(fps_value)

    def pick_weapon(self, x: float, y: float) -> str | None:
        for key, rect in self._weapon_rects().items():
            if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                return key

        return None

    def _draw_hp_bar(self, player: object) -> None:
        screen = get_screen()

        hp = float(getattr(player, "health", 0))
        max_hp = float(getattr(player, "max_health", 1))
        ratio = min(1.0, max(0.0, hp / max(1.0, max_hp)))

        bx, by = self.hp_bar_x, self.hp_bar_y
        bw, bh = self.hp_bar_w, self.hp_bar_h

        draw_rect(HUDColors.HP_BG, (bx, by, bw, bh), target=screen)

        fill_w = max(0, int(bw * ratio))
        if fill_w > 0:
            fill_color = HUDColors.HP_FILL_LOW if ratio < 0.30 else HUDColors.HP_FILL
            draw_rect(fill_color, (bx, by, fill_w, bh), target=screen)

        draw_rect(HUDColors.HP_BORDER, (bx, by, bw, 1), target=screen)
        draw_rect(HUDColors.HP_BORDER, (bx, by + bh - 1, bw, 1), target=screen)
        draw_rect(HUDColors.HP_BORDER, (bx, by, 1, bh), target=screen)
        draw_rect(HUDColors.HP_BORDER, (bx + bw - 1, by, 1, bh), target=screen)

        label = f"HP  {int(hp)} / {int(max_hp)}"
        surf = self.font_xp.render(label, False, HUDColors.HP_TEXT)
        screen.blit(surf, (bx + (bw - surf.get_width()) // 2, by + (bh - surf.get_height()) // 2))

    def _draw_xp_bar(self, player: object) -> None:
        screen = get_screen()

        xp = int(getattr(player, "xp", 0))
        xp_to_next = max(1, int(getattr(player, "xp_to_next", 1)))
        level = int(getattr(player, "level", 1))

        ratio = min(1.0, max(0.0, xp / xp_to_next))

        bx, by = self.xp_bar_x, self.xp_bar_y
        bw, bh = self.viewport_width, self.xp_bar_h

        draw_rect(HUDColors.XP_BG, (bx, by, bw, bh), target=screen)

        fill_w = max(0, int(bw * ratio))
        if fill_w > 0:
            draw_rect(HUDColors.XP_FILL, (bx, by, fill_w, bh), target=screen)

        draw_rect(HUDColors.XP_BORDER, (bx, by, bw, 1), target=screen)

        label = f"LV {level}"

        surf = self.font_xp.render(label, False, HUDColors.XP_TEXT)
        screen.blit(surf, ((bw - surf.get_width()) // 2, by + (bh - surf.get_height()) // 2))

    def _draw_kills_counter(self, total_kills: int) -> None:
        label = f"Kills: {total_kills}"

        screen = get_screen()

        shadow = self.font_hud.render(label, False, HUDColors.TIMER_SHADOW)
        surf = self.font_hud.render(label, False, HUDColors.KILLS_TEXT)
        x = self.hp_bar_x
        y = self.hp_bar_y + self.hp_bar_h + 8

        screen.blit(shadow, (x + 1, y + 1))
        screen.blit(surf, (x, y))

    def _draw_timer(self, run_time: float) -> None:
        screen = get_screen()

        label = self._timer_label(run_time)

        text_surf = self.font_hud.render(label, False, HUDColors.TIMER_TEXT)
        shadow_surf = self.font_hud.render(label, False, HUDColors.TIMER_SHADOW)

        tx, ty, _, _ = self._timer_rect(label)

        screen.blit(shadow_surf, (tx + 1, ty + 1))
        screen.blit(text_surf, (tx, ty))

    def _draw_fps(self, fps_value: float) -> None:
        screen = get_screen()

        if fps_value > 0.0:
            label = f"FPS: {int(round(fps_value))}"
        else:
            label = "FPS: --"

        text_surf = self.font_small.render(label, False, HUDColors.TIMER_TEXT)
        shadow_surf = self.font_small.render(label, False, HUDColors.TIMER_SHADOW)

        x = self.viewport_width - text_surf.get_width() - self.padding - 12
        y = self.padding + 10

        screen.blit(shadow_surf, (x + 1, y + 1))
        screen.blit(text_surf, (x, y))

    def _draw_weapon_bar(self, selected_weapon: str | None) -> None:
        screen = get_screen()

        for key, rect in self._weapon_rects().items():
            selected = key == selected_weapon
            border_color = HUDColors.WEAPON_SEL_BOR if selected else HUDColors.WEAPON_BORDER
            border_w = 2 if selected else 1

            draw_rect(HUDColors.WEAPON_BG, (rect.left, rect.top, rect.width, rect.height), target=screen)
            draw_rect(HUDColors.WEAPON_INNER, (rect.left + 4, rect.top + 4, rect.width - 8, rect.height - 8), target=screen)
            draw_rect(border_color, (rect.left, rect.top, rect.width, rect.height), width=border_w, target=screen)

            icon = self.weapon_icons.get(key)
            if icon is not None:
                ix = rect.left + self.weapon_icon_pad + (
                    (self.weapon_slot_size - self.weapon_icon_pad * 2 - icon.get_width()) // 2
                )
                iy = rect.top + self.weapon_icon_pad + (
                    (self.weapon_slot_size - self.weapon_icon_pad * 2 - icon.get_height()) // 2
                )
                blit_surface(icon, (ix, iy), target=screen)

    def _timer_label(self, run_time: float) -> str:
        minutes = int(run_time) // 60
        seconds = int(run_time) % 60

        return f"{minutes:02d}:{seconds:02d}"

    def _timer_rect(self, label: str) -> tuple[int, int, int, int]:
        surf = self.font_hud.render(label, False, HUDColors.TIMER_TEXT)

        tw = surf.get_width()
        th = surf.get_height()

        x = (self.viewport_width - tw) // 2
        y = self.padding + 8

        return (x, y, tw, th)

    def _weapon_rects(self) -> dict[str, Rect]:
        base_x = self.padding + 8
        base_y = self.xp_bar_y - self.weapon_gap - self.weapon_slot_size

        return {
            key: Rect(
                base_x + i * (self.weapon_slot_size + self.weapon_gap),
                base_y,
                self.weapon_slot_size,
                self.weapon_slot_size
            )
            for i, key in enumerate(self.weapon_order)
        }
