# ADHDClock
![Logo](readme_logo.png)

A customizable desktop clock with interval alerts designed specifically for those with ADHD or anyone who benefits from time awareness and regular reminders.
(I personally use this)
##### 🤖 IMPORTANT: _Parts of this code were generated with AI assistance. While efforts have been made to ensure quality, please report any issues or unexpected behavior on the GitHub repository. Consider it a vibe coded project that just works!_

![ADHDClock Screenshot](https://raw.githubusercontent.com/ExploiTR/ADHDClock/refs/heads/master/screenshot.png)

## Features

- **Always-visible transparent clock** that stays on top of other windows
- **Countdown display** showing time until next alert
- **Configurable interval alerts** to help maintain time awareness
- **Customizable appearance** including size, font, color, and opacity
- **Various alert sounds** with adjustable frequencies and waveform types
- **System tray integration** for easy access and control
- **Drag-to-move functionality** for easy repositioning
- **Right-click settings menu** for quick adjustments
- **Automatic dependency management** for easy setup

## Why ADHDClock?

For individuals with ADHD, time blindness (difficulty perceiving the passage of time) can be a significant challenge. ADHDClock helps by:

- Providing a constant visual reminder of the current time
- Showing a countdown to the next alert for better time awareness
- Delivering auditory alerts at regular intervals to help maintain focus and task awareness
- Offering customization options to suit individual preferences and sensory needs
- Being unobtrusive while remaining effective

## Installation

### Prerequisites

- Python 3.7+
- Windows (tested), not sure about Mac & Linux.

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ADHDClock.git
   cd ADHDClock
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv .venv
   ```

3. Run the application:
   - Windows: Double-click `run_clock.bat` or run `python main.py`
   - macOS/Linux: Run `python main.py`

The application will automatically check for and install required dependencies (numpy, simpleaudio-patched, and PySide6) on first run.

## Usage

1. **Launch the application** using the run_clock.bat script (Windows) or `python main.py` command
2. **Move the clock or countdown** by clicking and dragging anywhere on the display
3. **Access settings** by right-clicking on the clock or the system tray icon
4. **Configure alarms and appearance** through the settings dialog

### Settings

The settings dialog contains four tabs:

#### Main Clock
- Width and height
- Font type and size with real-time preview
- Opacity level
- Text color
- Live preview of settings

#### Countdown
- Width and height
- Font type and size
- Opacity level
- Text color
- Live preview of settings

#### Alarm
- Enable/disable alarm
- Sound duration
- Alarm interval in hours, minutes, and seconds
- Test button to hear current alarm sound

#### Sound
- Wave type selection (sine, square, sawtooth, triangle)
- Minimum and maximum frequencies
- Test buttons for each wave type
- Failsafe beep test option

## System Tray Integration

The application provides a system tray icon with the following options:
- Show/Hide Clock
- Enable/Disable Alarm
- Settings
- Quit

## Configuration

All settings are stored in a `config.json` file that's automatically created on first run. You can manually edit this file or use the settings interface.

## Building from Source

The application is written in Python and doesn't require compilation. Simply follow the installation instructions above.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.