import io, pygame, sys, time, ctypes, os, math
import numpy as np
from widgets import *
import cv2


# --- ИНИЦИАЛИЗАЦИЯ C++ БИБЛИОТЕКИ (опционально) ---
class Thresholds_t(ctypes.Structure):
    _fields_ = [
        ("Lmin", ctypes.c_int),
        ("Lmax", ctypes.c_int),
        ("Amin", ctypes.c_int),
        ("Amax", ctypes.c_int),
        ("Bmin", ctypes.c_int),
        ("Bmax", ctypes.c_int),
    ]


try:
    noise_lib = ctypes.CDLL("lib/noise_filter/noise.dll")
    noise_lib.remove_noise.restype = Thresholds_t
    LAB_type = ((ctypes.c_bool * 256) * 256) * 101
except:
    noise_lib = None


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ОБРАБОТКИ ---
def rgb2lab(image):
    labpix = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.int16)
    labpix[:, :, 0] = labpix[:, :, 0] * 100 // 255
    labpix[:, :, 1] -= 128
    labpix[:, :, 2] -= 128
    return labpix.astype(np.int8)


def lab_to_rgb(l, a, b):
    l_cv = np.uint8(l * 255 / 100)
    a_cv = np.uint8(a + 128)
    b_cv = np.uint8(b + 128)
    lab_pixel = np.array([[[l_cv, a_cv, b_cv]]], dtype=np.uint8)
    rgb_pixel = cv2.cvtColor(lab_pixel, cv2.COLOR_LAB2RGB)
    return rgb_pixel[0][0]


def threshold_filter(thr, pixels):
    ind = np.all(pixels >= thr[::2], axis=2) * np.all(pixels <= thr[1::2], axis=2)
    res = (ind * 255).astype(np.uint8)
    return cv2.cvtColor(res, cv2.COLOR_GRAY2RGB)


def filter_L(thr, pixels):
    l = pixels[:, :, 0]
    res = np.zeros((l.shape[0], l.shape[1], 3), dtype=np.uint8)
    res[l < thr[0]] = [0, 0, 0]
    res[(l >= thr[0]) & (l <= thr[1])] = [255, 255, 255]
    res[l > thr[1]] = [100, 100, 100]
    return res


def filter_A(thr, pixels):
    a = pixels[:, :, 1]
    res = np.zeros((a.shape[0], a.shape[1], 3), dtype=np.uint8)
    res[a < thr[2]] = [0, 100, 0]
    res[(a >= thr[2]) & (a <= thr[3])] = [255, 255, 255]
    res[a > thr[3]] = [100, 0, 0]
    return res


def filter_B(thr, pixels):
    b = pixels[:, :, 2]
    res = np.zeros((b.shape[0], b.shape[1], 3), dtype=np.uint8)
    res[b < thr[4]] = [0, 0, 100]
    res[(b >= thr[4]) & (b <= thr[5])] = [255, 255, 255]
    res[b > thr[5]] = [80, 80, 0]
    return res


def threshold_from_area(rect, pixels):
    sub = pixels[rect.left : rect.right, rect.top : rect.bottom]
    if sub.size == 0:
        return np.array([0, 100, -128, 127, -128, 127])
    return np.array(
        [
            np.min(sub[:, :, 0]),
            np.max(sub[:, :, 0]),
            np.min(sub[:, :, 1]),
            np.max(sub[:, :, 1]),
            np.min(sub[:, :, 2]),
            np.max(sub[:, :, 2]),
        ],
        dtype=np.int16,
    )


def threshold_sum(thr1, thr2):
    return [
        min(thr1[0], thr2[0]),
        max(thr1[1], thr2[1]),
        min(thr1[2], thr2[2]),
        max(thr1[3], thr2[3]),
        min(thr1[4], thr2[4]),
        max(thr1[5], thr2[5]),
    ]


def threshold_diff(thr1, rect, pixels):
    if noise_lib is None:
        return threshold_from_area(rect, pixels)
    thr_struct = Thresholds_t(
        int(thr1[0]),
        int(thr1[1]),
        int(thr1[2]) + 128,
        int(thr1[3]) + 128,
        int(thr1[4]) + 128,
        int(thr1[5]) + 128,
    )
    colorspace = LAB_type()
    sub_pixels = pixels[rect.left : rect.right, rect.top : rect.bottom]
    for row in sub_pixels:
        for p in row:
            l, a, b = map(int, p)
            if (
                l >= thr1[0]
                and l <= thr1[1]
                and a >= thr1[2]
                and a <= thr1[3]
                and b >= thr1[4]
                and b <= thr1[5]
            ):
                colorspace[l][a + 128][b + 128] = 1
    result = noise_lib.remove_noise(colorspace, thr_struct, 1)
    return [
        result.Lmin,
        result.Lmax,
        result.Amin - 128,
        result.Amax - 128,
        result.Bmin - 128,
        result.Bmax - 128,
    ]


# --- ПЕРЕМЕННЫЕ СОСТОЯНИЯ ---
pygame.init()
screen_w, screen_h = 1280, 720
screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE)
clock = pygame.time.Clock()

camera_input_text = "0"
input_active = False
requested_source = None
last_angle = -1

input_box_rect = pygame.Rect(0, 0, 0, 0)

# Заставка
current_dir = os.path.dirname(__file__)
image_path = os.path.join(current_dir, "svaga.jpg")
try:
    splash = pygame.image.load(image_path)
    splash = pygame.transform.scale(splash, (screen_w, screen_h))
    screen.blit(splash, (0, 0))
    pygame.display.flip()
except:
    screen.fill((100, 100, 100))
    pygame.display.flip()

thresholds = [[0, 100, -128, 127, -128, 127] for _ in range(5)]
thr_index = 0
process_mode = "Bitmap"
is_pause = False
pixels_LAB = np.array([])

pending_rgb = None
log_messages = []


# --- ВСПОМОГАТЕЛЬНЫЙ ВИДЖЕТ ДЛЯ ПАНЕЛИ ЛОГОВ ---
class LogPanel(Widget):
    def __init__(self, screen, rect):
        super().__init__(screen, rect)
        self.text = "Angle: ---\n\n--- History ---"
        self.font = pygame.font.Font(None, 20)
        self.bg_color = (240, 240, 240)
        self.text_color = (0, 0, 0)

    def set_text(self, text):
        self.text = text

    def draw(self):
        pygame.draw.rect(self.screen, self.bg_color, self.rect)
        lines = self.text.split("\n")
        y = self.rect.y + 5
        for line in lines:
            if line.strip():
                surf = self.font.render(line, True, self.text_color)
                self.screen.blit(surf, (self.rect.x + 5, y))
            y += self.font.get_height() + 2


# --- УПРАВЛЕНИЕ ---
def set_proc_mode(mode):
    global process_mode
    process_mode = mode


def set_pause():
    global is_pause, widgets
    is_pause = not is_pause
    widgets["btn_pause"].label.text = ">" if is_pause else "||"


def save_to_cam():
    global thresholds, thr_index, pending_rgb, last_angle
    t = thresholds[thr_index]
    l_mid = (t[0] + t[1]) / 2
    a_mid = (t[2] + t[3]) / 2
    b_mid = (t[4] + t[5]) / 2
    rgb = lab_to_rgb(l_mid, a_mid, b_mid)
    pending_rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    update_log_panel(last_angle, rgb_saved=pending_rgb)
    print(f"\n--- SAVE REPORT (Slot {thr_index+1}) ---")
    print(f"RGB: {pending_rgb}")


def change_source():
    global requested_source, camera_input_text
    val = camera_input_text.strip()
    if val.isdigit():
        requested_source = int(val)
    else:
        requested_source = val


def update_log_panel(angle, rgb_saved=None):
    global log_messages, widgets
    angle_msg = f"Angle: {angle}°" if angle != -1 else "Angle: ---"
    if rgb_saved is not None:
        timestamp = time.strftime("%H:%M:%S")
        log_messages.insert(0, f"[{timestamp}] Saved RGB: {rgb_saved}")
        if len(log_messages) > 10:
            log_messages.pop()
    history = "\n".join(log_messages) if log_messages else "No saves yet"
    log_text = angle_msg + "\n\n--- History ---\n" + history
    widgets["log_label"].set_text(log_text)


def set_thr_to_sliders():
    global thresholds, thr_index, widgets
    t = thresholds[thr_index]
    widgets["slider_L_low"].set_value(t[0])
    widgets["slider_L_high"].set_value(t[1])
    widgets["slider_A_low"].set_value(t[2])
    widgets["slider_A_high"].set_value(t[3])
    widgets["slider_B_low"].set_value(t[4])
    widgets["slider_B_high"].set_value(t[5])


# --- ВЕРСТКА ВИДЖЕТОВ ---
def update_all_widgets():
    global screen_w, screen_h, widgets, input_box_rect
    if screen_w < 100 or screen_h < 100:
        return

    margin = 30
    top_y = 15
    btn_h = 35

    def sync_btn(name, x, y, w, h):
        widgets[name].rect = pygame.Rect(x, y, w, h)
        if hasattr(widgets[name], "label"):
            widgets[name].label.rect = widgets[name].rect

    # 1. ТОП
    widgets["itemlist_select"].rect = pygame.Rect(margin, top_y, 160, btn_h)
    for i, item in enumerate(widgets["itemlist_select"].items):
        item.rect = pygame.Rect(margin + i * 55, top_y, 50, btn_h)

    mode_x = margin + 180
    sync_btn("btn_bitmap", mode_x, top_y, 90, btn_h)
    sync_btn("btn_l", mode_x + 100, top_y, 40, btn_h)
    sync_btn("btn_a", mode_x + 150, top_y, 40, btn_h)
    sync_btn("btn_b", mode_x + 200, top_y, 40, btn_h)
    sync_btn("btn_pause", mode_x + 260, top_y, 50, btn_h)

    # 2. КАМЕРЫ (СЛЕВА)
    v_y = top_y + btn_h + 20
    gap = 6
    max_v_w = (screen_w - (margin * 2) - 250) // 2
    max_v_h = int(screen_h * 0.65)
    side = min(max_v_w, max_v_h)

    x_left = margin
    x_right = x_left + side + gap
    widgets["img_src"].rect = pygame.Rect(x_left, v_y, side, side)
    widgets["img_proc"].rect = pygame.Rect(x_right, v_y, side, side)
    widgets["label_coords"].rect = pygame.Rect(x_left, v_y + side + 5, 0, 0)
    widgets["label_mode"].rect = pygame.Rect(x_right, v_y + side + 5, 0, 0)

    # 3. МЕНЮ КАМЕРЫ (СПРАВА)
    cam_x = x_right + side + 30
    widgets["label_cam_hint"].rect = pygame.Rect(cam_x, v_y, 200, 20)
    input_box_rect = pygame.Rect(cam_x, v_y + 30, 200, 35)
    sync_btn("btn_connect", cam_x, v_y + 75, 120, 35)

    # Панель логов – под полем ввода камеры
    log_y = v_y + 130
    widgets["log_label"].rect = pygame.Rect(cam_x, log_y, 250, 200)

    # 4. ТРЕШХОЛДЫ
    list_y = screen_h - 80
    col_text_w = 400
    for i, item in enumerate(widgets["itemlist_thr"].items):
        if i < 2:
            item.rect = pygame.Rect(margin, list_y + i * 20, col_text_w, 20)
        else:
            item.rect = pygame.Rect(
                margin + col_text_w + 30, list_y + (i - 2) * 20, col_text_w, 20
            )
    widgets["itemlist_thr"].rect = pygame.Rect(margin, list_y, col_text_w * 2 + 30, 60)

    # 5. СЛАЙДЕРЫ
    s_y = list_y - 50
    col_w = (screen_w - (margin * 2) - 100) // 3
    for i, char in enumerate(["L", "A", "B"]):
        x_start = margin + i * (col_w + 45)
        widgets[f"label_{char}"].rect = pygame.Rect(x_start, s_y - 25, 0, 0)
        for suffix, y_off in [("low", 0), ("high", 20)]:
            s_name = f"slider_{char}_{suffix}"
            bg_name = f"bg_slider_{char}_{suffix}"
            widgets[s_name].borders = (x_start, x_start + col_w)
            widgets[s_name].rect.y = s_y + y_off - 10
            widgets[s_name].rect.height = 20
            widgets[bg_name].rect = pygame.Rect(x_start, s_y + y_off - 10, col_w, 20)
            widgets[s_name].set_value(widgets[s_name].value)

    sync_btn("btn_save", screen_w - 130 - 20, screen_h - 40 - 20, 130, 40)


# --- ИНИЦИАЛИЗАЦИЯ ВИДЖЕТОВ ---
pixels_placeholder = np.zeros((240, 320, 3), dtype=np.uint8)
widgets = {
    "img_src": ImageNumpy(
        screen, pygame.Rect(0, 0, 0, 0), source=pixels_placeholder, select_area=True
    ),
    "img_proc": ImageNumpy(screen, pygame.Rect(0, 0, 0, 0), source=pixels_placeholder),
    "btn_bitmap": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "Bitmap",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 28),
            stratch=True,
        ),
        func=set_proc_mode,
        args=("Bitmap",),
    ),
    "btn_l": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "L",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 28),
            stratch=True,
        ),
        func=set_proc_mode,
        args=("L",),
    ),
    "btn_a": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "A",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 28),
            stratch=True,
        ),
        func=set_proc_mode,
        args=("A",),
    ),
    "btn_b": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "B",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 28),
            stratch=True,
        ),
        func=set_proc_mode,
        args=("B",),
    ),
    "log_label": LogPanel(screen, pygame.Rect(0, 0, 250, 200)),
    "bg_slider_L_low": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "bg_slider_L_high": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "bg_slider_A_low": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "bg_slider_A_high": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "bg_slider_B_low": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "bg_slider_B_high": Widget(screen, pygame.Rect(0, 0, 0, 0), block_click=False),
    "slider_L_low": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(0, 100)
    ),
    "slider_L_high": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(0, 100)
    ),
    "slider_A_low": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(-128, 127)
    ),
    "slider_A_high": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(-128, 127)
    ),
    "slider_B_low": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(-128, 127)
    ),
    "slider_B_high": HorizSlider(
        screen, pygame.Rect(0, 0, 12, 30), borders=(0, 100), values=(-128, 127)
    ),
    "label_L": Label(
        screen, pygame.Rect(0, 0, 0, 0), "L", font=pygame.font.Font(None, 35)
    ),
    "label_A": Label(
        screen, pygame.Rect(0, 0, 0, 0), "A", font=pygame.font.Font(None, 35)
    ),
    "label_B": Label(
        screen, pygame.Rect(0, 0, 0, 0), "B", font=pygame.font.Font(None, 35)
    ),
    "itemlist_thr": ItemList(
        screen,
        pygame.Rect(0, 0, 450, 130),
        items=[
            Label(
                screen,
                pygame.Rect(0, 0, 450, 25),
                f"Thr {i+1}",
                font=pygame.font.Font(None, 22),
                stratch=False,
            )
            for i in range(5)
        ],
        padding_y=25,
    ),
    "itemlist_select": ItemList(
        screen,
        pygame.Rect(0, 0, 160, 40),
        items=[
            Label(
                screen,
                pygame.Rect(0, 0, 40, 40),
                t,
                color=(255, 255, 255),
                font=pygame.font.Font(None, 28),
                stratch=True,
            )
            for t in ["R", "+", "-"]
        ],
        padding_x=50,
    ),
    "btn_save": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "SAVE",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 35),
            stratch=True,
        ),
        func=save_to_cam,
    ),
    "btn_pause": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "||",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 35),
            stratch=True,
        ),
        func=set_pause,
    ),
    "label_mode": Label(
        screen, pygame.Rect(0, 0, 0, 0), "Mode", font=pygame.font.Font(None, 25)
    ),
    "label_coords": Label(
        screen, pygame.Rect(0, 0, 0, 0), "Coords", font=pygame.font.Font(None, 20)
    ),
    "label_cam_hint": Label(
        screen,
        pygame.Rect(0, 0, 0, 0),
        "Camera Source:",
        font=pygame.font.Font(None, 25),
    ),
    "btn_connect": Button(
        screen,
        pygame.Rect(0, 0, 0, 0),
        label=Label(
            screen,
            pygame.Rect(0, 0, 0, 0),
            "CONNECT",
            color=(255, 255, 255),
            font=pygame.font.Font(None, 22),
            stratch=True,
        ),
        func=change_source,
    ),
}

wnames = list(widgets.keys())


# --- ОСНОВНАЯ ФУНКЦИЯ, ВЫЗЫВАЕМАЯ ИЗВНЕ ---
def main_loop_frame(image_pixels: np.array):
    global screen_w, screen_h, screen, widgets, pixels_LAB, thr_index, process_mode
    global thresholds, is_pause, camera_input_text, input_active, pending_rgb, last_angle

    is_real_frame = False

    # 1. ОБНОВЛЕНИЕ КАДРА
    if image_pixels is not None:
        is_real_frame = True
        if not is_pause:
            pixels_LAB = rgb2lab(image_pixels)
            v_w, v_h = widgets["img_src"].rect.width, widgets["img_src"].rect.height
            if v_w > 0 and v_h > 0:
                widgets["img_src"].pixels = cv2.resize(
                    image_pixels, (v_w, v_h), interpolation=cv2.INTER_LINEAR
                )

    # 2. ОБРАБОТКА СОБЫТИЙ
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.VIDEORESIZE:
            screen_w, screen_h = event.w, event.h
            screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE)
            update_all_widgets()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if input_box_rect.collidepoint(event.pos):
                input_active = True
            else:
                input_active = False
            for w in wnames[::-1]:
                if widgets[w].process_mousedown(event):
                    break

        if event.type == pygame.KEYDOWN and input_active:
            if event.key == pygame.K_BACKSPACE:
                camera_input_text = camera_input_text[:-1]
            elif event.key == pygame.K_RETURN:
                change_source()
            else:
                camera_input_text += event.unicode

        if event.type == pygame.MOUSEBUTTONUP:
            src_w = widgets["img_src"]
            temp_area = src_w.selected_area
            had_press = src_w.first_press is not None
            for w in wnames[::-1]:
                widgets[w].process_mouseup(event)
            if had_press and temp_area and pixels_LAB.size > 0:
                img_r = src_w.rect
                aw, ah = pixels_LAB.shape[0], pixels_LAB.shape[1]
                sx, sy = aw / img_r.width, ah / img_r.height
                x1, y1 = int(max(0, (temp_area.left - img_r.left) * sx)), int(
                    max(0, (temp_area.top - img_r.top) * sy)
                )
                x2, y2 = int(min(aw - 1, (temp_area.right - img_r.left) * sx)), int(
                    min(ah - 1, (temp_area.bottom - img_r.top) * sy)
                )
                if x2 > x1 and y2 > y1:
                    final_r = pygame.Rect(x1, y1, x2 - x1, y2 - y1)
                    mode = widgets["itemlist_select"].chosen
                    if mode == 0:
                        thresholds[thr_index] = list(
                            map(int, threshold_from_area(final_r, pixels_LAB))
                        )
                    elif mode == 1:
                        thresholds[thr_index] = threshold_sum(
                            thresholds[thr_index],
                            list(map(int, threshold_from_area(final_r, pixels_LAB))),
                        )
                    elif mode == 2:
                        thresholds[thr_index] = threshold_diff(
                            thresholds[thr_index], final_r, pixels_LAB
                        )
                    set_thr_to_sliders()

        if event.type == pygame.MOUSEMOTION:
            for w in wnames[::-1]:
                widgets[w].process_mousemotion(event)

    # 3. ОБНОВЛЕНИЕ ВИДЖЕТОВ И ПОЛУЧЕНИЕ ТЕКУЩИХ ПОРОГОВ
    for w in wnames:
        widgets[w].update()
    t = thresholds[thr_index]
    t[0], t[1] = widgets["slider_L_low"].value, widgets["slider_L_high"].value
    t[2], t[3] = widgets["slider_A_low"].value, widgets["slider_A_high"].value
    t[4], t[5] = widgets["slider_B_low"].value, widgets["slider_B_high"].value

    # 4. ОБРАБОТКА МАСКИ И ПОИСК ОБЪЕКТА
    current_angle = -1
    if pixels_LAB.size > 0:
        if process_mode == "Bitmap":
            mask = threshold_filter(thresholds[thr_index], pixels_LAB)
        elif process_mode == "L":
            mask = filter_L(thresholds[thr_index], pixels_LAB)
        elif process_mode == "A":
            mask = filter_A(thresholds[thr_index], pixels_LAB)
        elif process_mode == "B":
            mask = filter_B(thresholds[thr_index], pixels_LAB)

        gray_mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)
        contours, _ = cv2.findContours(
            gray_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        h, w = mask.shape[:2]
        center_x, center_y = w // 2, h // 2
        cv2.line(mask, (center_x, 0), (center_x, h), (100, 100, 100), 1)
        cv2.line(mask, (0, center_y), (w, center_y), (100, 100, 100), 1)

        if contours:
            largest_cnt = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest_cnt) > 300:
                M = cv2.moments(largest_cnt)
                if M["m00"] != 0:
                    cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                    dx, dy = cx - center_x, center_y - cy
                    current_angle = int(math.degrees(math.atan2(dy, dx)) % 360)
                    cv2.drawContours(mask, [largest_cnt], -1, (0, 255, 0), 2)
                    cv2.line(mask, (center_x, center_y), (cx, cy), (255, 0, 0), 2)

        widgets["img_proc"].pixels = mask

    # 5. ЛОГИРОВАНИЕ УГЛА (опционально)
    if is_real_frame and current_angle != -1:
        print(f"[TRACKING] Object found! Angle: {current_angle}°")

    # 6. ОТРИСОВКА ИНТЕРФЕЙСА
    screen.fill((200, 200, 200))
    widgets["label_L"].text = f"L [{t[0]}, {t[1]}]"
    widgets["label_A"].text = f"A [{t[2]}, {t[3]}]"
    widgets["label_B"].text = f"B [{t[4]}, {t[5]}]"
    for i in range(5):
        widgets["itemlist_thr"][i].text = f"Thr {i+1}: {list(map(int, thresholds[i]))}"
    if widgets["itemlist_thr"].chosen != thr_index:
        thr_index = widgets["itemlist_thr"].chosen
        set_thr_to_sliders()

    for w in wnames:
        widgets[w].draw()

    pygame.draw.rect(
        screen, (255, 255, 255) if input_active else (230, 230, 230), input_box_rect
    )
    pygame.draw.rect(screen, (0, 0, 0), input_box_rect, 2)
    txt_surf = pygame.font.Font(None, 26).render(camera_input_text, True, (0, 0, 0))
    screen.blit(txt_surf, (input_box_rect.x + 5, input_box_rect.y + 8))

    if widgets["img_src"].first_press and widgets["img_src"].selected_area:
        pygame.draw.rect(screen, (0, 255, 0), widgets["img_src"].selected_area, 2)

    pygame.display.update()
    clock.tick(60)

    # Сохраняем угол для панели логов
    last_angle = current_angle
    update_log_panel(current_angle, rgb_saved=None)

    # Возвращаем RGB (только если была нажата Save)
    rgb_to_send = None
    if pending_rgb is not None:
        rgb_to_send = pending_rgb
        pending_rgb = None

    return (current_angle, rgb_to_send)


# --- ЗАВЕРШЕНИЕ ИНИЦИАЛИЗАЦИИ ---
set_thr_to_sliders()
update_all_widgets()
