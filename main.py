import sys
import json
import os
import time
import threading
import random
import numpy as np
import simpleaudio as sa
import datetime
from PySide6 import QtWidgets, QtGui, QtCore

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
            "countdown": {  # Add new section for countdown clock
                "size": [250, 100],
                "font": "Arial",
                "text_size": 12,
                "opacity": 0.8,
                "color": "#FF0000",  # Red color for countdown by default
                "position": [100, 220]  # Position below the main clock
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
                return  # Don't start a new sound if one is already playing

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
    def __init__(self, config_manager, sound_generator, countdown=None):
        self.config_manager = config_manager
        self.sound_generator = sound_generator
        self.active = False
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.alarm_callback)
        self.last_trigger_time = QtCore.QDateTime.currentMSecsSinceEpoch()
        self.countdown = countdown  # Store reference to countdown window

    # Add a method to set the countdown reference if it wasn't available at initialization
    def set_countdown(self, countdown):
        self.countdown = countdown

    def start_alarm(self):
        if self.active:
            return

        self.active = True
        # Initialize last trigger time
        self.last_trigger_time = QtCore.QDateTime.currentMSecsSinceEpoch()
        interval = self.config_manager.config["alarm"]["interval"] * 1000
        self.timer.start(interval)

        # Show countdown if available
        if self.countdown:
            self.countdown.show()

    def stop_alarm(self):
        self.active = False
        self.timer.stop()

        # Hide countdown if available
        if self.countdown:
            self.countdown.hide()

    def alarm_callback(self):
        # Update last trigger time
        self.last_trigger_time = QtCore.QDateTime.currentMSecsSinceEpoch()

        # Play sound in a separate thread
        sound_thread = threading.Thread(target=self.sound_generator.play_sound)
        sound_thread.daemon = False
        sound_thread.start()

        # Update interval in case it was changed in settings
        interval = self.config_manager.config["alarm"]["interval"] * 1000
        self.timer.setInterval(interval)

class CountdownOverlay(QtWidgets.QMainWindow):
    def __init__(self, config_manager, alarm_manager):
        super().__init__(flags=QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)

        self.config_manager = config_manager
        self.alarm_manager = alarm_manager

        # Create transparent background
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # Create central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create countdown label
        self.countdown_label = QtWidgets.QLabel()
        self.countdown_label.setAlignment(QtCore.Qt.AlignCenter)

        # Set up font from config
        self.apply_config()

        # Add label to layout
        layout.addWidget(self.countdown_label)

        # Update countdown immediately and start timer
        self.update_countdown()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(100)  # Update more frequently for milliseconds

        # Setup drag functionality
        self.drag_enabled = self.config_manager.config.get("dragToMove", True)
        self.dragging = False

        # Right-click context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Initially hide if alarm is disabled
        self.setVisible(self.config_manager.config["alarm"]["enabled"])

    def apply_config(self):
        countdown_config = self.config_manager.config["countdown"]

        # Set size and position
        self.resize(countdown_config["size"][0], countdown_config["size"][1])
        self.move(countdown_config["position"][0], countdown_config["position"][1])

        # Set opacity
        self.setWindowOpacity(countdown_config["opacity"])

        # Configure font and color
        font_family = countdown_config["font"]
        font_size = countdown_config["text_size"]
        color = countdown_config["color"]

        # Create font with anti-aliasing
        font = QtGui.QFont(font_family, font_size)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.countdown_label.setFont(font)

        # Set text color
        self.countdown_label.setStyleSheet(f"color: {color}; background-color: transparent;")

    def update_countdown(self):
        if not self.alarm_manager.active:
            self.hide()
            return
        else:
            self.show()

        # Calculate time until next alarm
        interval_ms = self.config_manager.config["alarm"]["interval"] * 1000
        current_time = QtCore.QDateTime.currentMSecsSinceEpoch()
        elapsed_ms = (current_time - self.alarm_manager.last_trigger_time) % interval_ms
        remaining_ms = interval_ms - elapsed_ms

        # Convert to hours, minutes, seconds, milliseconds
        hours = remaining_ms // 3600000
        minutes = (remaining_ms % 3600000) // 60000
        seconds = (remaining_ms % 60000) // 1000
        millis = remaining_ms % 1000

        # Format the display
        countdown_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"
        self.countdown_label.setText(countdown_text)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.drag_enabled:
            self.dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() & QtCore.Qt.LeftButton and self.drag_enabled:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            # Update position in config
            self.config_manager.config["countdown"]["position"] = [self.x(), self.y()]
            self.config_manager.save_config()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False

    def show_context_menu(self, point):
        context_menu = QtWidgets.QMenu(self)
        settings_action = context_menu.addAction("Settings")
        quit_action = context_menu.addAction("Quit")

        action = context_menu.exec(self.mapToGlobal(point))
        if action == settings_action:
            # Find clock window
            clock = None
            for widget in QtWidgets.QApplication.allWidgets():
                if isinstance(widget, ClockOverlay):
                    clock = widget
                    break
            settings_window = SettingsWindow(self, self.config_manager, self.alarm_manager,
                                             clock=clock, countdown=self)
            settings_window.exec()
        elif action == quit_action:
            QtWidgets.QApplication.instance().quit()

class ClockOverlay(QtWidgets.QMainWindow):
    def __init__(self, config_manager, alarm_manager):
        super().__init__(flags=QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)

        self.config_manager = config_manager
        self.alarm_manager = alarm_manager

        # Create transparent background
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # Create central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Create layout
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create time label
        self.time_label = QtWidgets.QLabel()
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)

        # Set up font from config
        self.apply_config()

        # Add label to layout
        layout.addWidget(self.time_label)

        # Update time immediately and start timer
        self.update_time()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

        # Setup drag functionality
        self.drag_enabled = self.config_manager.config.get("dragToMove", True)
        self.dragging = False

        # Right-click context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def apply_config(self):
        clock_config = self.config_manager.config["clock"]

        # Set size and position
        self.resize(clock_config["size"][0], clock_config["size"][1])
        self.move(clock_config["position"][0], clock_config["position"][1])

        # Set opacity
        self.setWindowOpacity(clock_config["opacity"])

        # Configure font and color
        font_family = clock_config["font"]
        font_size = clock_config["text_size"]
        color = clock_config["color"]

        # Create font with anti-aliasing
        font = QtGui.QFont(font_family, font_size)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.time_label.setFont(font)

        # Set text color
        self.time_label.setStyleSheet(f"color: {color}; background-color: transparent;")

    def update_time(self):
        current_time = datetime.datetime.now().strftime("%I:%M:%S %p")
        self.time_label.setText(current_time)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.drag_enabled:
            self.dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() & QtCore.Qt.LeftButton and self.drag_enabled:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            # Update position in config
            self.config_manager.config["clock"]["position"] = [self.x(), self.y()]
            self.config_manager.save_config()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False

    def show_context_menu(self, point):
        context_menu = QtWidgets.QMenu(self)
        settings_action = context_menu.addAction("Settings")
        quit_action = context_menu.addAction("Quit")

        action = context_menu.exec(self.mapToGlobal(point))
        if action == settings_action:
            # Find countdown window
            countdown = None
            for widget in QtWidgets.QApplication.allWidgets():
                if isinstance(widget, CountdownOverlay):
                    countdown = widget
                    break
            settings_window = SettingsWindow(self, self.config_manager, self.alarm_manager,
                                             clock=self, countdown=countdown)
            settings_window.exec()
        elif action == quit_action:
            QtWidgets.QApplication.instance().quit()

class FontComboBox(QtWidgets.QComboBox):
    """Custom combobox specifically for font selection with search capabilities"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)  # Don't add search text as an item

        # Configure completer for better search
        completer = self.completer()
        completer.setFilterMode(QtCore.Qt.MatchContains)  # Match anywhere in the text
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)  # Case insensitive matching

        # Set reasonable max visible items
        self.setMaxVisibleItems(15)

        # Load preview delegate
        self.setItemDelegate(FontItemDelegate(self))

    def populate_fonts(self):
        """Get all system fonts and populate the combobox"""
        self.clear()

        # Get all installed fonts
        font_db = QtGui.QFontDatabase
        all_fonts = sorted(font_db.families())

        # Filter out incompatible fonts and add remaining ones
        compatible_fonts = []
        for font in all_fonts:
            if self.is_compatible_font(font):
                compatible_fonts.append(font)
                # Add font to combobox with font preview
                self.addItem(font)
                # Set the item's font to itself for preview
                self.setItemData(self.count() - 1, QtGui.QFont(font), QtCore.Qt.FontRole)

        return compatible_fonts

    def is_compatible_font(self, font_name):
        """Check if a font is likely compatible with our clock application"""
        # Common patterns for emoji, symbol, or decorative fonts to exclude
        excluded_patterns = [
            "emoji", "symbol", "webdings", "wingdings", "dingbat",
            "awesome", "icon", "glyph", "math", "braille", "pictograph"
        ]

        # Check if font name contains excluded patterns
        lower_name = font_name.lower()
        for pattern in excluded_patterns:
            if pattern in lower_name:
                return False

        # Test if font can render basic text
        try:
            test_font = QtGui.QFont(font_name)
            # Check if font can render basic characters
            font_db = QtGui.QFontDatabase
            if not font_db.hasFamily(font_name):
                return False

            # Additional check: if font defaults to a fallback font, it might be special purpose
            test_font.setStyleHint(QtGui.QFont.AnyStyle, QtGui.QFont.PreferMatch)
            if test_font.exactMatch():
                return True

            # If we can't get an exact match, use some additional filtering
            # Additional check for CJK fonts, monospaced fonts, etc.
            # This is just a basic heuristic and might need adjustment
            if ('mono' in lower_name or 'cjk' in lower_name or
                    'sans' in lower_name or 'serif' in lower_name):
                return True

            return True  # Include by default if above checks pass
        except:
            return False

class FontItemDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate to render font names in their own font"""

    def paint(self, painter, option, index):
        # Get the font for this item
        item_font = index.data(QtCore.Qt.FontRole)
        if item_font:
            # Create a copy of the option to modify
            option_copy = QtWidgets.QStyleOptionViewItem(option)

            # Set the font for painting
            option_copy.font = item_font

            # Handle selection state
            if option.state & QtWidgets.QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
                painter.setPen(option.palette.highlightedText().color())
            else:
                painter.setPen(option.palette.text().color())

            # Draw the text
            painter.setFont(item_font)
            text = index.data(QtCore.Qt.DisplayRole)
            painter.drawText(option.rect.adjusted(5, 2, -5, -2), QtCore.Qt.AlignVCenter, text)
        else:
            # Fall back to default rendering if no font is set
            super().paint(painter, option, index)

class SettingsWindow(QtWidgets.QDialog):
    def __init__(self, parent, config_manager, alarm_manager, clock=None, countdown=None):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = config_manager
        self.alarm_manager = alarm_manager
        self.clock = clock
        self.countdown = countdown

        # If clock or countdown isn't provided, try to infer them from parent
        if self.clock is None and isinstance(parent, ClockOverlay):
            self.clock = parent
        if self.countdown is None and isinstance(parent, CountdownOverlay):
            self.countdown = parent

        # Set window properties
        self.setWindowTitle("Clock Settings")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(400)  # Ensure dialog is wide enough for font list

        # Create tab widget
        tab_widget = QtWidgets.QTabWidget()

        # Create tabs
        appearance_tab = self.create_appearance_tab()
        alarm_tab = self.create_alarm_tab()
        sound_tab = self.create_sound_tab()
        countdown_tab = self.create_countdown_tab()  # Add new tab

        # Add tabs to widget
        tab_widget.addTab(appearance_tab, "Main Clock")
        tab_widget.addTab(countdown_tab, "Countdown")  # Add new tab
        tab_widget.addTab(alarm_tab, "Alarm")
        tab_widget.addTab(sound_tab, "Sound")

        # Create buttons
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)

        # Create layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(tab_widget)
        layout.addWidget(button_box)
        self.setLayout(layout)

        # Default size
        self.resize(500, 500)

    def create_appearance_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()

        # Width
        self.width_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.width_slider.setRange(150, 500)
        self.width_slider.setValue(self.config_manager.config["clock"]["size"][0])

        self.width_spinbox = QtWidgets.QSpinBox()
        self.width_spinbox.setRange(150, 500)
        self.width_spinbox.setValue(self.width_slider.value())
        self.width_spinbox.setSuffix(" px")

        # Connect for two-way synchronization
        self.width_slider.valueChanged.connect(self.width_spinbox.setValue)
        self.width_spinbox.valueChanged.connect(self.width_slider.setValue)

        width_layout = QtWidgets.QHBoxLayout()
        width_layout.addWidget(self.width_slider)
        width_layout.addWidget(self.width_spinbox)
        layout.addRow("Width:", width_layout)

        # Height
        self.height_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.height_slider.setRange(80, 200)
        self.height_slider.setValue(self.config_manager.config["clock"]["size"][1])

        self.height_spinbox = QtWidgets.QSpinBox()
        self.height_spinbox.setRange(80, 200)
        self.height_spinbox.setValue(self.height_slider.value())
        self.height_spinbox.setSuffix(" px")

        # Connect for two-way synchronization
        self.height_slider.valueChanged.connect(self.height_spinbox.setValue)
        self.height_spinbox.valueChanged.connect(self.height_slider.setValue)

        height_layout = QtWidgets.QHBoxLayout()
        height_layout.addWidget(self.height_slider)
        height_layout.addWidget(self.height_spinbox)
        layout.addRow("Height:", height_layout)

        # Font with loading indicator and system font scanning
        font_layout = QtWidgets.QVBoxLayout()
        font_label = QtWidgets.QLabel("Loading system fonts...")
        self.font_combo = FontComboBox()
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo)
        layout.addRow("Font:", font_layout)

        # Add a loading effect and load fonts in a separate thread
        self.load_fonts_thread = threading.Thread(target=self.load_system_fonts, args=(font_label,))
        self.load_fonts_thread.daemon = True
        self.load_fonts_thread.start()

        # Text Size
        self.text_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.text_size_slider.setRange(10, 72)
        self.text_size_slider.setValue(self.config_manager.config["clock"]["text_size"])

        self.text_size_spinbox = QtWidgets.QSpinBox()
        self.text_size_spinbox.setRange(10, 72)
        self.text_size_spinbox.setValue(self.text_size_slider.value())
        self.text_size_spinbox.setSuffix(" pt")

        # Connect for two-way synchronization
        self.text_size_slider.valueChanged.connect(self.text_size_spinbox.setValue)
        self.text_size_spinbox.valueChanged.connect(self.text_size_slider.setValue)

        text_size_layout = QtWidgets.QHBoxLayout()
        text_size_layout.addWidget(self.text_size_slider)
        text_size_layout.addWidget(self.text_size_spinbox)
        layout.addRow("Text Size:", text_size_layout)

        # Opacity
        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setRange(1, 10)
        self.opacity_slider.setValue(int(self.config_manager.config["clock"]["opacity"] * 10))

        self.opacity_spinbox = QtWidgets.QDoubleSpinBox()
        self.opacity_spinbox.setRange(0.1, 1.0)
        self.opacity_spinbox.setSingleStep(0.1)
        self.opacity_spinbox.setDecimals(1)
        self.opacity_spinbox.setValue(self.opacity_slider.value() / 10)

        # Connect with conversion between slider int value and spinbox decimal
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_spinbox.setValue(v / 10))
        self.opacity_spinbox.valueChanged.connect(lambda v: self.opacity_slider.setValue(int(v * 10)))

        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_spinbox)
        layout.addRow("Opacity:", opacity_layout)

        # Text Color
        self.color_button = QtWidgets.QPushButton()
        current_color = self.config_manager.config["clock"]["color"]
        self.color_button.setStyleSheet(f"background-color: {current_color}; min-width: 60px; min-height: 30px;")
        self.color_button.clicked.connect(self.choose_color)
        layout.addRow("Text Color:", self.color_button)

        # Drag to Move
        self.drag_checkbox = QtWidgets.QCheckBox()
        self.drag_checkbox.setChecked(self.config_manager.config.get("dragToMove", True))
        layout.addRow("Drag to Move:", self.drag_checkbox)

        # Font preview
        self.preview_frame = QtWidgets.QFrame()
        self.preview_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.preview_frame.setMinimumHeight(60)
        self.preview_layout = QtWidgets.QVBoxLayout(self.preview_frame)

        self.preview_label = QtWidgets.QLabel("12:34:56 PM")
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_layout.addWidget(self.preview_label)

        layout.addRow("Preview:", self.preview_frame)

        # Connect signals for live preview
        self.font_combo.currentTextChanged.connect(self.update_preview)
        self.text_size_slider.valueChanged.connect(self.update_preview)
        self.color_button.clicked.connect(self.update_preview)

        # Initial preview update
        QtCore.QTimer.singleShot(100, self.update_preview)

        tab.setLayout(layout)
        return tab

    def load_system_fonts(self, loading_label):
        """Load system fonts in a separate thread to avoid UI freezing"""
        try:
            # Update UI from main thread
            QtCore.QMetaObject.invokeMethod(loading_label, "setText",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, "Scanning system fonts..."))

            # This might take a moment
            compatible_fonts = self.font_combo.populate_fonts()

            # Get current font
            current_font = self.config_manager.config["clock"]["font"]

            # Update combo box selection from main thread
            QtCore.QMetaObject.invokeMethod(self.font_combo, "setCurrentText",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, current_font))

            # Update label from main thread
            QtCore.QMetaObject.invokeMethod(loading_label, "setText",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, f"Found {len(compatible_fonts)} compatible fonts"))

            # Update preview when fonts are loaded - use QTimer instead
            QtCore.QTimer.singleShot(0, self.update_preview)

        except Exception as e:
            print(f"Error loading fonts: {e}")
            # Update UI from main thread
            QtCore.QMetaObject.invokeMethod(loading_label, "setText",
                                            QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, f"Error loading fonts: {e}"))

    def update_preview(self):
        """Update the font preview based on current settings"""
        try:
            # Get current settings
            font_name = self.font_combo.currentText()
            font_size = self.text_size_slider.value()

            # Get color from button
            color_style = self.color_button.styleSheet()
            color = color_style.split("background-color:")[1].split(";")[0].strip()

            # Create font
            font = QtGui.QFont(font_name, font_size)
            font.setStyleStrategy(QtGui.QFont.PreferAntialias)

            # Update preview
            self.preview_label.setFont(font)
            self.preview_label.setStyleSheet(f"color: {color};")
        except Exception as e:
            print(f"Error updating preview: {e}")

    def create_alarm_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()

        # Alarm Enabled checkbox (unchanged)
        self.alarm_checkbox = QtWidgets.QCheckBox()
        self.alarm_checkbox.setChecked(self.config_manager.config["alarm"]["enabled"])
        layout.addRow("Enable Alarm:", self.alarm_checkbox)

        # Duration (with decimal control as requested earlier)
        self.duration_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.duration_slider.setRange(1, 100)  # Range from 0.1 to 10.0 seconds
        current_duration = self.config_manager.config["alarm"]["duration"]
        self.duration_slider.setValue(int(current_duration * 10))  # Convert to slider value

        self.duration_spinbox = QtWidgets.QDoubleSpinBox()
        self.duration_spinbox.setRange(0.1, 10.0)
        self.duration_spinbox.setSingleStep(0.1)
        self.duration_spinbox.setDecimals(1)
        self.duration_spinbox.setValue(current_duration)
        self.duration_spinbox.setSuffix(" sec")

        # Connect for two-way synchronization
        self.duration_slider.valueChanged.connect(lambda v: self.duration_spinbox.setValue(v / 10.0))
        self.duration_spinbox.valueChanged.connect(lambda v: self.duration_slider.setValue(int(v * 10)))

        duration_layout = QtWidgets.QHBoxLayout()
        duration_layout.addWidget(self.duration_slider)
        duration_layout.addWidget(self.duration_spinbox)
        layout.addRow("Duration:", duration_layout)

        # Interval - NEW HH:MM:SS CONTROLS
        interval_layout = QtWidgets.QHBoxLayout()

        # Convert total seconds to hours, minutes, seconds
        total_seconds = self.config_manager.config["alarm"]["interval"]
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        # Hours
        self.hours_spinbox = QtWidgets.QSpinBox()
        self.hours_spinbox.setRange(0, 23)
        self.hours_spinbox.setValue(hours)
        self.hours_spinbox.setSuffix(" h")
        self.hours_spinbox.setFixedWidth(70)

        # Minutes
        self.minutes_spinbox = QtWidgets.QSpinBox()
        self.minutes_spinbox.setRange(0, 59)
        self.minutes_spinbox.setValue(minutes)
        self.minutes_spinbox.setSuffix(" m")
        self.minutes_spinbox.setFixedWidth(70)

        # Seconds
        self.seconds_spinbox = QtWidgets.QSpinBox()
        self.seconds_spinbox.setRange(0, 59)
        self.seconds_spinbox.setValue(seconds)
        self.seconds_spinbox.setSuffix(" s")
        self.seconds_spinbox.setFixedWidth(70)

        # Add labels and spinboxes to layout
        interval_layout.addWidget(self.hours_spinbox)
        interval_layout.addWidget(QtWidgets.QLabel(":"))
        interval_layout.addWidget(self.minutes_spinbox)
        interval_layout.addWidget(QtWidgets.QLabel(":"))
        interval_layout.addWidget(self.seconds_spinbox)
        interval_layout.addStretch()

        layout.addRow("Interval:", interval_layout)

        # Prevent setting all values to zero
        def check_all_zeros():
            if (self.hours_spinbox.value() == 0 and
                    self.minutes_spinbox.value() == 0 and
                    self.seconds_spinbox.value() == 0):
                self.seconds_spinbox.setValue(5)  # Minimum 5 seconds

        self.hours_spinbox.valueChanged.connect(check_all_zeros)
        self.minutes_spinbox.valueChanged.connect(check_all_zeros)
        self.seconds_spinbox.valueChanged.connect(check_all_zeros)

        tab.setLayout(layout)
        return tab

    def create_sound_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()

        # Wave Types
        wave_types_group = QtWidgets.QGroupBox("Wave Types")
        wave_types_layout = QtWidgets.QGridLayout()  # Changed to grid layout

        self.sine_checkbox = QtWidgets.QCheckBox("Sine")
        self.square_checkbox = QtWidgets.QCheckBox("Square")
        self.sawtooth_checkbox = QtWidgets.QCheckBox("Sawtooth")
        self.triangle_checkbox = QtWidgets.QCheckBox("Triangle")

        current_types = self.config_manager.config["sound"]["type"]
        self.sine_checkbox.setChecked("sine" in current_types)
        self.square_checkbox.setChecked("square" in current_types)
        self.sawtooth_checkbox.setChecked("sawtooth" in current_types)
        self.triangle_checkbox.setChecked("triangle" in current_types)

        # Create test buttons for each wave type
        sine_test_button = QtWidgets.QPushButton("Test")
        sine_test_button.clicked.connect(lambda: self.test_sound("sine"))
        square_test_button = QtWidgets.QPushButton("Test")
        square_test_button.clicked.connect(lambda: self.test_sound("square"))
        sawtooth_test_button = QtWidgets.QPushButton("Test")
        sawtooth_test_button.clicked.connect(lambda: self.test_sound("sawtooth"))
        triangle_test_button = QtWidgets.QPushButton("Test")
        triangle_test_button.clicked.connect(lambda: self.test_sound("triangle"))

        # Add to layout in a grid format
        wave_types_layout.addWidget(self.sine_checkbox, 0, 0)
        wave_types_layout.addWidget(sine_test_button, 0, 1)
        wave_types_layout.addWidget(self.square_checkbox, 1, 0)
        wave_types_layout.addWidget(square_test_button, 1, 1)
        wave_types_layout.addWidget(self.sawtooth_checkbox, 2, 0)
        wave_types_layout.addWidget(sawtooth_test_button, 2, 1)
        wave_types_layout.addWidget(self.triangle_checkbox, 3, 0)
        wave_types_layout.addWidget(triangle_test_button, 3, 1)

        wave_types_group.setLayout(wave_types_layout)
        layout.addRow(wave_types_group)

        # Min Frequency
        self.freq_min_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.freq_min_slider.setRange(200, 1000)
        self.freq_min_slider.setValue(self.config_manager.config["sound"]["frequency_min"])

        self.freq_min_spinbox = QtWidgets.QSpinBox()
        self.freq_min_spinbox.setRange(200, 1000)
        self.freq_min_spinbox.setValue(self.freq_min_slider.value())
        self.freq_min_spinbox.setSuffix(" Hz")

        # Connect for two-way synchronization
        self.freq_min_slider.valueChanged.connect(self.freq_min_spinbox.setValue)
        self.freq_min_spinbox.valueChanged.connect(self.freq_min_slider.setValue)

        freq_min_layout = QtWidgets.QHBoxLayout()
        freq_min_layout.addWidget(self.freq_min_slider)
        freq_min_layout.addWidget(self.freq_min_spinbox)
        layout.addRow("Min Frequency:", freq_min_layout)

        # Max Frequency
        self.freq_max_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.freq_max_slider.setRange(400, 2000)
        self.freq_max_slider.setValue(self.config_manager.config["sound"]["frequency_max"])

        self.freq_max_spinbox = QtWidgets.QSpinBox()
        self.freq_max_spinbox.setRange(400, 2000)
        self.freq_max_spinbox.setValue(self.freq_max_slider.value())
        self.freq_max_spinbox.setSuffix(" Hz")

        # Connect for two-way synchronization
        self.freq_max_slider.valueChanged.connect(self.freq_max_spinbox.setValue)
        self.freq_max_spinbox.valueChanged.connect(self.freq_max_slider.setValue)

        freq_max_layout = QtWidgets.QHBoxLayout()
        freq_max_layout.addWidget(self.freq_max_slider)
        freq_max_layout.addWidget(self.freq_max_spinbox)
        layout.addRow("Max Frequency:", freq_max_layout)

        # Test All Sounds Button (optional)
        test_all_button = QtWidgets.QPushButton("Test All Selected")
        test_all_button.clicked.connect(lambda: self.test_sound())
        layout.addRow(test_all_button)

        tab.setLayout(layout)
        return tab

    def create_countdown_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()

        # Width
        self.countdown_width_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.countdown_width_slider.setRange(150, 500)
        self.countdown_width_slider.setValue(self.config_manager.config["countdown"]["size"][0])

        self.countdown_width_spinbox = QtWidgets.QSpinBox()
        self.countdown_width_spinbox.setRange(150, 500)
        self.countdown_width_spinbox.setValue(self.countdown_width_slider.value())
        self.countdown_width_spinbox.setSuffix(" px")

        # Connect for two-way synchronization
        self.countdown_width_slider.valueChanged.connect(self.countdown_width_spinbox.setValue)
        self.countdown_width_spinbox.valueChanged.connect(self.countdown_width_slider.setValue)

        width_layout = QtWidgets.QHBoxLayout()
        width_layout.addWidget(self.countdown_width_slider)
        width_layout.addWidget(self.countdown_width_spinbox)
        layout.addRow("Width:", width_layout)

        # Height
        self.countdown_height_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.countdown_height_slider.setRange(80, 200)
        self.countdown_height_slider.setValue(self.config_manager.config["countdown"]["size"][1])

        self.countdown_height_spinbox = QtWidgets.QSpinBox()
        self.countdown_height_spinbox.setRange(80, 200)
        self.countdown_height_spinbox.setValue(self.countdown_height_slider.value())
        self.countdown_height_spinbox.setSuffix(" px")

        # Connect for two-way synchronization
        self.countdown_height_slider.valueChanged.connect(self.countdown_height_spinbox.setValue)
        self.countdown_height_spinbox.valueChanged.connect(self.countdown_height_slider.setValue)

        height_layout = QtWidgets.QHBoxLayout()
        height_layout.addWidget(self.countdown_height_slider)
        height_layout.addWidget(self.countdown_height_spinbox)
        layout.addRow("Height:", height_layout)

        # Font (use the same font combo system as the main clock)
        self.countdown_font_combo = FontComboBox()
        layout.addRow("Font:", self.countdown_font_combo)

        # Populate font combo after fonts are loaded in main tab
        QtCore.QTimer.singleShot(1000, self.populate_countdown_fonts)

        # Text Size
        self.countdown_text_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.countdown_text_size_slider.setRange(10, 72)
        self.countdown_text_size_slider.setValue(self.config_manager.config["countdown"]["text_size"])

        self.countdown_text_size_spinbox = QtWidgets.QSpinBox()
        self.countdown_text_size_spinbox.setRange(10, 72)
        self.countdown_text_size_spinbox.setValue(self.countdown_text_size_slider.value())
        self.countdown_text_size_spinbox.setSuffix(" pt")

        # Connect for two-way synchronization
        self.countdown_text_size_slider.valueChanged.connect(self.countdown_text_size_spinbox.setValue)
        self.countdown_text_size_spinbox.valueChanged.connect(self.countdown_text_size_slider.setValue)

        text_size_layout = QtWidgets.QHBoxLayout()
        text_size_layout.addWidget(self.countdown_text_size_slider)
        text_size_layout.addWidget(self.countdown_text_size_spinbox)
        layout.addRow("Text Size:", text_size_layout)

        # Opacity
        self.countdown_opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.countdown_opacity_slider.setRange(1, 10)
        self.countdown_opacity_slider.setValue(int(self.config_manager.config["countdown"]["opacity"] * 10))

        self.countdown_opacity_spinbox = QtWidgets.QDoubleSpinBox()
        self.countdown_opacity_spinbox.setRange(0.1, 1.0)
        self.countdown_opacity_spinbox.setSingleStep(0.1)
        self.countdown_opacity_spinbox.setDecimals(1)
        self.countdown_opacity_spinbox.setValue(self.countdown_opacity_slider.value() / 10)

        # Connect with conversion between slider int value and spinbox decimal
        self.countdown_opacity_slider.valueChanged.connect(lambda v: self.countdown_opacity_spinbox.setValue(v / 10))
        self.countdown_opacity_spinbox.valueChanged.connect(
            lambda v: self.countdown_opacity_slider.setValue(int(v * 10)))

        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_layout.addWidget(self.countdown_opacity_slider)
        opacity_layout.addWidget(self.countdown_opacity_spinbox)
        layout.addRow("Opacity:", opacity_layout)

        # Text Color
        self.countdown_color_button = QtWidgets.QPushButton()
        current_color = self.config_manager.config["countdown"]["color"]
        self.countdown_color_button.setStyleSheet(
            f"background-color: {current_color}; min-width: 60px; min-height: 30px;")
        self.countdown_color_button.clicked.connect(self.choose_countdown_color)
        layout.addRow("Text Color:", self.countdown_color_button)

        # Font preview
        self.countdown_preview_frame = QtWidgets.QFrame()
        self.countdown_preview_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.countdown_preview_frame.setMinimumHeight(60)
        self.countdown_preview_layout = QtWidgets.QVBoxLayout(self.countdown_preview_frame)

        self.countdown_preview_label = QtWidgets.QLabel("00:00:30.00")
        self.countdown_preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.countdown_preview_layout.addWidget(self.countdown_preview_label)

        layout.addRow("Preview:", self.countdown_preview_frame)

        # Connect signals for live preview
        self.countdown_font_combo.currentTextChanged.connect(self.update_countdown_preview)
        self.countdown_text_size_slider.valueChanged.connect(self.update_countdown_preview)
        self.countdown_color_button.clicked.connect(self.update_countdown_preview)

        # Initial preview update
        QtCore.QTimer.singleShot(500, self.update_countdown_preview)

        tab.setLayout(layout)
        return tab

    def populate_countdown_fonts(self):
        """Populate countdown font combo with the same fonts"""
        try:
            # Populate with the same fonts as the main combo
            self.countdown_font_combo.populate_fonts()
            # Set current font
            current_font = self.config_manager.config["countdown"]["font"]
            self.countdown_font_combo.setCurrentText(current_font)
        except Exception as e:
            print(f"Error populating countdown fonts: {e}")

    def choose_countdown_color(self):
        current_color = self.config_manager.config["countdown"]["color"]
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current_color), self, "Choose Countdown Text Color")
        if color.isValid():
            self.countdown_color_button.setStyleSheet(
                f"background-color: {color.name()}; min-width: 60px; min-height: 30px;")
            self.update_countdown_preview()

    def update_countdown_preview(self):
        """Update the countdown font preview based on current settings"""
        try:
            # Get current settings
            font_name = self.countdown_font_combo.currentText()
            font_size = self.countdown_text_size_slider.value()

            # Get color from button
            color_style = self.countdown_color_button.styleSheet()
            color = color_style.split("background-color:")[1].split(";")[0].strip()

            # Create font
            font = QtGui.QFont(font_name, font_size)
            font.setStyleStrategy(QtGui.QFont.PreferAntialias)

            # Update preview
            self.countdown_preview_label.setFont(font)
            self.countdown_preview_label.setStyleSheet(f"color: {color};")
        except Exception as e:
            print(f"Error updating countdown preview: {e}")

    def choose_color(self):
        current_color = self.config_manager.config["clock"]["color"]
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current_color), self, "Choose Text Color")
        if color.isValid():
            self.color_button.setStyleSheet(f"background-color: {color.name()}; min-width: 60px; min-height: 30px;")
            self.update_preview()

    def test_sound(self, sound_type=None):
        # Create temporary config
        temp_config = self.config_manager.config.copy()

        # Get selected sound types or use the provided one
        if sound_type:
            sound_types = [sound_type]
        else:
            sound_types = []
            if self.sine_checkbox.isChecked():
                sound_types.append("sine")
            if self.square_checkbox.isChecked():
                sound_types.append("square")
            if self.sawtooth_checkbox.isChecked():
                sound_types.append("sawtooth")
            if self.triangle_checkbox.isChecked():
                sound_types.append("triangle")

        # Ensure at least one type is selected
        if not sound_types:
            sound_types = ["sine"]

        temp_config["sound"]["type"] = sound_types
        temp_config["sound"]["frequency_min"] = self.freq_min_slider.value()
        temp_config["sound"]["frequency_max"] = self.freq_max_slider.value()
        temp_config["alarm"]["duration"] = 1.0  # Short duration for testing

        # Create temporary config manager with this config
        temp_config_manager = ConfigManager()
        temp_config_manager.config = temp_config

        # Create temporary sound generator
        sound_generator = SoundGenerator(temp_config_manager)

        # Play sound in separate thread
        threading.Thread(target=sound_generator.play_sound).start()

    def save_settings(self):
        # Get color from button
        color_style = self.color_button.styleSheet()
        color = color_style.split("background-color:")[1].split(";")[0].strip()

        # Update config with new values - now using spinbox values for precision
        self.config_manager.config["clock"]["size"] = [self.width_spinbox.value(), self.height_spinbox.value()]
        self.config_manager.config["clock"]["font"] = self.font_combo.currentText()
        self.config_manager.config["clock"]["text_size"] = self.text_size_spinbox.value()
        self.config_manager.config["clock"]["opacity"] = self.opacity_spinbox.value()
        self.config_manager.config["clock"]["color"] = color
        self.config_manager.config["dragToMove"] = self.drag_checkbox.isChecked()

        # Save countdown settings
        self.config_manager.config["countdown"]["size"] = [
            self.countdown_width_spinbox.value(),
            self.countdown_height_spinbox.value()
        ]
        self.config_manager.config["countdown"]["font"] = self.countdown_font_combo.currentText()
        self.config_manager.config["countdown"]["text_size"] = self.countdown_text_size_spinbox.value()
        self.config_manager.config["countdown"]["opacity"] = self.countdown_opacity_spinbox.value()

        # Get color from button
        countdown_color_style = self.countdown_color_button.styleSheet()
        countdown_color = countdown_color_style.split("background-color:")[1].split(";")[0].strip()
        self.config_manager.config["countdown"]["color"] = countdown_color

        # Alarm settings
        old_alarm_enabled = self.config_manager.config["alarm"]["enabled"]
        self.config_manager.config["alarm"]["enabled"] = self.alarm_checkbox.isChecked()
        self.config_manager.config["alarm"]["duration"] = self.duration_spinbox.value()

        # Convert HH:MM:SS to total seconds for interval
        total_seconds = (self.hours_spinbox.value() * 3600 +
                         self.minutes_spinbox.value() * 60 +
                         self.seconds_spinbox.value())
        # Ensure minimum interval of 5 seconds
        if total_seconds < 5:
            total_seconds = 5
        self.config_manager.config["alarm"]["interval"] = total_seconds

        # Sound settings
        sound_types = []
        if self.sine_checkbox.isChecked():
            sound_types.append("sine")
        if self.square_checkbox.isChecked():
            sound_types.append("square")
        if self.sawtooth_checkbox.isChecked():
            sound_types.append("sawtooth")
        if self.triangle_checkbox.isChecked():
            sound_types.append("triangle")

        # Ensure at least one type is selected
        if not sound_types:
            sound_types = ["sine"]

        self.config_manager.config["sound"]["type"] = sound_types
        self.config_manager.config["sound"]["frequency_min"] = self.freq_min_spinbox.value()
        self.config_manager.config["sound"]["frequency_max"] = self.freq_max_spinbox.value()

        # Save to file
        self.config_manager.save_config()

        # Apply changes to both windows if they exist
        if self.clock:
            self.clock.apply_config()
            self.clock.drag_enabled = self.drag_checkbox.isChecked()

        if self.countdown:
            self.countdown.apply_config()
            self.countdown.drag_enabled = self.drag_checkbox.isChecked()

        # Handle alarm state - this will take care of showing/hiding the countdown
        if self.alarm_checkbox.isChecked() and not old_alarm_enabled:
            self.alarm_manager.start_alarm()
        elif not self.alarm_checkbox.isChecked() and old_alarm_enabled:
            self.alarm_manager.stop_alarm()

        self.accept()

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, app, clock, countdown, alarm_manager, config_manager):
        # Load custom PNG icon
        icon_path = "logo.png"  # Path to your icon file

        # Check if file exists and use it, otherwise fall back to system icon
        if os.path.exists(icon_path):
            icon = QtGui.QIcon(icon_path)
        else:
            # Fallback to system icon
            icon = app.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DesktopIcon)

        super().__init__(icon, app)  # Pass parent application

        self.app = app
        self.clock = clock
        self.countdown = countdown
        self.alarm_manager = alarm_manager
        self.config_manager = config_manager

        # Create icon (you might want to use a proper icon file)
        self.setIcon(icon)

        # Create menu
        self.menu = QtWidgets.QMenu()

        # Add actions
        self.show_clock_action = self.menu.addAction("Show/Hide Clock")
        self.show_clock_action.triggered.connect(self.toggle_clock)

        self.alarm_action = self.menu.addAction("Enable Alarm")
        self.alarm_action.setCheckable(True)
        self.alarm_action.setChecked(self.alarm_manager.active)
        self.alarm_action.triggered.connect(self.toggle_alarm)

        self.menu.addSeparator()

        self.settings_action = self.menu.addAction("Settings")
        self.settings_action.triggered.connect(self.show_settings)

        self.menu.addSeparator()

        self.quit_action = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_app)

        # Set context menu
        self.setContextMenu(self.menu)

        # Show the tray icon
        self.show()

        # Connect activated signal (when user clicks the tray icon)
        self.activated.connect(self.on_activated)

    def toggle_clock(self):
        if self.clock.isVisible():
            self.clock.hide()
        else:
            self.clock.show()

    def toggle_alarm(self, checked):
        if checked:
            self.alarm_manager.start_alarm()
            self.config_manager.config["alarm"]["enabled"] = True
        else:
            self.alarm_manager.stop_alarm()
            self.config_manager.config["alarm"]["enabled"] = False
        self.config_manager.save_config()

    def show_settings(self):
        settings_window = SettingsWindow(self.clock, self.config_manager, self.alarm_manager,
                                         clock=self.clock, countdown=self.countdown)
        settings_window.exec()
        # Update alarm action state after settings might have changed
        self.alarm_action.setChecked(self.alarm_manager.active)

    def quit_app(self):
        self.app.quit()

    def on_activated(self, reason):
        # If double-clicked or clicked, show/hide the clock
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick or reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.toggle_clock()

def main():
    # For Qt 6 (PySide6), high DPI scaling is enabled by default
    # Set these environment variables before QApplication is created if you need custom scaling
    # os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"  # Already on by default in Qt 6
    # os.environ["QT_SCALE_FACTOR"] = "1"  # Can be used to force a specific scale factor
    # Modern way to handle screen scaling in Qt 6
    # Default is already set to PerMonitorV2 in Qt 6
    if hasattr(QtCore, 'Qt'):
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QtWidgets.QApplication(sys.argv)

    # Important: Set this to keep app running when all windows are closed
    app.setQuitOnLastWindowClosed(False)

    config_manager = ConfigManager()
    sound_generator = SoundGenerator(config_manager)
    alarm_manager = AlarmManager(config_manager, sound_generator)

    clock = ClockOverlay(config_manager, alarm_manager)
    countdown = CountdownOverlay(config_manager, alarm_manager)

    # Set Tool flag to hide from taskbar
    clock.setWindowFlags(clock.windowFlags() | QtCore.Qt.Tool)
    countdown.setWindowFlags(countdown.windowFlags() | QtCore.Qt.Tool)

    # Now set the countdown in the alarm_manager
    alarm_manager.set_countdown(countdown)

    # Start alarm if enabled in config (which will also show countdown if needed)
    if config_manager.config["alarm"]["enabled"]:
        alarm_manager.start_alarm()

    # Create system tray icon
    tray_icon = SystemTrayIcon(app, clock, countdown, alarm_manager, config_manager)

    clock.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()