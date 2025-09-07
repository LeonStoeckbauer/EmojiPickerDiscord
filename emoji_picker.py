import sys
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

EMOJI_SIZE = 64
ANIMATION_DELAY_MS = 80  # Verzögerung für Emoji-Animationen in Millisekunden

# Einfache Mutex-Implementierung für Windows, um Mehrfachstarts zu verhindern
if sys.platform == 'win32':
    import win32event
    import win32api
    import winerror
    mutex = win32event.CreateMutex(None, False, 'EmojiPickerDiscordMutex')
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        messagebox.showerror('EmojiPicker läuft bereits', 'Die Anwendung ist bereits gestartet!', parent=root)
        root.destroy()
        sys.exit(0)

# AppData-Pfad bestimmen (plattformunabhängig)
if sys.platform == 'win32':
    BASE_DATA_DIR = os.path.join(os.environ.get('APPDATA'), 'EmojiPickerDiscord')
else:
    BASE_DATA_DIR = os.path.join(os.path.expanduser('~'), '.config', 'EmojiPickerDiscord')

os.makedirs(BASE_DATA_DIR, exist_ok=True)

EMOJI_FILE = os.path.join(BASE_DATA_DIR, 'emojis.json')
CACHE_DIR = os.path.join(BASE_DATA_DIR, 'emoji_cache')
CACHE_DIR_PREVIEW = os.path.join(BASE_DATA_DIR, 'emoji_preview_cache')
CONFIG_FILE = os.path.join(BASE_DATA_DIR, 'config.json')
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR_PREVIEW, exist_ok=True)


class EmojiPickerApp:
    def load_emojis(self):
        if not os.path.exists(EMOJI_FILE):
            return []
        with open(EMOJI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_emojis(self):
        with open(EMOJI_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.emoji_list, f, indent=4)
        # Vorschau-Cache für alle Emojis erzeugen
        for emoji in self.emoji_list:
            self.create_emoji_preview_cache(emoji)
        self.invalidate_emoji_previews()

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
        # Wenn beim ersten Start und emojis.json leer ist, Standard-Emojis einfügen
        if not self.emoji_list:
            self.emoji_list = [
                {"link": "https://cdn.7tv.app/emote/01F6MKTFTG0009C9ZSNZTFV2ZF/3x.avif", "name": "NOOOO"},
                {"link": "https://cdn.7tv.app/emote/01F6MZGCNG000255K4X1K7NTHR/3x.avif", "name": "GIGACHAD"},
                {"link": "https://cdn.7tv.app/emote/01F6MQ33FG000FFJ97ZB8MWV52/3x.avif", "name": "catJAM"},
                {"link": "https://cdn.7tv.app/emote/01F7M225F8000AWSXNQ65M4PKG/3x.avif", "name": "SNIFFA"},
                {"link": "https://cdn.7tv.app/emote/01GBFAYKGR000FWWN7MDZZ8XQN/3x.avif", "name": "RAGEY"},
                {"link": "https://cdn.7tv.app/emote/01H0405680000AJFXTYVX2PNJ7/3x.avif", "name": "uuh"},
                {"link": "https://cdn.7tv.app/emote/01F6NCKMP000052X5637DW2XDY/3x.avif", "name": "meow"},
                {"link": "https://cdn.7tv.app/emote/01F6ME9FRG0005TFYTWP1H8R42/3x.avif", "name": "catJam"},
                {"link": "https://cdn.7tv.app/emote/01F6N7QDN8000DJW55Q77ZXZ4E/3x.avif", "name": "Awkward"},
                {"link": "https://cdn.7tv.app/emote/01FCJPHMT00008XKZT17QKXE7W/3x.avif", "name": "YesYes"},
                {"link": "https://cdn.7tv.app/emote/01FECSYPZR0002KVMNHJBZWTWH/3x.avif", "name": "PLEASE\n"},
                {"link": "https://cdn.7tv.app/emote/01FC4W70J80005D6HG0ANTP023/3x.avif", "name": "AAAA"},
                {"link": "https://cdn.7tv.app/emote/01GMAH9MB000066S7TTNVB1TGD/3x.avif", "name": "veryCat"},
                {"link": "https://cdn.7tv.app/emote/01GNDAV6R8000ASVTS4W77SX5G/3x.avif", "name": "TheVoices"}
            ]
            self.save_emojis()
        self.config = self.load_config()
        self.hotkey = self.config.get('hotkey', 'ctrl+shift+e')
        self.create_widgets()
        self.hotkey_handle = None
        threading.Thread(target=self.register_hotkey, daemon=True).start()
        self.last_active_window = None
        self.emoji_previews = None  # Cache für die Tkinter-Bilder/Frames

    def invalidate_emoji_previews(self):
        self.emoji_previews = None

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Emoji Picker läuft im Hintergrund. Globaler Hotkey: Strg+Shift+E').pack(anchor='w',
                                                                                                       pady=10)
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
            new_hotkey = simpledialog.askstring('Hotkey ändern', 'Neuen Hotkey eingeben (z.B. ctrl+alt+e):',
                                                initialvalue=self.hotkey)
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

    def get_preview_cache_path(self, url, frame_idx=None):
        ext = 'png'
        h = hashlib.sha256(url.encode('utf-8')).hexdigest()
        if frame_idx is not None:
            return os.path.join(CACHE_DIR_PREVIEW, f'{h}_{frame_idx}.{ext}')
        else:
            return os.path.join(CACHE_DIR_PREVIEW, f'{h}.{ext}')

    def create_emoji_preview_cache(self, emoji):
        """
        Erstellt und speichert eine Vorschau für ein Emoji als PNG im Cache-Verzeichnis.
        Für animierte Emojis werden alle Frames als einzelne PNGs gespeichert.
        Für statische Emojis wird ein einzelnes PNG erzeugt.
        Parameter:
            emoji (dict): Emoji-Daten mit 'link' (Bild-URL) und optional 'name'.
        Verhalten:
            - Lädt das Bild (ggf. aus Cache), skaliert es auf EMOJI_SIZE.
            - Speichert die Vorschau im CACHE_DIR_PREVIEW.
            - Bei Fehlern wird ein Platzhalterbild erzeugt.
        """
        url = emoji['link']
        print(f'[PreviewCache] Starte für {url}')
        img_bytes = self.fetch_and_cache_image(url)
        if img_bytes is None:
            print(f'[PreviewCache] Kein Bild geladen für {url}')
            return
        img_bytes_io = io.BytesIO(img_bytes)
        ext = url.split('.')[-1].lower()
        EMOJI_SIZE = 64
        try:
            pil_img = Image.open(img_bytes_io)
            is_animated = getattr(pil_img, 'is_animated', False)
        except Exception as e:
            print(f'[PreviewCache] Fehler beim Öffnen des Bildes: {e}')
            pil_img = None
            is_animated = False
        if is_animated and pil_img:
            # Animierte Emoji: mehrere PNGs
            try:
                for frame_idx in range(pil_img.n_frames):
                    pil_img.seek(frame_idx)
                    frame = pil_img.copy().resize((EMOJI_SIZE, EMOJI_SIZE))
                    cache_path = self.get_preview_cache_path(url, frame_idx)
                    try:
                        if not os.path.exists(cache_path):
                            frame.save(cache_path, format='PNG')
                            print(f'[PreviewCache] Frame gespeichert: {cache_path}')
                    except Exception as e:
                        print(f'[PreviewCache] Fehler beim Speichern von Frame {frame_idx}: {e}')
            except Exception as e:
                print(f'[PreviewCache] Fehler bei Animationsextraktion: {e}')
        else:
            # Statisches Emoji: ein PNG
            try:
                if pil_img:
                    pil_img.seek(0)
                    img = pil_img.copy().resize((EMOJI_SIZE, EMOJI_SIZE))
                else:
                    img = Image.open(img_bytes_io).resize((EMOJI_SIZE, EMOJI_SIZE))
            except Exception as e:
                print(f'[PreviewCache] Fehler beim Erstellen des statischen Bildes: {e}')
                img = Image.new('RGBA', (EMOJI_SIZE, EMOJI_SIZE), (200, 200, 200, 255))
            cache_path = self.get_preview_cache_path(url)
            try:
                if not os.path.exists(cache_path):
                    img.save(cache_path, format='PNG')
                    print(f'[PreviewCache] Statisches Bild gespeichert: {cache_path}')
            except Exception as e:
                print(f'[PreviewCache] Fehler beim Speichern des statischen Bildes: {e}')

    def open_popover(self):
        # Aktives Fenster merken
        try:
            self.last_active_window = gw.getActiveWindow()
        except Exception:
            self.last_active_window = None
        x, y = pyautogui.position()
        if hasattr(self, 'popover') and self.popover is not None:
            try:
                if self.popover.winfo_exists():
                    self.popover.destroy()
            except Exception:
                pass
            self.popover = None
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
        self.emoji_anim_states = []
        columns = 6
        EMOJI_SIZE = 64

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
                self.invalidate_emoji_previews()

        for idx, emoji in enumerate(self.emoji_list):
            url = emoji['link']
            h = hashlib.sha256(url.encode('utf-8')).hexdigest()
            # Try to load static preview image
            static_frame_path = os.path.join(CACHE_DIR_PREVIEW, f'{h}.png')
            static_photo = None
            if os.path.exists(static_frame_path):
                try:
                    static_img = Image.open(static_frame_path)
                    static_photo = ImageTk.PhotoImage(static_img)
                except Exception:
                    static_photo = None
            # If static preview is missing, try to use first animation frame
            if static_photo is None:
                frame_path = os.path.join(CACHE_DIR_PREVIEW, f'{h}_0.png')
                if os.path.exists(frame_path):
                    try:
                        static_img = Image.open(frame_path)
                        static_photo = ImageTk.PhotoImage(static_img)
                    except Exception:
                        static_photo = None
                static_photo = ImageTk.PhotoImage(Image.new('RGBA', (EMOJI_SIZE, EMOJI_SIZE), (200, 200, 200, 255)))
            if static_photo is None:
                static_photo = ImageTk.PhotoImage(Image.new('RGBA', (64, 64), (200, 200, 200, 255)))
            self.emoji_images.append(static_photo)
            self.emoji_anim_states.append({'frames': None, 'running': False, 'after_id': None})
            btn = tk.Button(grid, image=static_photo, command=lambda l=emoji['link']: self.select_emoji(l), relief='flat', bd=0, highlightthickness=0)
            btn.grid(row=idx // columns, column=idx % columns, padx=4, pady=4)
            def start_animation(event, btn=btn, idx=idx, h=h):
                state = self.emoji_anim_states[idx]
                # Frames nur bei Hover laden
                if state['frames'] is None:
                    frames = []
                    frame_idx = 0
                    while True:
                        frame_path = os.path.join(CACHE_DIR_PREVIEW, f'{h}_{frame_idx}.png')
                        if os.path.exists(frame_path):
                            try:
                                img = Image.open(frame_path)
                                frames.append(ImageTk.PhotoImage(img))
                            except Exception:
                                pass
                            frame_idx += 1
                        else:
                            break
                    if frames:
                        state['frames'] = frames
                    else:
                        state['frames'] = [self.emoji_images[idx]]
                if len(state['frames']) > 1:
                    state['running'] = True
                    def animate(frame_idx=0):
                        if not state['running']:
                            btn.config(image=state['frames'][0])
                            return
                        btn.config(image=state['frames'][frame_idx])
                        state['after_id'] = self.popover.after(80, animate, (frame_idx + 1) % len(state['frames']))
                    animate()
            def stop_animation(event, btn=btn, idx=idx):
                state = self.emoji_anim_states[idx]
                state['running'] = False
                if state['after_id']:
                    self.popover.after_cancel(state['after_id'])
                    state['after_id'] = None
                btn.config(image=self.emoji_images[idx])
                # Animation-Frames aus dem Speicher entfernen (RAM sparen)
                state['frames'] = None
            btn.bind('<Enter>', start_animation)
            btn.bind('<Leave>', stop_animation)
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
        # Link in Zwischenablage und per Ctrl+V einfügen
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
            # Pillow kann AVIF evtl. nicht öffnen, ist ok
            try:
                Image.open(img_bytes)
            except Exception:
                if ext not in ('avif', 'webp'):
                    raise ValueError('Bild konnte nicht geladen werden.')
        except Exception as e:
            messagebox.showerror('Fehler', f'Bild konnte nicht geladen werden: {e}')
            return
        name = simpledialog.askstring('Name (optional)', 'Name für das Emoji (optional):')
        emoji = {'link': url, 'name': name or ''}
        self.emoji_list.append(emoji)
        self.create_emoji_preview_cache(emoji)
        self.save_emojis()
        messagebox.showinfo('Erfolg', 'Emoji hinzugefügt!')
        self.invalidate_emoji_previews()

    def open_data_folder(self):
        # Öffnet den Ordner, in dem Cache und Config liegen
        try:
            os.startfile(BASE_DATA_DIR)
        except Exception as e:
            messagebox.showerror('Fehler', f'Ordner konnte nicht geöffnet werden:\n{e}')

    def run_tray(self):
        def on_open():
            self.root.after(0, self.open_popover)

        def on_add():
            self.root.after(0, self.add_emoji_dialog)

        def on_hotkey():
            self.change_hotkey()

        def on_open_folder():
            self.root.after(0, self.open_data_folder)

        def on_quit():
            self.tray_icon.stop()
            self.root.after(0, self.root.destroy)

        image = PILImage.open(os.path.join(os.path.dirname(__file__), 'tray_icon.png'))
        menu = pystray.Menu(
            pystray.MenuItem('Emoji auswählen', lambda: on_open()),
            pystray.MenuItem('Emoji hinzufügen', lambda: on_add()),
            pystray.MenuItem('Hotkey ändern', lambda: on_hotkey()),
            pystray.MenuItem('Ordner öffnen', lambda: on_open_folder()),
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
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def motion(self, event=None):
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
        label = tk.Label(tw, text=self.text, justify='left', background='#ffffe0', relief='solid', borderwidth=1,
                         font=('tahoma', '8', 'normal'))
        label.pack(ipadx=2)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = EmojiPickerApp(root)
    root.withdraw()
    threading.Thread(target=app.run_tray, daemon=True).start()
    root.mainloop()
