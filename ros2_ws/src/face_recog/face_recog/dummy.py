from .agent import QwenAgent
import os
import pathlib as path
from PIL import Image

agent = QwenAgent()

img = Image.open(path.Path(os.path.expanduser("~/ros2_ws/config/Face_Config/Test_img2.jpg")))


test = agent.ask("Deliver this ice cream to Simon", img)

print(test)