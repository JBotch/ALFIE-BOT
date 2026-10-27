"""A few small pygame widgets for the developer panel.

Kept deliberately simple so the panel has no dependencies beyond pygame
and also runs on the Pi.
"""

import pygame

BG = (22, 26, 34)
PANEL = (32, 37, 48)
WIDGET = (48, 55, 70)
WIDGET_HOVER = (62, 71, 90)
WIDGET_ACTIVE = (30, 140, 190)
WIDGET_DISABLED = (38, 42, 52)
TEXT = (225, 232, 240)
TEXT_DIM = (130, 140, 155)
ACCENT = (90, 215, 255)
GOOD = (80, 210, 120)
WARN = (240, 180, 60)
BAD = (235, 85, 85)

_fonts = {}


def font(size: int = 18) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def draw_text(surface, text, pos, colour=TEXT, size=18, max_width=None):
    f = font(size)
    if max_width:
        while text and f.size(text)[0] > max_width:
            text = text[:-4] + "..." if len(text) > 2 else ""
    img = f.render(text, True, colour)
    surface.blit(img, pos)
    return img.get_rect(topleft=pos)


def wrap_text(text, width, size=18):
    f = font(size)
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            trial = word if not line else line + " " + word
            if f.size(trial)[0] <= width:
                line = trial
            else:
                if line:
                    lines.append(line)
                while f.size(word)[0] > width and len(word) > 1:
                    cut = len(word)
                    while cut > 1 and f.size(word[:cut])[0] > width:
                        cut -= 1
                    lines.append(word[:cut])
                    word = word[cut:]
                line = word
        lines.append(line)
    return lines


class Button:
    def __init__(self, rect, label, on_click=None, enabled=True, tooltip="",
                 on_press=None, on_release=None, size=17):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.on_press = on_press
        self.on_release = on_release
        self.enabled = enabled
        self.tooltip = tooltip
        self.selected = False
        self.size = size
        self._held = False

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.enabled:
                    self._held = True
                    if self.on_press:
                        self.on_press()
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._held:
            self._held = False
            if self.on_release:
                self.on_release()
            if self.enabled and self.rect.collidepoint(event.pos) and self.on_click:
                self.on_click()
            return True
        return False

    def draw(self, surface, mouse_pos):
        if not self.enabled:
            colour = WIDGET_DISABLED
        elif self.selected or self._held:
            colour = WIDGET_ACTIVE
        elif self.rect.collidepoint(mouse_pos):
            colour = WIDGET_HOVER
        else:
            colour = WIDGET
        pygame.draw.rect(surface, colour, self.rect, border_radius=6)
        if self.selected:
            pygame.draw.rect(surface, ACCENT, self.rect, 1, border_radius=6)
        img = font(self.size).render(self.label, True, TEXT if self.enabled else TEXT_DIM)
        surface.blit(img, img.get_rect(center=self.rect.center))


class TextInput:
    def __init__(self, rect, on_submit, placeholder=""):
        self.rect = pygame.Rect(rect)
        self.on_submit = on_submit
        self.placeholder = placeholder
        self.text = ""
        self.focused = False
        self.enabled = True
        self._cursor_t = 0.0

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            was = self.focused
            self.focused = self.rect.collidepoint(event.pos) and self.enabled
            if self.focused != was:
                (pygame.key.start_text_input if self.focused else pygame.key.stop_text_input)()
            return self.focused
        if not self.focused:
            return False
        if event.type == pygame.TEXTINPUT:
            self.text += event.text
            return True
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit()
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.focused = False
            return True
        return False

    def submit(self):
        text = self.text.strip()
        self.text = ""
        if text:
            self.on_submit(text)

    def draw(self, surface, dt=0.0):
        self._cursor_t += dt
        pygame.draw.rect(surface, (16, 19, 25), self.rect, border_radius=6)
        border = ACCENT if self.focused else WIDGET_HOVER
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=6)
        inner = self.rect.inflate(-16, 0)
        f = font(19)
        if self.text:
            shown = self.text
            while f.size(shown)[0] > inner.width - 8 and shown:
                shown = shown[1:]
            img = f.render(shown, True, TEXT)
        else:
            shown = ""
            img = f.render(self.placeholder, True, TEXT_DIM)
        y = self.rect.centery - img.get_height() // 2
        surface.blit(img, (inner.x, y))
        if self.focused and int(self._cursor_t * 2) % 2 == 0:
            x = inner.x + f.size(shown)[0] + 1
            pygame.draw.line(surface, TEXT, (x, y), (x, y + img.get_height()), 2)


class LogView:
    """Scrolling list of (colour, text) lines, newest at the bottom."""

    def __init__(self, rect, title, size=16):
        self.rect = pygame.Rect(rect)
        self.title = title
        self.size = size
        self.scroll = 0  # lines scrolled up from the bottom

    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll = max(0, self.scroll + event.y)
            return True
        return False

    def draw(self, surface, lines):
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=8)
        draw_text(surface, self.title, (self.rect.x + 10, self.rect.y + 7), ACCENT, 19)
        body = self.rect.inflate(-20, -40)
        body.y = self.rect.y + 30
        line_h = font(self.size).get_linesize()
        wrapped = []
        for colour, text in lines:
            for part in wrap_text(text, body.width, self.size):
                wrapped.append((colour, part))
        visible = max(1, body.height // line_h)
        self.scroll = min(self.scroll, max(0, len(wrapped) - visible))
        end = len(wrapped) - self.scroll
        start = max(0, end - visible)
        clip = surface.get_clip()
        surface.set_clip(body)
        for i, (colour, text) in enumerate(wrapped[start:end]):
            surface.blit(font(self.size).render(text, True, colour), (body.x, body.y + i * line_h))
        surface.set_clip(clip)
        if self.scroll:
            draw_text(surface, f"scrolled up {self.scroll}", (self.rect.right - 130, self.rect.y + 9), TEXT_DIM, 15)
