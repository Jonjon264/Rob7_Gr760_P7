import base64
import mimetypes
import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog

from openai import OpenAI

BASE_URL = "https://circuit-eric-certificates-donation.trycloudflare.com/v1"
MODEL = "qwen3-vl"
MAX_TOKENS = 512


def get_api_key(root):
    key = os.environ.get("QWEN_API_KEY")
    if not key:
        key = simpledialog.askstring("API key", "Enter API key:", show="*", parent=root)
    return key


def image_part(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


class App:
    def __init__(self, root, client):
        self.root = root
        self.client = client
        self.history = []
        self.image = None
        self.busy = False

        root.title("Qwen")
        root.geometry("700x600")

        self.log = scrolledtext.ScrolledText(root, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.log.tag_config("you", foreground="#1a5fb4", font=("Segoe UI", 10, "bold"))
        self.log.tag_config("qwen", foreground="#26a269", font=("Segoe UI", 10, "bold"))
        self.log.tag_config("err", foreground="#c01c28")

        bottom = tk.Frame(root)
        bottom.pack(fill="x", padx=8, pady=(0, 8))

        self.entry = tk.Text(bottom, height=3, wrap="word")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus_set()

        buttons = tk.Frame(bottom)
        buttons.pack(side="left", padx=(8, 0))
        self.send_btn = tk.Button(buttons, text="Send", width=10, command=self.send)
        self.send_btn.pack(fill="x")
        self.img_btn = tk.Button(buttons, text="Attach image", width=10, command=self.attach)
        self.img_btn.pack(fill="x", pady=2)
        tk.Button(buttons, text="Clear", width=10, command=self.clear).pack(fill="x")

    def on_enter(self, event):
        if event.state & 0x1:  # Shift+Enter inserts a newline
            return None
        self.send()
        return "break"

    def attach(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp"), ("All", "*.*")]
        )
        if path:
            self.image = path
            self.img_btn.config(text=os.path.basename(path)[:10])

    def clear(self):
        self.history = []
        self.image = None
        self.img_btn.config(text="Attach image")
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def write(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def send(self):
        text = self.entry.get("1.0", "end").strip()
        if not text or self.busy:
            return
        self.entry.delete("1.0", "end")

        if self.image:
            content = [{"type": "text", "text": text}, image_part(self.image)]
            shown = f"{text}\n[image: {os.path.basename(self.image)}]"
            self.image = None
            self.img_btn.config(text="Attach image")
        else:
            content = text
            shown = text

        self.history.append({"role": "user", "content": content})
        self.write("You\n", "you")
        self.write(shown + "\n\n")
        self.write("Qwen\n", "qwen")
        self.busy = True
        self.send_btn.config(state="disabled")
        threading.Thread(target=self.stream, daemon=True).start()

    def stream(self):
        reply = ""
        try:
            resp = self.client.chat.completions.create(
                model=MODEL,
                messages=self.history,
                max_tokens=MAX_TOKENS,
                stream=True,
            )
            for chunk in resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    piece = chunk.choices[0].delta.content
                    reply += piece
                    self.root.after(0, self.write, piece)
            self.history.append({"role": "assistant", "content": reply})
            self.root.after(0, self.write, "\n\n")
        except Exception as e:
            self.history.pop()  # drop the unanswered user turn
            self.root.after(0, self.write, f"\n[error] {e}\n\n", "err")
        finally:
            self.root.after(0, self.done)

    def done(self):
        self.busy = False
        self.send_btn.config(state="normal")


def main():
    root = tk.Tk()
    key = get_api_key(root)
    if not key:
        return
    client = OpenAI(base_url=BASE_URL, api_key=key, timeout=180)
    App(root, client)
    root.mainloop()


if __name__ == "__main__":
    main()
