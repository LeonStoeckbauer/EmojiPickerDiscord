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
import pygetwindow as gw
import time
import hashlib
import pystray
from PIL import Image as PILImage
import random

EMOJI_FILE = os.path.join(os.path.dirname(__file__), 'emojis.json')
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'emoji_cache')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
os.makedirs(CACHE_DIR, exist_ok=True)

class EmojiPickerApp:
    def load_emojis(self):
        if not os.path.exists(EMOJI_FILE):
            return []
        with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_emojis(self):
        with open(EMOJI_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.emoji_list, f, indent=4)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return {'hotkey': 'ctrl+shift+e'}
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'hotkey': 'ctrl+shift+e'}

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def __init__(self, root):
        self.root = root
        self.root.title('Emoji Picker')
        self.emoji_list = self.load_emojis()
        self.config = self.load_config()
        self.hotkey = self.config.get('hotkey', 'ctrl+shift+e')
        self.create_widgets()
        # Globaler Hotkey in separatem Thread
        self.hotkey_handle = None
        threading.Thread(target=self.register_hotkey, daemon=True).start()
        self.last_active_window = None

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Emoji Picker läuft im Hintergrund. Globaler Hotkey: Strg+Shift+E').pack(anchor='w', pady=10)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=5)
        ttk.Button(btn_frame, text='Emoji auswählen', command=self.open_popover).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='Emoji hinzufügen', command=self.add_emoji_dialog).pack(side='left', padx=2)

    def register_hotkey(self):
        if self.hotkey_handle:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass
        self.hotkey_handle = keyboard.add_hotkey(self.hotkey, lambda: self.open_popover())
        keyboard.wait()  # blockiert Thread, hält Hotkey aktiv

    def change_hotkey(self):
        def ask():
            new_hotkey = simpledialog.askstring('Hotkey ändern', 'Neuen Hotkey eingeben (z.B. ctrl+alt+e):', initialvalue=self.hotkey)
            if not new_hotkey:
                return  # Abbruch oder leere Eingabe
            old_hotkey = self.hotkey
            old_handle = self.hotkey_handle
            try:
                # Alten Hotkey deregistrieren
                if old_handle:
                    try:
                        keyboard.remove_hotkey(old_handle)
                    except Exception:
                        pass
                # Neuen Hotkey registrieren
                new_handle = keyboard.add_hotkey(new_hotkey, lambda: self.open_popover())
                # Test: Hotkey-String valid?
                if not new_handle:
                    raise ValueError('Hotkey konnte nicht registriert werden.')
                self.hotkey = new_hotkey
                self.hotkey_handle = new_handle
                self.config['hotkey'] = new_hotkey
                self.save_config()
                messagebox.showinfo('Hotkey geändert', f'Neuer Hotkey: {self.hotkey}')
            except Exception as e:
                # Alten Hotkey wiederherstellen
                try:
                    self.hotkey_handle = keyboard.add_hotkey(old_hotkey, lambda: self.open_popover())
                except Exception:
                    pass
                self.hotkey = old_hotkey
                self.config['hotkey'] = old_hotkey
                self.save_config()
                messagebox.showerror('Fehler', f'Hotkey konnte nicht geändert werden:\n{e}')
        self.root.after(0, ask)

    def get_cached_image_path(self, url):
        ext = url.split('.')[-1].lower()
        h = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return os.path.join(CACHE_DIR, f'{h}.{ext}')

    def fetch_and_cache_image(self, url):
        path = self.get_cached_image_path(url)
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    return f.read()
            except Exception:
                pass  # Datei beschädigt, neu laden
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(response.content)
                return response.content
        except Exception:
            pass
        return None

    def open_popover(self):
        # Aktives Fenster merken
        try:
            self.last_active_window = gw.getActiveWindow()
        except Exception:
            self.last_active_window = None
        # Mausposition holen
        x, y = pyautogui.position()
        # Wenn Fenster offen, schließen und neu öffnen
        if hasattr(self, 'popover') and self.popover is not None:
            try:
                if self.popover.winfo_exists():
                    self.popover.destroy()
            except Exception:
                pass
            self.popover = None
        # Fenster immer neu an aktueller Mausposition öffnen
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
        def delete_emoji(idx):
            if messagebox.askyesno('Emoji löschen', 'Dieses Emoji wirklich löschen?'):
                del self.emoji_list[idx]
                self.save_emojis()
                if hasattr(self, 'popover') and self.popover is not None:
                    try:
                        self.popover.destroy()
                    except Exception:
                        pass
                    self.popover = None
                self.open_popover()
        for idx, emoji in enumerate(self.emoji_list):
            try:
                img_bytes = self.fetch_and_cache_image(emoji['link'])
                if img_bytes is None:
                    raise Exception('Kein Bild')
                img_bytes_io = io.BytesIO(img_bytes)
                # AVIF-Unterstützung prüfen
                if emoji['link'].lower().endswith('.avif'):
                    try:
                        img = Image.open(img_bytes_io).resize((32, 32))
                    except Exception:
                        img = Image.new('RGBA', (32, 32), (200, 200, 200, 255))
                else:
                    img = Image.open(img_bytes_io).resize((32, 32))
                tk_img = ImageTk.PhotoImage(img)
                self.emoji_images.append(tk_img)
                btn = tk.Button(grid, image=tk_img, command=lambda l=emoji['link']: self.select_emoji(l), relief='flat', bd=0, highlightthickness=0)
                btn.grid(row=idx//columns, column=idx%columns, padx=4, pady=4)
                # Rechtsklick-Kontextmenü
                def make_popup(event, i=idx, e=emoji):
                    menu = tk.Menu(self.popover, tearoff=0)
                    if e.get('name'):
                        menu.add_command(label=f'Name: {e["name"]}', state='disabled')
                    menu.add_command(label='Emoji löschen', command=lambda: delete_emoji(i))
                    menu.tk_popup(event.x_root, event.y_root)
                btn.bind('<Button-3>', make_popup)
            except Exception:
                img = Image.new('RGBA', (32, 32), (200, 200, 200, 255))
                tk_img = ImageTk.PhotoImage(img)
                self.emoji_images.append(tk_img)
                btn = tk.Button(grid, image=tk_img, command=lambda l=emoji['link']: self.select_emoji(l), relief='flat', bd=0, highlightthickness=0)
                btn.grid(row=idx//columns, column=idx%columns, padx=4, pady=4)
                def make_popup(event, i=idx, e=emoji):
                    menu = tk.Menu(self.popover, tearoff=0)
                    if e.get('name'):
                        menu.add_command(label=f'Name: {e["name"]}', state='disabled')
                    menu.add_command(label='Emoji löschen', command=lambda: delete_emoji(i))
                    menu.tk_popup(event.x_root, event.y_root)
                btn.bind('<Button-3>', make_popup)

    def select_emoji(self, link):
        # Popover schließen
        if hasattr(self, 'popover') and self.popover is not None:
            try:
                self.popover.destroy()
            except Exception:
                pass
            self.popover = None
        # Fokus zurück zum letzten aktiven Fenster
        if self.last_active_window is not None:
            try:
                self.last_active_window.activate()
                time.sleep(0.05)  # noch kürzer für schnelleren Paste
            except Exception:
                pass
        # Link in Zwischenablage und per Ctrl+V einfügen (schneller als keyboard.write)
        pyperclip.copy(link)
        try:
            keyboard.press_and_release('ctrl+v')
        except Exception:
            pass

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

    def run_tray(self):
        def on_open():
            self.root.after(0, self.open_popover)
        def on_add():
            self.root.after(0, self.add_emoji_dialog)
        def on_hotkey():
            self.change_hotkey()
        def on_quit():
            self.tray_icon.stop()
            self.root.after(0, self.root.destroy)
        image = PILImage.open(os.path.join(os.path.dirname(__file__), 'tray_icon.png'))
        menu = pystray.Menu(
            pystray.MenuItem('Emoji auswählen', lambda: on_open()),
            pystray.MenuItem('Emoji hinzufügen', lambda: on_add()),
            pystray.MenuItem('Hotkey ändern', lambda: on_hotkey()),
            pystray.MenuItem('Beenden', lambda: on_quit())
        )
        self.tray_icon = pystray.Icon('emoji_picker', image, 'Emoji Picker', menu)
        self.tray_icon.run()

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', self.leave)
        widget.bind('<Motion>', self.motion)

    def enter(self, event=None):
        # print('Tooltip enter')
        self.schedule()

    def leave(self, event=None):
        # print('Tooltip leave')
        self.unschedule()
        self.hidetip()

    def motion(self, event=None):
        # print('Tooltip motion')
        if self.tipwindow:
            self.showtip(event)

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(400, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # Position direkt unter dem Button
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        parent = self.widget.winfo_toplevel()
        self.tipwindow = tw = tk.Toplevel(parent)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        tw.attributes('-topmost', True)
        tw.transient(parent)
        label = tk.Label(tw, text=self.text, justify='left', background='#ffffe0', relief='solid', borderwidth=1, font=('tahoma', '8', 'normal'))
        label.pack(ipadx=2)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = EmojiPickerApp(root)
    root.withdraw()  # Hauptfenster verstecken
    threading.Thread(target=app.run_tray, daemon=True).start()
    root.mainloop()
