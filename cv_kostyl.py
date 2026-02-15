import sys
import unikostyl
import cv2 as cv
import pygame
import asyncio
import numpy as np

cap = cv.VideoCapture(0)
input_frame = np.zeros((160, 120, 3))


def update_frame():
    global input_frame

    ret, input_frame = cap.read()
    if input_frame is None:
        raise ValueError("No camera")

    input_frame = input_frame[:,:,::-1].transpose(1, 0, 2).copy()
    input_frame = cv.resize(input_frame, (240, 320), interpolation=cv.INTER_CUBIC)


def main_loop():
    global input_frame

    while(True):
        update_frame()
        unikostyl.main_loop_frame(input_frame)


main_loop()