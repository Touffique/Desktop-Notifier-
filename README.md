<<<<<<< HEAD
# Desktop Notifier 

A local Windows desktop reminder app built with Python, PySide6, and SQLite.

## Features
- Create reminders with title, optional notes, due date/time, and priority
- Persistent local SQLite database (`focusbell.db`)
- Background due-time checker (checks every 5 seconds)
- System-tray notification when a reminder is due
- Mark reminders complete or delete them
- Minimize/close window to tray; use the tray menu to reopen or quit
- Dark dashboard

## Requirements
- Windows 10/11
- Python 3.10+ (a current supported Python version is recommended)
- Internet access for installing PySide6

## Run on Windows
1. Extract the ZIP to a folder, e.g. `%USERPROFILE%\FocusBell`.
2. Open Command Prompt in that folder.
3. Run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   python main.py
   ```

If `py` is not recognized but `python` works, replace `py` with `python` for the venv command.

## Quick test
1. Add a reminder with a due time about one minute from now.
2. Click “Minimize to tray” (or close the window).
3. Wait for the due time. A FocusBell tray notification should appear.
4. Click the FocusBell tray icon to reopen the app. Right-click it to quit.

## Important behavior / MVP limitations
- Reminders are stored locally in `focusbell.db` in the project folder.
- Closing the window hides the app; it does not quit it. Quit through the tray menu.
- Notifications use Qt's system-tray notification mechanism. Windows settings, Focus Assist/Do Not Disturb, and notification permissions may affect how they appear.
- The app must be running for reminders to fire. It does not yet start automatically with Windows.
- This MVP does not sync to the cloud or send notifications while the computer is off.
=======
# Desktop-Notifier-
Mini Project 
>>>>>>> f99653fd3252b4a68812c3b777aa2e59ce322274
