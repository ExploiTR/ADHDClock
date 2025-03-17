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
    def __init__(self, config_manager, sound_generator):
        self.config_manager = config_manager
        self.sound_generator = sound_generator
        self.active = False
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.alarm_callback)

    def start_alarm(self):
        if self.active:
            return

        self.active = True
        interval = self.config_manager.config["alarm"]["interval"] * 1000  # Convert to milliseconds
        self.timer.start(interval)

    def stop_alarm(self):
        self.active = False
        self.timer.stop()

    def alarm_callback(self):
        # Play sound in a separate thread
        sound_thread = threading.Thread(target=self.sound_generator.play_sound)
        sound_thread.daemon = True
        sound_thread.start()

        # Update interval in case it was changed in settings
        interval = self.config_manager.config["alarm"]["interval"] * 1000
        self.timer.setInterval(interval)


class ClockOverlay(QtWidgets.QMainWindow):
    def __init__(self, config_manager, alarm_manager):
        super().__init__(flags=QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

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
            settings_window = SettingsWindow(self, self.config_manager, self.alarm_manager)
            settings_window.exec()
        elif action == quit_action:
            self.close()


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
    def __init__(self, parent, config_manager, alarm_manager):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = config_manager
        self.alarm_manager = alarm_manager

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

        # Add tabs to widget
        tab_widget.addTab(appearance_tab, "Appearance")
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

            # Update preview when fonts are loaded
            QtCore.QMetaObject.invokeMethod(self, "update_preview",
                                            QtCore.Qt.QueuedConnection)

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

        # Duration
        self.duration_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.duration_slider.setRange(1, 10)
        self.duration_slider.setValue(self.config_manager.config["alarm"]["duration"])

        self.duration_spinbox = QtWidgets.QSpinBox()
        self.duration_spinbox.setRange(1, 10)
        self.duration_spinbox.setValue(self.duration_slider.value())
        self.duration_spinbox.setSuffix(" sec")

        # Connect for two-way synchronization
        self.duration_slider.valueChanged.connect(self.duration_spinbox.setValue)
        self.duration_spinbox.valueChanged.connect(self.duration_slider.setValue)

        duration_layout = QtWidgets.QHBoxLayout()
        duration_layout.addWidget(self.duration_slider)
        duration_layout.addWidget(self.duration_spinbox)
        layout.addRow("Duration:", duration_layout)

        # Interval
        self.interval_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.interval_slider.setRange(5, 3600)
        self.interval_slider.setValue(self.config_manager.config["alarm"]["interval"])

        self.interval_spinbox = QtWidgets.QSpinBox()
        self.interval_spinbox.setRange(5, 3600)
        self.interval_spinbox.setValue(self.interval_slider.value())
        self.interval_spinbox.setSuffix(" sec")

        # Connect for two-way synchronization
        self.interval_slider.valueChanged.connect(self.interval_spinbox.setValue)
        self.interval_spinbox.valueChanged.connect(self.interval_slider.setValue)

        interval_layout = QtWidgets.QHBoxLayout()
        interval_layout.addWidget(self.interval_slider)
        interval_layout.addWidget(self.interval_spinbox)
        layout.addRow("Interval:", interval_layout)

        tab.setLayout(layout)
        return tab

    def create_sound_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()

        # Wave Types
        wave_types_group = QtWidgets.QGroupBox("Wave Types")
        wave_types_layout = QtWidgets.QHBoxLayout()

        self.sine_checkbox = QtWidgets.QCheckBox("Sine")
        self.square_checkbox = QtWidgets.QCheckBox("Square")
        self.sawtooth_checkbox = QtWidgets.QCheckBox("Sawtooth")
        self.triangle_checkbox = QtWidgets.QCheckBox("Triangle")

        current_types = self.config_manager.config["sound"]["type"]
        self.sine_checkbox.setChecked("sine" in current_types)
        self.square_checkbox.setChecked("square" in current_types)
        self.sawtooth_checkbox.setChecked("sawtooth" in current_types)
        self.triangle_checkbox.setChecked("triangle" in current_types)

        wave_types_layout.addWidget(self.sine_checkbox)
        wave_types_layout.addWidget(self.square_checkbox)
        wave_types_layout.addWidget(self.sawtooth_checkbox)
        wave_types_layout.addWidget(self.triangle_checkbox)

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

        # Test Sound Button
        test_sound_button = QtWidgets.QPushButton("Test Sound")
        test_sound_button.clicked.connect(self.test_sound)
        layout.addRow(test_sound_button)

        tab.setLayout(layout)
        return tab

    def choose_color(self):
        current_color = self.config_manager.config["clock"]["color"]
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(current_color), self, "Choose Text Color")
        if color.isValid():
            self.color_button.setStyleSheet(f"background-color: {color.name()}; min-width: 60px; min-height: 30px;")
            self.update_preview()

    def test_sound(self):
        # Create temporary config
        temp_config = self.config_manager.config.copy()

        # Get selected sound types
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
        temp_config["alarm"]["duration"] = 1  # Short duration for testing

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

        # Alarm settings
        old_alarm_enabled = self.config_manager.config["alarm"]["enabled"]
        self.config_manager.config["alarm"]["enabled"] = self.alarm_checkbox.isChecked()
        self.config_manager.config["alarm"]["duration"] = self.duration_spinbox.value()
        self.config_manager.config["alarm"]["interval"] = self.interval_spinbox.value()

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

        # Apply changes to clock
        self.parent.apply_config()
        self.parent.drag_enabled = self.drag_checkbox.isChecked()

        # Handle alarm state
        if self.alarm_checkbox.isChecked() and not old_alarm_enabled:
            self.alarm_manager.start_alarm()
        elif not self.alarm_checkbox.isChecked() and old_alarm_enabled:
            self.alarm_manager.stop_alarm()

        self.accept()


def main():
    # For Qt 6 (PySide6), high DPI scaling is enabled by default
    # Set these environment variables before QApplication is created if you need custom scaling
    # os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"  # Already on by default in Qt 6
    # os.environ["QT_SCALE_FACTOR"] = "1"  # Can be used to force a specific scale factor

    app = QtWidgets.QApplication(sys.argv)

    # Modern way to handle screen scaling in Qt 6
    # Default is already set to PerMonitorV2 in Qt 6
    if hasattr(QtCore, 'Qt'):
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    config_manager = ConfigManager()
    sound_generator = SoundGenerator(config_manager)
    alarm_manager = AlarmManager(config_manager, sound_generator)

    # Start alarm if enabled in config
    if config_manager.config["alarm"]["enabled"]:
        alarm_manager.start_alarm()

    clock = ClockOverlay(config_manager, alarm_manager)
    clock.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()