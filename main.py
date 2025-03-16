import sys
import tkinter as tk
from tkinter import ttk, colorchooser
import json
import os
import time
import threading
import random
import numpy as np
import simpleaudio as sa
import datetime


class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        default_config = {
            "clock": {
                "size": [250, 100],
                "font": "Arial",
                "text_size": 36,
                "opacity": 0.8,
                "color": "#FFFFFF",
                "position": [100, 100]
            },
            "alarm": {
                "enabled": False,
                "duration": 3,
                "interval": 30
            },
            "sound": {
                "type": ['sine', 'square', 'sawtooth', 'triangle'],
                "frequency_min": 400,
                "frequency_max": 800
            },
            "dragToMove": True
        }

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return default_config
        else:
            self.save_config(default_config)
            return default_config

    def save_config(self, config=None):
        if config:
            self.config = config
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)


class SoundGenerator:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.playing = False
        self.sample_rate = 44100
        self.play_obj = None
        self._lock = threading.Lock()  # Add a lock for thread safety

    def generate_sine_wave(self, frequency, duration):
        t = np.linspace(0, duration, int(duration * self.sample_rate), False)
        wave = np.sin(2 * np.pi * frequency * t) * 0.5
        return (wave * 32767).astype(np.int16)

    def generate_square_wave(self, frequency, duration):
        t = np.linspace(0, duration, int(duration * self.sample_rate), False)
        wave = np.sign(np.sin(2 * np.pi * frequency * t)) * 0.5
        return (wave * 32767).astype(np.int16)

    def generate_sawtooth_wave(self, frequency, duration):
        t = np.linspace(0, duration, int(duration * self.sample_rate), False)
        wave = 2 * (t * frequency - np.floor(t * frequency + 0.5)) * 0.5
        return (wave * 32767).astype(np.int16)

    def generate_triangle_wave(self, frequency, duration):
        t = np.linspace(0, duration, int(duration * self.sample_rate), False)
        wave = 2 * np.abs(2 * (t * frequency - np.floor(t * frequency + 0.5))) - 1
        wave = wave * 0.5
        return (wave * 32767).astype(np.int16)

    def play_sound(self):
        with self._lock:  # Ensure only one thread modifies state at a time
            if self.playing:
                return  # Don't start a new sound if one is already playi

            sound_config = self.config_manager.config["sound"]
            alarm_config = self.config_manager.config["alarm"]

            # Randomly select a wave type from the available types
            sound_types = sound_config["type"]
            selected_type = random.choice(sound_types)

            # Randomly select a frequency within the specified range
            min_freq = sound_config["frequency_min"]
            max_freq = sound_config["frequency_max"]
            selected_frequency = random.randint(min_freq, max_freq)

            duration = alarm_config["duration"]

            if selected_type == "sine":
                wave = self.generate_sine_wave(selected_frequency, duration)
            elif selected_type == "square":
                wave = self.generate_square_wave(selected_frequency, duration)
            elif selected_type == "sawtooth":
                wave = self.generate_sawtooth_wave(selected_frequency, duration)
            else:  # triangle
                wave = self.generate_triangle_wave(selected_frequency, duration)

            # Convert to stereo
            audio = np.column_stack((wave, wave))

            # Play sound
            if self.play_obj:
                self.play_obj.stop()  # Stop any previous sound

            self.playing = True
            try:
                self.play_obj = sa.play_buffer(audio, 2, 2, self.sample_rate)
                self.play_obj.wait_done()
            except Exception as e:
                print(f"Sound playback error: {e}")
            finally:
                self.playing = False
                # Clear reference to play_obj
                self.play_obj = None


class AlarmManager:
    def __init__(self, config_manager, sound_generator):
        self.config_manager = config_manager
        self.sound_generator = sound_generator
        self.active = False
        self.timer = None

    def start_alarm(self):
        if self.active:
            return

        self.active = True
        self.schedule_next_alarm()

    def stop_alarm(self):
        self.active = False
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def schedule_next_alarm(self):
        if not self.active:
            return

        interval = self.config_manager.config["alarm"]["interval"]

        def alarm_callback():
            # Play sound in a separate thread
            sound_thread = threading.Thread(target=self.sound_generator.play_sound)
            sound_thread.daemon = True
            sound_thread.start()

            # Schedule next alarm from the main callback, not from the sound thread
            if self.active:
                # Use a new timer instead of recursively calling schedule_next_alarm
                self.timer = threading.Timer(interval, alarm_callback)
                self.timer.daemon = True
                self.timer.start()

        # Initial timer setup
        self.timer = threading.Timer(interval, alarm_callback)
        self.timer.daemon = True
        self.timer.start()


class ClockOverlay:
    def __init__(self, config_manager, alarm_manager):
        self.config_manager = config_manager
        self.alarm_manager = alarm_manager

        self.root = tk.Tk()
        self.root.title("Clock Overlay")
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)

        # Set transparency
        win_bg = '#F0F0F1'  # Windows system color for transparency
        self.root.configure(bg=win_bg)
        self.root.wm_attributes('-alpha', self.config_manager.config["clock"]["opacity"])

        # On Windows, we can use transparentcolor for better transparency
        if sys.platform == 'win32':
            self.root.attributes('-transparentcolor', win_bg)

        # Create frame with transparent background
        self.clock_frame = tk.Frame(self.root, bg=win_bg)
        self.clock_frame.pack(fill=tk.BOTH, expand=1)

        clock_config = self.config_manager.config["clock"]
        self.time_label = tk.Label(
            self.clock_frame,
            font=(clock_config["font"], clock_config["text_size"]),
            fg=clock_config["color"],
            bg=win_bg,  # Match transparent color
            anchor='center',
            padx=15,
            pady=10,
            bd=0,  # No border
            highlightthickness=0  # No highlight
        )
        self.time_label.pack(fill=tk.BOTH, expand=1)

        # Set initial size and position
        size = clock_config["size"]
        pos = clock_config["position"]
        self.root.geometry(f"{size[0]}x{size[1]}+{pos[0]}+{pos[1]}")

        # Enable dragging if dragToMove is enabled
        if self.config_manager.config.get("dragToMove", True):
            self.time_label.bind("<Button-1>", self.start_drag)
            self.time_label.bind("<B1-Motion>", self.on_drag)

        # Right-click for settings
        self.time_label.bind("<Button-3>", self.show_settings)

        # Update time
        self.update_time()

    def start_drag(self, event):
        self.x = event.x
        self.y = event.y

    def on_drag(self, event):
        x = self.root.winfo_x() - self.x + event.x
        y = self.root.winfo_y() - self.y + event.y
        self.root.geometry(f"+{x}+{y}")

        # Update position in config and save immediately
        self.config_manager.config["clock"]["position"] = [x, y]
        self.config_manager.save_config()

    def update_time(self):
        current_time = datetime.datetime.now().strftime("%I:%M:%S %p")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def show_settings(self, event):
        settings = SettingsWindow(self.root, self.config_manager, self.alarm_manager)

    def run(self):
        self.root.mainloop()


class SettingsWindow:
    def __init__(self, parent, config_manager, alarm_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.alarm_manager = alarm_manager

        self.window = tk.Toplevel(parent)
        self.window.title("Clock Settings")
        self.window.attributes('-topmost', True)

        notebook = ttk.Notebook(self.window)

        # Clock appearance tab
        appearance_frame = ttk.Frame(notebook)
        notebook.add(appearance_frame, text="Appearance")

        # Size settings
        tk.Label(appearance_frame, text="Width:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.width_var = tk.IntVar(value=self.config_manager.config["clock"]["size"][0])
        tk.Scale(appearance_frame, from_=150, to=500, orient=tk.HORIZONTAL, variable=self.width_var).grid(row=0,
                                                                                                          column=1,
                                                                                                          padx=5,
                                                                                                          pady=5,
                                                                                                          sticky="we")

        tk.Label(appearance_frame, text="Height:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.height_var = tk.IntVar(value=self.config_manager.config["clock"]["size"][1])
        tk.Scale(appearance_frame, from_=80, to=200, orient=tk.HORIZONTAL, variable=self.height_var).grid(row=1,
                                                                                                          column=1,
                                                                                                          padx=5,
                                                                                                          pady=5,
                                                                                                          sticky="we")

        # Font settings
        tk.Label(appearance_frame, text="Font:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        fonts = ["Arial", "Helvetica", "Times", "Courier", "Verdana"]
        self.font_var = tk.StringVar(value=self.config_manager.config["clock"]["font"])
        ttk.Combobox(appearance_frame, textvariable=self.font_var, values=fonts).grid(row=2, column=1, padx=5, pady=5,
                                                                                      sticky="we")

        tk.Label(appearance_frame, text="Text Size:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.text_size_var = tk.IntVar(value=self.config_manager.config["clock"]["text_size"])
        tk.Scale(appearance_frame, from_=10, to=72, orient=tk.HORIZONTAL, variable=self.text_size_var).grid(row=3,
                                                                                                            column=1,
                                                                                                            padx=5,
                                                                                                            pady=5,
                                                                                                            sticky="we")

        # Opacity settings
        tk.Label(appearance_frame, text="Opacity:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.opacity_var = tk.DoubleVar(value=self.config_manager.config["clock"]["opacity"])
        tk.Scale(appearance_frame, from_=0.1, to=1.0, resolution=0.1, orient=tk.HORIZONTAL,
                 variable=self.opacity_var).grid(row=4, column=1, padx=5, pady=5, sticky="we")

        # Color settings
        tk.Label(appearance_frame, text="Text Color:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.color_button = tk.Button(appearance_frame, text="Choose Color", command=self.choose_color)
        self.color_button.grid(row=5, column=1, padx=5, pady=5, sticky="we")
        self.color_button.config(bg=self.config_manager.config["clock"]["color"])

        # Drag to Move setting
        tk.Label(appearance_frame, text="Drag to Move:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.drag_to_move_var = tk.BooleanVar(value=self.config_manager.config.get("dragToMove", True))
        tk.Checkbutton(appearance_frame, variable=self.drag_to_move_var).grid(row=6, column=1, padx=5, pady=5,
                                                                              sticky="w")

        # Alarm settings tab
        alarm_frame = ttk.Frame(notebook)
        notebook.add(alarm_frame, text="Alarm")

        # Alarm enabled
        self.alarm_enabled_var = tk.BooleanVar(value=self.config_manager.config["alarm"]["enabled"])
        tk.Checkbutton(alarm_frame, text="Enable Alarm", variable=self.alarm_enabled_var).grid(row=0, column=0,
                                                                                               columnspan=2, padx=5,
                                                                                               pady=5, sticky="w")

        # Duration settings
        tk.Label(alarm_frame, text="Duration (seconds):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.duration_var = tk.IntVar(value=self.config_manager.config["alarm"]["duration"])
        tk.Scale(alarm_frame, from_=1, to=10, orient=tk.HORIZONTAL, variable=self.duration_var).grid(row=1, column=1,
                                                                                                     padx=5, pady=5,
                                                                                                     sticky="we")

        # Interval settings
        tk.Label(alarm_frame, text="Interval (seconds):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.interval_var = tk.IntVar(value=self.config_manager.config["alarm"]["interval"])
        tk.Scale(alarm_frame, from_=5, to=3600, orient=tk.HORIZONTAL, variable=self.interval_var).grid(row=2, column=1,
                                                                                                       padx=5, pady=5,
                                                                                                       sticky="we")

        # Sound settings tab
        sound_frame = ttk.Frame(notebook)
        notebook.add(sound_frame, text="Sound")

        # Sound type checkboxes
        tk.Label(sound_frame, text="Wave Types:").grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.sound_types_frame = ttk.Frame(sound_frame)
        self.sound_types_frame.grid(row=0, column=1, padx=5, pady=5, sticky="we")

        self.sine_var = tk.BooleanVar(value="sine" in self.config_manager.config["sound"]["type"])
        self.square_var = tk.BooleanVar(value="square" in self.config_manager.config["sound"]["type"])
        self.sawtooth_var = tk.BooleanVar(value="sawtooth" in self.config_manager.config["sound"]["type"])
        self.triangle_var = tk.BooleanVar(value="triangle" in self.config_manager.config["sound"]["type"])

        tk.Checkbutton(self.sound_types_frame, text="Sine", variable=self.sine_var).pack(side=tk.LEFT)
        tk.Checkbutton(self.sound_types_frame, text="Square", variable=self.square_var).pack(side=tk.LEFT)
        tk.Checkbutton(self.sound_types_frame, text="Sawtooth", variable=self.sawtooth_var).pack(side=tk.LEFT)
        tk.Checkbutton(self.sound_types_frame, text="Triangle", variable=self.triangle_var).pack(side=tk.LEFT)

        # Frequency min settings
        tk.Label(sound_frame, text="Min Frequency (Hz):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.freq_min_var = tk.IntVar(value=self.config_manager.config["sound"]["frequency_min"])
        tk.Scale(sound_frame, from_=200, to=1000, orient=tk.HORIZONTAL, variable=self.freq_min_var).grid(row=1,
                                                                                                         column=1,
                                                                                                         padx=5, pady=5,
                                                                                                         sticky="we")

        # Frequency max settings
        tk.Label(sound_frame, text="Max Frequency (Hz):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.freq_max_var = tk.IntVar(value=self.config_manager.config["sound"]["frequency_max"])
        tk.Scale(sound_frame, from_=400, to=2000, orient=tk.HORIZONTAL, variable=self.freq_max_var).grid(row=2,
                                                                                                         column=1,
                                                                                                         padx=5, pady=5,
                                                                                                         sticky="we")

        # Test sound button
        tk.Button(sound_frame, text="Test Sound", command=self.test_sound).grid(row=3, column=0, columnspan=2, padx=5,
                                                                                pady=5, sticky="we")

        notebook.pack(expand=1, fill="both", padx=10, pady=10)

        # Save button
        tk.Button(self.window, text="Save Settings", command=self.save_settings).pack(side=tk.RIGHT, padx=10, pady=10)

        # Center the window
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def choose_color(self):
        color = colorchooser.askcolor(initialcolor=self.config_manager.config["clock"]["color"])[1]
        if color:
            self.color_button.config(bg=color)

    def test_sound(self):
        # Create temporary config
        temp_config = self.config_manager.config.copy()

        # Get selected sound types
        sound_types = []
        if self.sine_var.get():
            sound_types.append("sine")
        if self.square_var.get():
            sound_types.append("square")
        if self.sawtooth_var.get():
            sound_types.append("sawtooth")
        if self.triangle_var.get():
            sound_types.append("triangle")

        # Ensure at least one type is selected
        if not sound_types:
            sound_types = ["sine"]

        temp_config["sound"]["type"] = sound_types
        temp_config["sound"]["frequency_min"] = self.freq_min_var.get()
        temp_config["sound"]["frequency_max"] = self.freq_max_var.get()
        temp_config["alarm"]["duration"] = 1  # Short duration for testing

        # Create temporary sound generator with this config
        sound_generator = SoundGenerator(ConfigManager())
        sound_generator.config_manager.config = temp_config

        # Play sound in separate thread
        threading.Thread(target=sound_generator.play_sound).start()

    def save_settings(self):
        # Update config with new values
        self.config_manager.config["clock"]["size"] = [self.width_var.get(), self.height_var.get()]
        self.config_manager.config["clock"]["font"] = self.font_var.get()
        self.config_manager.config["clock"]["text_size"] = self.text_size_var.get()
        self.config_manager.config["clock"]["opacity"] = self.opacity_var.get()

        # Get color from button
        color = self.color_button.cget("bg")
        self.config_manager.config["clock"]["color"] = color

        # Alarm settings
        old_alarm_enabled = self.config_manager.config["alarm"]["enabled"]
        self.config_manager.config["alarm"]["enabled"] = self.alarm_enabled_var.get()
        self.config_manager.config["alarm"]["duration"] = self.duration_var.get()
        self.config_manager.config["alarm"]["interval"] = self.interval_var.get()

        # Sound settings - get selected types
        sound_types = []
        if self.sine_var.get():
            sound_types.append("sine")
        if self.square_var.get():
            sound_types.append("square")
        if self.sawtooth_var.get():
            sound_types.append("sawtooth")
        if self.triangle_var.get():
            sound_types.append("triangle")

        # Ensure at least one type is selected
        if not sound_types:
            sound_types = ["sine"]

        self.config_manager.config["sound"]["type"] = sound_types
        self.config_manager.config["sound"]["frequency_min"] = self.freq_min_var.get()
        self.config_manager.config["sound"]["frequency_max"] = self.freq_max_var.get()

        # Drag to move setting
        self.config_manager.config["dragToMove"] = self.drag_to_move_var.get()

        # Save to file
        self.config_manager.save_config()

        # Apply changes to clock
        self.parent.wm_attributes('-alpha', self.opacity_var.get())
        self.parent.geometry(
            f"{self.width_var.get()}x{self.height_var.get()}+{self.parent.winfo_x()}+{self.parent.winfo_y()}")

        parent_time_label = self.parent.winfo_children()[0].winfo_children()[0]
        parent_time_label.config(
            font=(self.font_var.get(), self.text_size_var.get()),
            fg=color
        )

        # Update drag bindings based on dragToMove setting
        if self.drag_to_move_var.get():
            parent_time_label.bind("<Button-1>", self.parent.master.start_drag)
            parent_time_label.bind("<B1-Motion>", self.parent.master.on_drag)
        else:
            parent_time_label.unbind("<Button-1>")
            parent_time_label.unbind("<B1-Motion>")

        # Handle alarm state
        if self.alarm_enabled_var.get() and not old_alarm_enabled:
            self.alarm_manager.start_alarm()
        elif not self.alarm_enabled_var.get() and old_alarm_enabled:
            self.alarm_manager.stop_alarm()

        self.window.destroy()


def main():
    config_manager = ConfigManager()
    sound_generator = SoundGenerator(config_manager)
    alarm_manager = AlarmManager(config_manager, sound_generator)

    # Start alarm if enabled in config
    if config_manager.config["alarm"]["enabled"]:
        alarm_manager.start_alarm()

    app = ClockOverlay(config_manager, alarm_manager)
    app.run()


if __name__ == "__main__":
    main()
