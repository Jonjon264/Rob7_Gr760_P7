from .agent import QwenAgent
import os
import pathlib as path
from PIL import Image
from time import sleep

agent = QwenAgent()

img = Image.open(path.Path(os.path.expanduser("~/ros2_ws/config/Face_Config/Test_img2.jpg")))

print("Sending request to QwenAgent...")
test = agent.ask("Deliver this ice cream to Simon", img)

print(test)

sleep(10)

print("Sending new request...")
test2 = agent.ask("This package is for Bo", img)

print(test2)