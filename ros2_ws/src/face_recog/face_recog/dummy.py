from .agent import QwenAgent
import os
import pathlib as path
from PIL import Image
import time


agent = QwenAgent()

time.sleep(10)

img = Image.open(path.Path(os.path.expanduser("~/ros2_ws/config/Face_Config/Test_img2.jpg")))

print("Sending request to QwenAgent...")
start = time.time()

test = agent.ask("Deliver this ice cream to Simon", img)

Tasktime = time.time() - start
print(test)
print(Tasktime)

# time.sleep(10)

# print("Sending new request...")
# start = time.time()

# test2 = agent.ask("This package is for Bo", img)

# print(test2)

# Tasktime = time.time() - start
# print(test)
# print(Tasktime)