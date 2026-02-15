import unikostyl
import cv2 as cv
import numpy as np
from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start()
cap = cv.VideoCapture(0)
input_frame = np.zeros((160, 120, 3))


def update_frame():
    global input_frame

    input_frame = picam2.capture_array("main")
    if input_frame is None:
        raise ValueError("No camera")

    input_frame = cv.resize(input_frame, (240, 320), interpolation=cv.INTER_CUBIC)


def main_loop():
    global input_frame

    while(True):
        update_frame()
        unikostyl.main_loop_frame(input_frame)


main_loop()