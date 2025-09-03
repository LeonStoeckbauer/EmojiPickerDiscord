import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
from PIL import Image, ImageTk
import requests
import io
import json
import os
import threading
import pyperclip
import keyboard
import pyautogui

EMOJI_FILE = os.path.join(os.path.dirname(__file__), 'emojis.json')

class EmojiPickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Emoji Picker')
        self.emoji_list = self.load_emojis()
        self.create_widgets()
        # Globaler Hotkey in separatem Thread
        threading.Thread(target=self.register_hotkey, daemon=True).start()

    def load_emojis(self):
        if not os.path.exists(EMOJI_FILE):
            return []
        with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_emojis(self):
        with open(EMOJI_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.emoji_list, f, indent=4)

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Emoji Picker läuft im Hintergrund. Globaler Hotkey: Strg+Shift+E').pack(anchor='w', pady=10)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)
        ttk.Button(btn_frame, text='Emoji auswählen', command=self.open_popover).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='Emoji hinzufügen', command=self.add_emoji_dialog).pack(side='left', padx=2)

    def register_hotkey(self):
        keyboard.add_hotkey('ctrl+shift+e', lambda: self.root.event_generate('<<OpenEmojiPopover>>'))
        self.root.bind('<<OpenEmojiPopover>>', lambda e: self.open_popover())
        keyboard.wait()  # blockiert Thread, hält Hotkey aktiv

    def open_popover(self):
        # Mausposition holen
        x, y = pyautogui.position()
        if hasattr(self, 'popover') and self.popover.winfo_exists():
            self.popover.lift()
            self.popover.geometry(f'+{x}+{y}')
            self.popover.attributes('-topmost', True)
            self.popover.focus_force()
            return
        self.popover = tk.Toplevel(self.root)
        self.popover.title('Emoji auswählen')
        self.popover.transient(self.root)
        self.popover.geometry(f'+{x}+{y}')
        self.popover.attributes('-topmost', True)
        self.popover.lift()
        self.popover.focus_force()
        self.popover.deiconify()
        self.popover.grab_set()
        grid = ttk.Frame(self.popover, padding=10)
        grid.pack()
        self.emoji_images = []
        columns = 6
        for idx, emoji in enumerate(self.emoji_list):
            try:
                response = requests.get(emoji['link'], timeout=5)
                img_bytes = io.BytesIO(response.content)
                # AVIF-Unterstützung prüfen
                if emoji['link'].lower().endswith('.avif'):
                    try:
                        img = Image.open(img_bytes).resize((32, 32))
                    except Exception:
                        # Platzhalter für nicht unterstützte AVIFs
                        img = Image.new('RGBA', (32, 32), (200, 200, 200, 255))
                else:
                    img = Image.open(img_bytes).resize((32, 32))
                tk_img = ImageTk.PhotoImage(img)
                self.emoji_images.append(tk_img)
                btn = ttk.Button(grid, image=tk_img, command=lambda l=emoji['link']: self.select_emoji(l))
                btn.grid(row=idx//columns, column=idx%columns, padx=4, pady=4)
            except Exception:
                continue

    def select_emoji(self, link):
        # Link in Zwischenablage und als Tastatureingabe einfügen
        pyperclip.copy(link)
        try:
            keyboard.write(link)
        except Exception:
            pass
        if hasattr(self, 'popover'):
            self.popover.destroy()

    def add_emoji_dialog(self):
        url = simpledialog.askstring('Emoji hinzufügen', 'Bild-Link (PNG/GIF/AVIF/JPG/WEBP) eingeben:')
        if not url:
            return
        try:
            response = requests.get(url, timeout=5)
            img_bytes = io.BytesIO(response.content)
            ext = url.split('.')[-1].lower()
            allowed_exts = ('png', 'gif', 'avif', 'jpg', 'jpeg', 'webp')
            if ext not in allowed_exts:
                raise ValueError('Nur PNG, GIF, AVIF, JPG oder WEBP erlaubt.')
            # Pillow kann AVIF evtl. nicht öffnen, das ist ok
            try:
                Image.open(img_bytes)
            except Exception:
                if ext not in ('avif', 'webp'):
                    raise ValueError('Bild konnte nicht geladen werden.')
        except Exception as e:
            messagebox.showerror('Fehler', f'Bild konnte nicht geladen werden: {e}')
            return
        name = simpledialog.askstring('Name (optional)', 'Name für das Emoji (optional):')
        self.emoji_list.append({'link': url, 'name': name or ''})
        self.save_emojis()
        messagebox.showinfo('Erfolg', 'Emoji hinzugefügt!')

if __name__ == '__main__':
    root = tk.Tk()
    app = EmojiPickerApp(root)
    root.mainloop()
