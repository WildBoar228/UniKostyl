import io, pygame, sys, time, ctypes
from PIL import Image, ImageOps
import numpy as np
# from skimage.color import rgb2lab
from widgets import *
import cv2


class Thresholds_t(ctypes.Structure):
    _fields_ = [("Lmin", ctypes.c_int),
                ("Lmax", ctypes.c_int),
                ("Amin", ctypes.c_int),
                ("Amax", ctypes.c_int),
                ("Bmin", ctypes.c_int),
                ("Bmax", ctypes.c_int)]


noise_lib = ctypes.CDLL("lib/noise_filter/noise.dll")
noise_lib.remove_noise.restype = Thresholds_t
LAB_type = ((ctypes.c_bool * 256) * 256) * 101


def rgb2lab(image):
    labpix = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.int16)
    labpix[:,:,0] = labpix[:,:,0] * 100 // 255
    labpix[:,:,1] -= 128
    labpix[:,:,2] -= 128
    labpix = labpix.astype(np.int8)
    return labpix


def threshold_filter(thr, pixels):
    labpix = pixels #rgb2lab(pixels / 255).astype(np.int8)
    ind = np.all(labpix >= thr[::2], axis=2) * np.all(labpix <= thr[1::2], axis=2)
    return ind * 255


def filter_L(thr, pixels):
    labpix = pixels #rgb2lab(pixels / 255).astype(np.int8)
    ind_low = labpix[:,:,0] < thr[0]
    ind_high = labpix[:,:,0] > thr[1]
    ind_ok = ((~ind_low) & (~ind_high))
    labpix[ind_low] = np.array([0, 0, 0])
    labpix[ind_ok] = np.array([255, 255, 255])
    labpix[ind_high] = np.array([100, 100, 100])
    return labpix


def filter_A(thr, pixels):
    labpix = pixels #rgb2lab(pixels / 255).astype(np.int8)
    ind_low = labpix[:,:,1] < thr[2]
    ind_high = labpix[:,:,1] > thr[3]
    ind_ok = ((~ind_low) & (~ind_high))
    labpix[ind_low] = np.array([0, 100, 0])
    labpix[ind_ok] = np.array([255, 255, 255])
    labpix[ind_high] = np.array([100, 0, 0])
    return labpix


def filter_B(thr, pixels):
    labpix = pixels #rgb2lab(pixels / 255).astype(np.int8)
    ind_low = labpix[:,:,2] < thr[4]
    ind_high = labpix[:,:,2] > thr[5]
    ind_ok = ((~ind_low) & (~ind_high))
    labpix[ind_low] = np.array([0, 0, 100])
    labpix[ind_ok] = np.array([255, 255, 255])
    labpix[ind_high] = np.array([80, 80, 0])
    return labpix


def threshold_from_area(rect, pixels):
    labpix = pixels #rgb2lab(pixels / 255).astype(np.int8)
    print(labpix.shape, f"{rect.left}..{rect.right}   {rect.top}..{rect.bottom}")
    l_min = np.min(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 0])
    l_max = np.max(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 0])
    a_min = np.min(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 1])
    a_max = np.max(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 1])
    b_min = np.min(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 2])
    b_max = np.max(labpix[rect.left : rect.right + 1, rect.top : rect.bottom + 1, 2])
    thr = np.array([l_min, l_max, a_min, a_max, b_min, b_max], dtype=np.int16)
    print(list(map(int, thr)))
    return list(map(int, thr))


def threshold_sum(thr1, thr2):
    thr = np.array(thr1)
    thr[0] = min(thr1[0], thr2[0])
    thr[1] = max(thr1[1], thr2[1])
    thr[2] = min(thr1[2], thr2[2])
    thr[3] = max(thr1[3], thr2[3])
    thr[4] = min(thr1[4], thr2[4])
    thr[5] = max(thr1[5], thr2[5])
    return list(map(int, thr))


def threshold_diff(thr1, rect, pixels):
    # thr2 = threshold_from_area(rect, pixels)
    # thr = np.array(thr1)
    # thr[0] = max(thr1[0], thr2[0])
    # thr[1] = min(thr1[1], thr2[1])
    # thr[2] = max(thr1[2], thr2[2])
    # thr[3] = min(thr1[3], thr2[3])
    # thr[4] = max(thr1[4], thr2[4])
    # thr[5] = min(thr1[5], thr2[5])
    # return thr

    thr = Thresholds_t(int(thr1[0]),
                       int(thr1[1]),
                       int(thr1[2]) + 128,
                       int(thr1[3]) + 128,
                       int(thr1[4]) + 128,
                       int(thr1[5]) + 128)
    colorspace = LAB_type()

    for i in range(rect.left, rect.right + 1):
        for j in range(rect.top, rect.bottom + 1):
            # try:
            l, a, b = map(int, pixels[i][j])
            # except IndexError:
            #     continue
            if (l >= thr1[0] and l <= thr1[1] and
                a >= thr1[2] and a <= thr1[3] and
                b >= thr1[4] and b <= thr1[5]):
                    a += 128
                    b += 128
                    #print(f'strike out:  {l} {a} {b}')
                    colorspace[l][a][b] = 1
    
    time_complexity = (thr1[1] - thr1[0] + 1) ** 2 * (thr1[3] - thr1[2] + 1) * (thr1[5] - thr1[4] + 1)
    print(f'time_complexity:   {time_complexity}, s = {1 if time_complexity < 1e7 else 2}')

    print(thr1, end=' -> ')
    result = noise_lib.remove_noise(colorspace, thr, 1 if time_complexity < 1e7 else 2)
    thr1 = [result.Lmin, result.Lmax,
            result.Amin - 128, result.Amax - 128,
            result.Bmin - 128, result.Bmax - 128]
    print(thr1)
        
    return list(map(int, thr1))


def save_to_cam():
    print("save_to_cam")
    global save_thr
    save_thr = True


def set_thr_to_sliders():
    global thresholds
    global thr_index

    widgets['slider_L_low'].set_value(thresholds[thr_index][0])
    widgets['slider_L_high'].set_value(thresholds[thr_index][1])

    widgets['slider_A_low'].set_value(thresholds[thr_index][2])
    widgets['slider_A_high'].set_value(thresholds[thr_index][3])

    widgets['slider_B_low'].set_value(thresholds[thr_index][4])
    widgets['slider_B_high'].set_value(thresholds[thr_index][5])


def set_pause():
    global is_pause
    if is_pause:
        is_pause = False
        widgets['btn_pause'].label.text = '||'
    else:
        is_pause = True
        widgets['btn_pause'].label.text = '>'


pygame.init()
screen_w = 1280
screen_h = 600
screen = pygame.display.set_mode((screen_w, screen_h))

pygame.display.set_caption("OpenKostyl")
clock = pygame.time.Clock()

take_thr_from_cam = True
save_thr = False

MAX_THR_STORY_SIZE = 10
thr_story = []
inv_thr_story = []

thresholds = [
    [0, 100, -128, 127, -128, 127],
    [0, 100, -128, 127, -128, 127],
    [0, 100, -128, 127, -128, 127],
    [0, 100, -128, 127, -128, 127],
    [0, 100, -128, 127, -128, 127],
]

thr_buffer = [-1, -1, -1, -1, -1, -1]

thr_index = 0
edit_index = 0

pixels = np.array([])
pixels_processed = np.array([])
process_mode = 'Bitmap'
is_pause = False


def backup_thresholds():
    global thresholds
    global thr_story
    global inv_thr_story
    global MAX_THR_STORY_SIZE

    if len(thr_story) >= MAX_THR_STORY_SIZE:
        thr_story.pop(0)
        
    thr_story.append(thresholds.copy())
    inv_thr_story = []


def set_proc_mode(mode):
    global process_mode
    process_mode = mode


widgets = {'img_src': ImageNumpy(screen, pygame.Rect(20, 60, 320, 240), source=pixels, select_area=True),
           'img_proc': ImageNumpy(screen, pygame.Rect(20 + 320 + 20, 60, 320, 240), source=pixels_processed),

           'btn_bitmap': Button(screen, pygame.Rect(20 + 320 + 20, 10, 100, 40),
                                label=Label(screen, pygame.Rect(20 + 320 + 20, 10, 100, 40),
                                            text='Bitmap', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=set_proc_mode, args=('Bitmap',),
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)}),

           'btn_l': Button(screen, pygame.Rect(360 + 100 + 10, 10, 40, 40),
                                label=Label(screen, pygame.Rect(360 + 100 + 10, 10, 40, 40),
                                            text='L', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=set_proc_mode, args=('L',),
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)}),

           'btn_a': Button(screen, pygame.Rect(470 + 40 + 10, 10, 40, 40),
                                label=Label(screen, pygame.Rect(470 + 40 + 10, 10, 40, 40),
                                            text='A', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=set_proc_mode, args=('A',),
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)}),

           'btn_b': Button(screen, pygame.Rect(520 + 40 + 10, 10, 40, 40),
                                label=Label(screen, pygame.Rect(520 + 40 + 10, 10, 40, 40),
                                            text='B', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=set_proc_mode, args=('B',),
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)}),

            'label_mode': Label(screen, pygame.Rect(20 + 320 + 20, 60 + 240 + 20, 0, 0),
                                'Mode', color=(0, 0, 0), stratch=False),

            'label_coords': Label(screen, pygame.Rect(20, 60 + 240 + 20, 0, 0),
                                'Coords', color=(0, 0, 0), stratch=False,
                                font=pygame.font.Font(None, 20)),
            
            'slider_L_low': HorizSlider(screen, pygame.Rect(20, 360, 10, 10),
                                    borders=(20, 400), values=(0, 100),
                                    radius=8, bg_width=3,
                                    color=(0, 0, 0)),
            'bg_slider_L_low': Widget(screen, pygame.Rect(20, 360, 380, 9), block_click=False),
            'slider_L_high': HorizSlider(screen, pygame.Rect(20, 370, 10, 10),
                                    borders=(20, 400), values=(0, 100),
                                    radius=8, bg_width=3,
                                    color=(150, 150, 150)),
            'bg_slider_L_high': Widget(screen, pygame.Rect(20, 370, 380, 9), block_click=False),
            'label_L': Label(screen, pygame.Rect(420, 370, 0, 0),
                            'L  [0, 100]', color=(0, 0, 0), stratch=False,
                            font=pygame.font.Font(None, 30)),
            
            'slider_A_low': HorizSlider(screen, pygame.Rect(20, 400, 10, 10),
                                    borders=(20, 400), values=(-128, 127),
                                    radius=8, bg_width=3,
                                    color=(100, 150, 100)),
            'bg_slider_A_low': Widget(screen, pygame.Rect(20, 400, 380, 9), block_click=False),
            'slider_A_high': HorizSlider(screen, pygame.Rect(20, 410, 10, 10),
                                    borders=(20, 400), values=(-128, 127),
                                    radius=8, bg_width=3,
                                    color=(150, 100, 100)),
            'bg_slider_A_high': Widget(screen, pygame.Rect(20, 410, 380, 9), block_click=False),
            'label_A': Label(screen, pygame.Rect(420, 400, 0, 0),
                            'A  [-128, 127]', color=(0, 0, 0), stratch=False,
                            font=pygame.font.Font(None, 30)),
            
            'slider_B_low': HorizSlider(screen, pygame.Rect(20, 450, 10, 10),
                                    borders=(20, 400), values=(-128, 127),
                                    radius=8, bg_width=3,
                                    color=(100, 100, 150)),
            'bg_slider_B_low': Widget(screen, pygame.Rect(20, 450, 380, 9), block_click=False),
            'slider_B_high': HorizSlider(screen, pygame.Rect(20, 460, 10, 10),
                                    borders=(20, 400), values=(-128, 127),
                                    radius=8, bg_width=3,
                                    color=(150, 150, 80)),
            'bg_slider_B_high': Widget(screen, pygame.Rect(20, 460, 380, 9), block_click=False),
            'label_B': Label(screen, pygame.Rect(420, 450, 0, 0),
                            'B  [-128, 127]', color=(0, 0, 0), stratch=False,
                            font=pygame.font.Font(None, 30)),

            'itemlist_thr': ItemList(screen, pygame.Rect(750, 20, 0, 0),
                                     items=[Label(screen, pygame.Rect(750, 20, 300, 60),
                                            'Thr 1: ', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                            
                                            Label(screen, pygame.Rect(750, 20, 300, 60),
                                            'Thr 2: ', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                            
                                            Label(screen, pygame.Rect(750, 20, 300, 60),
                                            'Thr 3: ', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                            
                                            Label(screen, pygame.Rect(750, 20, 300, 60),
                                            'Thr 4: ', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                            
                                            Label(screen, pygame.Rect(750, 20, 300, 60),
                                            'Thr 5: ', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),],

                                     padding_y=30),
            
            'itemlist_select': ItemList(screen, pygame.Rect(20, 10, 40, 40),
                                     items=[Label(screen, pygame.Rect(20, 10, 40, 40),
                                            'R', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                         
                                            Label(screen, pygame.Rect(20, 10, 40, 40),
                                            '+', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                            
                                            Label(screen, pygame.Rect(20, 10, 40, 40),
                                            '-', color=(0, 0, 0), stratch=True,
                                            font=pygame.font.Font(None, 25)),
                                     ],

                                     padding_x=60),

           'btn_save': Button(screen, pygame.Rect(800, 400, 150, 40),
                              label=Label(screen, pygame.Rect(800, 400, 150, 40),
                                            text='Save', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=save_to_cam,
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)}),
            
            'btn_pause': Button(screen, pygame.Rect(300, 10, 40, 40),
                                label=Label(screen, pygame.Rect(300, 10, 40, 40),
                                            text='||', color=(255, 255, 255),
                                            font=pygame.font.Font(None, 40),
                                            stratch=True),
                                func=set_pause,
                                colors={'normal': (0, 0, 0),
                                        'pressed': (100, 100, 100)})
}
pixels_LAB = np.array([])
wnames = list(widgets.keys())
bg_names = ['bg_slider_L_low', 'bg_slider_L_high',
            'bg_slider_A_low', 'bg_slider_A_high',
            'bg_slider_B_low', 'bg_slider_B_high',]

keys = {}
press_pos = (-1, -1)

try:
    with open("thresholds.txt") as file:
        thresholds = np.array(eval(file.read().strip()), dtype=np.int8)
except FileNotFoundError as exc:
    pass

set_thr_to_sliders()


def save_to_camera():
    global save_thr
    print("dfgdfghfh")
    save_thr = False
    with open("thresholds.txt", "w") as file:
        file.write(str(list(thresholds)))


# This will be called with the bytes() object generated by the slave device.
def main_loop_frame(image_pixels: np.array):
    global edit_index
    global process_mode
    global thresholds
    global thr_index
    global thr_buffer
    global save_thr
    global take_thr_from_cam

    sys.stdout.flush()
    
    image_pixels = cv2.resize(image_pixels, (240, 320), interpolation=cv2.INTER_CUBIC)

    pygame.draw.rect(screen, (200, 200, 200),
                     (0, 0, screen_w, screen_h))

    try:
        if not is_pause:
            widgets['img_src'].pixels = image_pixels
    except Exception as exc:
        print(exc)
        return
    
    # pixels_LAB = np.rot90(np.array(ImageOps.mirror(image.convert('LAB')), dtype=np.float32), k=1)
    pixels_LAB = rgb2lab(widgets['img_src'].pixels).astype(np.int16)
    # print(np.min(pixels_LAB[:,:,1]), np.max(pixels_LAB[:,:,1]), ";   ", np.min(pixels_LAB[:,:,2]), np.max(pixels_LAB[:,:,2]))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()
            
        if event.type == pygame.KEYDOWN:
            keys[event.key] = 1
            
            if event.key == pygame.K_c and (keys.get(pygame.K_LCTRL) or keys.get(pygame.K_RCTRL)):
                thr_buffer = thresholds[thr_index].copy()

            if event.key == pygame.K_v and (keys.get(pygame.K_LCTRL) or keys.get(pygame.K_RCTRL)):
                backup_thresholds()
                if thr_buffer[0] != -1:
                    thresholds[thr_index] = thr_buffer.copy()
                    set_thr_to_sliders()

            if event.key == pygame.K_z and (keys.get(pygame.K_LCTRL) or keys.get(pygame.K_RCTRL)):
                if len(thr_story) > 0:
                    inv_thr_story.append(thresholds.copy())
                    thresholds = thr_story[-1].copy()
                    thr_story.pop()
                    set_thr_to_sliders()

            if event.key == pygame.K_y and (keys.get(pygame.K_LCTRL) or keys.get(pygame.K_RCTRL)):
                if len(inv_thr_story) > 0:
                    thr_story.append(thresholds.copy())
                    thresholds = inv_thr_story[-1].copy()
                    inv_thr_story.pop()
                    set_thr_to_sliders()
            
            if keys.get(pygame.K_LEFT) or keys.get(pygame.K_a):
                for i in range(6):
                    if widgets[bg_names[i]].mouse_inside:
                        if (keys.get(pygame.K_LALT) or keys.get(pygame.K_RALT)):
                            backup_thresholds()
                            thresholds[thr_index][i] -= 5
                        else:
                            backup_thresholds()
                            thresholds[thr_index][i] -= 1
                        set_thr_to_sliders()
            
            elif keys.get(pygame.K_RIGHT) or keys.get(pygame.K_d):
                for i in range(6):
                    if widgets[bg_names[i]].mouse_inside:
                        if (keys.get(pygame.K_LALT) or keys.get(pygame.K_RALT)):
                            backup_thresholds()
                            thresholds[thr_index][i] += 5
                        else:
                            backup_thresholds()
                            thresholds[thr_index][i] += 1
                        set_thr_to_sliders()
        
        if event.type == pygame.KEYUP:
            keys[event.key] = 0
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            blocked = False
            for w in wnames[::-1]:
                if widgets[w].process_mousedown(event) and not (blocked and widgets[w].block_click):
                    if widgets[w].block_click:
                        blocked = True

            if thr_index != widgets['itemlist_thr'].chosen:
                thr_index = widgets['itemlist_thr'].chosen
                set_thr_to_sliders()

        if event.type == pygame.MOUSEBUTTONUP:
            flag = widgets['img_src'].first_press is not None
            for w in wnames[::-1]:
                widgets[w].process_mouseup(event)
            
            if flag and widgets['img_src'].selected_area is not None:
                rect = widgets['img_src'].selected_area.copy()

                rect.left -= widgets['img_src'].rect.left + 1
                rect.top -= widgets['img_src'].rect.top + 1
                # rect.width //= 2
                # rect.height //= 2
                # rect.left //= 2
                # rect.top //= 2

                backup_thresholds()

                if widgets['itemlist_select'].chosen == 0:
                    thresholds[thr_index] = list(map(int, threshold_from_area(rect, pixels_LAB).copy()))

                if widgets['itemlist_select'].chosen == 1:
                    thresholds[thr_index] = threshold_sum(thresholds[thr_index],
                                                          list(map(int, threshold_from_area(rect, pixels_LAB).copy())))
                    
                if widgets['itemlist_select'].chosen == 2:
                    thresholds[thr_index] = threshold_diff(thresholds[thr_index], rect, pixels_LAB)
                    # thresholds[thr_index] = threshold_diff(thresholds[thr_index],
                    #                                       list(map(int, threshold_from_area(rect, pixels_LAB).copy())))
                thresholds[thr_index] = list(thresholds[thr_index])

                set_thr_to_sliders()

        if event.type == pygame.MOUSEMOTION:
            for w in wnames[::-1]:
                widgets[w].process_mousemotion(event)

    if process_mode == 'Bitmap':
        widgets['img_proc'].pixels = threshold_filter(thresholds[thr_index], pixels_LAB)
    if process_mode == 'L':
        widgets['img_proc'].pixels = filter_L(thresholds[thr_index], pixels_LAB)
    if process_mode == 'A':
        widgets['img_proc'].pixels = filter_A(thresholds[thr_index], pixels_LAB)
    if process_mode == 'B':
        widgets['img_proc'].pixels = filter_B(thresholds[thr_index], pixels_LAB)
    
    clock.tick()
    
    thresholds[thr_index][0] = constrain(thresholds[thr_index][0], 0, 100)
    thresholds[thr_index][1] = constrain(thresholds[thr_index][1], 0, 100)
    thresholds[thr_index][2] = constrain(thresholds[thr_index][2], -128, 127)
    thresholds[thr_index][3] = constrain(thresholds[thr_index][3], -128, 127)
    thresholds[thr_index][4] = constrain(thresholds[thr_index][4], -128, 127)
    thresholds[thr_index][5] = constrain(thresholds[thr_index][5], -128, 127)

    if widgets['img_src'].selected_area is not None:
        widgets['label_coords'].text = 'Coords ' + str(widgets['img_src'].selected_area)

    widgets['label_mode'].text = 'Mode ' + process_mode

    for i in range(len(widgets['itemlist_thr'].items)):
        widgets['itemlist_thr'][i].text = f'Thr {i + 1}: ' + str(thresholds[i])

    L_low = widgets['slider_L_low'].value
    L_high = widgets['slider_L_high'].value
    widgets['label_L'].text = "L  [" + str(L_low) + ", " + str(L_high) + "]"

    A_low = widgets['slider_A_low'].value
    A_high = widgets['slider_A_high'].value
    widgets['label_A'].text = "A  [" + str(A_low) + ", " + str(A_high) + "]"

    B_low = widgets['slider_B_low'].value
    B_high = widgets['slider_B_high'].value
    widgets['label_B'].text = "B  [" + str(B_low) + ", " + str(B_high) + "]"
    
    thresholds[thr_index][0] = L_low
    thresholds[thr_index][1] = L_high
    thresholds[thr_index][2] = A_low
    thresholds[thr_index][3] = A_high
    thresholds[thr_index][4] = B_low
    thresholds[thr_index][5] = B_high
    
    for w in wnames:
        widgets[w].update()
    for w in wnames:
        widgets[w].draw()

    if widgets['img_src'].first_press is not None and widgets['img_src'].selected_area is not None:
        draw_rect_alpha(screen, (70, 100, 250, 100), widgets['img_src'].selected_area)
    
    pygame.display.update()

    if save_thr:
        save_thr = False
        save_to_camera()
        return
