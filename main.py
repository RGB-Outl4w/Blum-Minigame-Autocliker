import math
import os
import random
import sys
import time

import cv2
import keyboard
import mss
import numpy as np
import pygetwindow as gw
import win32api
import win32con

# Constants for clearer code
CLICK_IMAGES = [
    os.path.join(sys._MEIPASS, "media\\lobby-play.png") if hasattr(sys, "_MEIPASS") else "media\\lobby-play.png",
    os.path.join(sys, "_MEIPASS", "media\\continue-play.png") if hasattr(sys, "_MEIPASS") else "media\\continue-play.png"
]

PERCENTAGES = {
    "1": 0.13,   # 90-110 points
    "2": 0.17,   # 140-160 points
    "3": 0.235,  # 170-180 points
    "4": 1,      # Max points
}

# Pre-calculate HSV values for target and nearby colors
TARGET_HSVS = [
    (int(c[1:3], 16) * 180 // 256, int(c[3:5], 16) * 255 // 256, int(c[5:7], 16) * 255 // 256)
    for c in ["#c9e100", "#bae70e"]
]
NEARBY_HSVS = [
    (int(c[1:3], 16) * 180 // 256, int(c[3:5], 16) * 255 // 256, int(c[5:7], 16) * 255 // 256)
    for c in ["#abff61", "#87ff27"]
]


class Logger:
    def __init__(self, prefix=None):
        self.prefix = prefix

    def log(self, data: str):
        print(f"{self.prefix} {data}" if self.prefix else data)

    def input(self, text: str):
        return input(f"{self.prefix} {text}" if self.prefix else text)


class AutoClicker:
    def __init__(self, window_title, logger, percentages: float, is_continue: bool):
        self.window_title = window_title
        self.logger = logger
        self.running = False
        self.clicked_points = []
        self.iteration_count = 0
        self.percentage_click = percentages
        self.is_continue = is_continue

        # Load template images for 'Play' buttons only once
        self.templates_plays = [
            cv2.cvtColor(cv2.imread(img, cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2GRAY)
            for img in CLICK_IMAGES
        ]

    @staticmethod
    def click_at(x, y):
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def toggle_script(self):
        self.running = not self.running
        self.logger.log(f'Mode changed: {"on" if self.running else "off"}')

    def is_near_color(self, hsv_img, center, radius=8):
        x, y = center
        height, width = hsv_img.shape[:2]
        for i in range(max(0, x - radius), min(width, x + radius + 1)):
            for j in range(max(0, y - radius), min(height, y + radius + 1)):
                if math.sqrt((x - i) ** 2 + (y - j) ** 2) <= radius:
                    pixel_hsv = hsv_img[j, i]
                    for target_hsv in NEARBY_HSVS:  # Using pre-calculated HSVs
                        if np.allclose(pixel_hsv, target_hsv, atol=[1, 50, 50]):
                            return True
        return False

    def find_and_click_image(self, template_gray, screen, monitor):
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)
        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.6:
            template_height, template_width = template_gray.shape
            center_x = max_loc[0] + template_width // 2 + monitor["left"]
            center_y = max_loc[1] + template_height // 2 + monitor["top"]
            self.click_at(center_x, center_y)
            return True
        return False

    def click_color_areas(self):
        windows = gw.getWindowsWithTitle(self.window_title)
        if not windows:
            self.logger.log(
                f"No window with the title: {self.window_title} was found. "
                f"Open the Blum web application and execute the script again."
            )
            return

        window = windows[0]
        window.activate()

        with mss.mss() as sct:
            keyboard.add_hotkey(41, self.toggle_script)  # Grave key (~)

            while True:
                if self.running:
                    monitor = {
                        "top": window.top,
                        "left": window.left,
                        "width": window.width,
                        "height": window.height
                    }
                    img = np.array(sct.grab(monitor))
                    hsv = cv2.cvtColor(img, cv2.COLOR_BGRA2HSV)  # Convert once

                    for target_hsv in TARGET_HSVS:  # Using pre-calculated HSVs
                        lower_bound = np.array([max(0, target_hsv[0] - 1), 30, 30])
                        upper_bound = np.array([min(179, target_hsv[0] + 1), 255, 255])
                        mask = cv2.inRange(hsv, lower_bound, upper_bound)
                        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        for contour in reversed(contours):
                            if random.random() >= self.percentage_click:
                                continue
                            if cv2.contourArea(contour) < 8:
                                continue

                            M = cv2.moments(contour)
                            if M["m00"] == 0:
                                continue
                            cX = int(M["m10"] / M["m00"]) + monitor["left"]
                            cY = int(M["m01"] / M["m00"]) + monitor["top"]

                            if not self.is_near_color(hsv, (cX - monitor["left"], cY - monitor["top"])):
                                continue
                            if any(math.sqrt((cX - px) ** 2 + (cY - py) ** 2) < 35 for px, py in self.clicked_points):
                                continue

                            self.click_at(cX, cY + 7)
                            self.logger.log(f'Clicked: {cX} {cY}')
                            self.clicked_points.append((cX, cY))

                    time.sleep(0.222) 
                    self.iteration_count += 1
                    if self.iteration_count >= 5:
                        self.clicked_points.clear()
                        if self.is_continue:
                            for tp in self.templates_plays:
                                self.find_and_click_image(tp, img, monitor)
                        self.iteration_count = 0


if __name__ == "__main__":
    logger = Logger("[https://github.com/RGB-Outl4w/blum-minigame-autocliker]")
    logger.log('You are using "Blum Minigame Autoclicker"')

    while True:
        points_key = logger.input(
            "Specify the desired number of points | 1 -> 90-110 | 2 -> 140-160 | 3 -> 170-180 | 4 -> MAX: "
        )
        percentages = PERCENTAGES.get(points_key)
        if percentages is not None:
            break
        logger.log("Invalid parameter.")

    while True:
        continue_key = logger.input("Should the bot continue playing automatically? | 1 - YES / 0 - NO: ")
        is_continue = {"1": True, "0": False}.get(continue_key)
        if is_continue is not None:
            break
        logger.log("Invalid parameter.")

    logger.log('After starting the mini-game, press the (~) key on your keyboard.')
    auto_clicker = AutoClicker("TelegramDesktop", logger, percentages, is_continue)
    try:
        auto_clicker.click_color_areas()
    except Exception as e:
        logger.log(f"An error has occurred: {e}")

    for i in range(5, 0, -1):
        print(f"The script will shut down in {i}")
        time.sleep(1)