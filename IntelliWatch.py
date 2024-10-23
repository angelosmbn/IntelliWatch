import IntelliWatchHome
import tkinter as tk
import sqlite3
import socket
from tkinter import messagebox

def is_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

def no_internet_popup():
    window = tk.Tk()
    window.title("No Internet Connection")
    window.iconbitmap("IntelliWatchLogo.ico")
    window.resizable(False, False)
    
    # Set geometry for a smaller window
    window.geometry("300x100")

    label = tk.Label(window, text="Please connect to the internet to use this application.", font=("Helvetica", 8))
    label.pack(padx=10, pady=10)

    button = tk.Button(window, text="OK", command=window.destroy, font=("Helvetica", 10))
    button.pack(pady=5)

    window.mainloop()

def agreementWindow():
    window = tk.Tk()
    window.title("Data Privacy Agreement")
    window.iconbitmap("IntelliWatchLogo.ico")
    window.resizable(False, False)

    # reads the txt file
    with open("agreement.txt", "r") as file:
        file = file.read()

    # opens the window
    title_label = tk.Label(
        window, text="Data Privacy Agreement", font=("Helvetica", 16)
    )
    title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=5)
    text = tk.Label(
        window,
        text=file,
        font=("Helvetica", 11),
        padx=20,
        pady=5,
        wraplength=600,
        anchor="w",
        justify="left",
    )
    text.grid(row=1, column=0, columnspan=2, padx=10, pady=5)

    def accept():
        window.destroy()
        conn = sqlite3.connect("userdata.db")
        cur = conn.cursor()
        cur.execute("UPDATE userdata SET agreed = 1")
        conn.commit()
        conn.close()
        IntelliWatchHome.app()

    def on_closing():
        conn = sqlite3.connect("userdata.db")
        cur = conn.cursor()
        cur.execute("UPDATE userdata SET is_active = 0")
        conn.commit()
        conn.close()
        window.destroy()

    def checkbox_changed():
        if checkbox_var.get() == 1:  # If checkbox is checked
            continue_button.config(state=tk.NORMAL)  # Enable the button
        else:
            continue_button.config(state=tk.DISABLED)  # Disable the button

    checkbox_var = tk.IntVar()
    checkbox = tk.Checkbutton(
        window, text="I agree", variable=checkbox_var, command=checkbox_changed
    )
    checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=5)
    continue_button = tk.Button(
        window,
        text="Continue",
        command=accept,
        font=("Helvetica", 12, "bold"),
        state=tk.DISABLED,
    )
    continue_button.grid(row=3, column=0, columnspan=2, padx=10, pady=5)

    window.protocol("WM_DELETE_WINDOW", on_closing)  # Handle window closing event
    window.mainloop()

if __name__ == "__main__":
    if is_connected():
        conn = sqlite3.connect("userdata.db")
        cur = conn.cursor()
        cur.execute("SELECT agreed FROM userdata WHERE id = 1")
        row = cur.fetchone()  # Fetch the first row
        cur.execute("SELECT is_active FROM userdata WHERE id = 1")
        row2 = cur.fetchone()
        conn.close()
        if row2 is not None:
            active_value = row2[0]
            if active_value == 0 or active_value == None:  # checks  if the window is already active, if not, then it opens home
                conn = sqlite3.connect("userdata.db")
                cur = conn.cursor()
                cur.execute("UPDATE userdata SET is_active = 1 WHERE id = 1")
                conn.commit()
                conn.close()
                if row is not None:
                    agreed_value = row[0]
                    if agreed_value == 1:  # Check if the value is True
                        IntelliWatchHome.app()
                    elif agreed_value == 0:
                        agreementWindow()
        else:
            messagebox.showerror("Error", "No data found in the 'userdata' table.")
    else:
        no_internet_popup()