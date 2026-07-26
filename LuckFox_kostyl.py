import os
import subprocess
from unittest import result

import unikostyl
import cv2 as cv
import numpy as np
import time

url = 'rtsp://172.32.0.93/live/0' # Замените на ваш URL

cap = cv.VideoCapture(url)

input_frame = np.zeros((160, 120, 3))


def update_frame():
    global input_frame

    ret, frame = cap.read()
    if not ret:
        raise ValueError("No camera")
    
    # print("Frame shape:", frame.shape)
    input_frame = cv.resize(cv.cvtColor(frame, cv.COLOR_BGR2RGB), (240, 320), interpolation=cv.INTER_CUBIC)


def after_save(tresholds):
    print("after_save called\n")
    result = subprocess.run(["adb", "push", "thresholds.txt", "/userdata"], capture_output=True)
    if result.returncode != 0:
        print(f"Ошибка adb push: {result.stderr.decode()}")

start_time = time.time()
x = 1 # displays the frame rate every 1 second
counter = 0


def main_loop():
    global counter
    global start_time
    global input_frame

    unikostyl.save_to_camera_callbeck = after_save

    while(True):
        counter+=1
        if (time.time() - start_time) > x :
            print("FPS: ", counter / (time.time() - start_time))
            counter = 0
            start_time = time.time()
        update_frame()
        unikostyl.main_loop_frame(input_frame)

        


main_loop()

# Освобождаем ресурсы
cap.release()
