import sqlite3
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, Scale
from PIL import Image, ImageTk
import cv2
from ultralytics import YOLO
import os
import time
import pygetwindow as gw
from mss import mss
import numpy as np
import google.generativeai as genai
from email.message import EmailMessage
import smtplib
import ssl
import re
from twilio.rest import Client
import threading

# Move YOLO model initialization into a function
def initialize_yolo_models():
    model = YOLO("yolov8s-pose.pt")
    cnn_model = YOLO("cnn-model.pt")
    return model, cnn_model

class App(tk.Tk):

    def __init__(self):

        # Initialize YOLO models
        self.model, self.cnn_model = initialize_yolo_models()

        def get_emails():
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("SELECT email, email2 FROM userdata WHERE id = 1")
            row = cur.fetchone()
            conn.close()
            if row:
                email, email2 = row  # Assuming the query returns exactly two columns
                return str(email), str(email2)

        self.email, self.email2 = get_emails()
        if self.email == "None":
            self.email = "Please enter an email address"
        super().__init__()
        self.title("INTELLIWATCH")
        self.iconbitmap("IntelliWatchLogo.ico")


        # Set initial size of the window
        self.geometry("1920x1080")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_columnconfigure(4, weight=1)
        self.streaming = False
        self.camera_capturing = False
        self.email_receiver = None

        self.refresh_sources = tk.Button(
            self,
            text="Refresh",
            bg="#4CAF50",
            fg="white",
            command=self.refresh_all_sources,
        )
        self.refresh_sources.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Email label and entry
        self.edit_email_button = tk.Button(
            self, text="Email", command=self.email_window, bg="#4CAF50", fg="white"
        )
        self.edit_email_button.grid(row=1, column=0, padx=10, pady=1, sticky="w")

        self.email_entry = tk.Label(self, text=self.email)
        self.email_entry.grid(
            row=1, column=1, columnspan=2, padx=10, pady=1, sticky="we"
        )

        # Number label and entry
        self.number_label = tk.Label(self, text="Number")
        self.number_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.number_entry = tk.Entry(self)
        self.number_entry.grid(
            row=2, column=1, columnspan=2, padx=10, pady=5, sticky="we"
        )

        # Choose source label and dropdown
        self.source_label = tk.Label(self, text="Choose Source")
        self.source_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.source_dropdown = ttk.Combobox(self)
        self.source_dropdown.grid(
            row=3, column=1, columnspan=2, padx=10, pady=5, sticky="we"
        )
        self.update_sources()

        # Use camera button
        self.use_camera_button = tk.Button(
            self,
            text="Use Camera",
            bg="#4CAF50",
            fg="white",
            command=self.toggle_camera,
        )
        self.use_camera_button.grid(row=4, column=0, padx=10, pady=5, sticky="we")

        # Use source button
        self.use_source_button = tk.Button(
            self,
            text="Use Source",
            bg="#4CAF50",
            fg="white",
            command=self.start_source_capture,
        )
        self.use_source_button.grid(row=4, column=2, padx=10, pady=5, sticky="we")

        # choose camera source
        self.camera_source_dropdown = ttk.Combobox(self)
        self.camera_source_dropdown.grid(row=4, column=1, padx=10, pady=5, sticky="we")
        self.update_camera_sources()

        # OUTPUT FRAME
        self.output_frame = tk.Frame(self, bg="white")
        self.output_frame.grid(
            row=5, column=0, columnspan=3, padx=10, pady=5, sticky="ew"
        )

        # Camera and output frames
        self.camera_frame = tk.Canvas(self, bg="white")
        self.camera_frame.grid(
            row=0, column=3, rowspan=6, columnspan=1, padx=10, pady=5, sticky="e"
        )

        # Create the Scrollbar
        self.scrollbar = tk.Scrollbar(self.output_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.output_text = tk.Text(
            self.output_frame, width=50, height=20, font=("Helvetica", 10)
        )
        self.output_text.pack(expand=True, fill="both", padx=5, pady=5)

        # Configure the Scrollbar
        self.scrollbar.config(command=self.output_text.yview)

        # Make frames resize with the window
        self.grid_rowconfigure(5, weight=1)
        # self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)

        # Set initial size of the camera frame
        self.update_idletasks()
        self.initial_width_cam = int(self.winfo_width() * 0.7)
        self.initial_height_cam = int(self.winfo_height() * 0.85)
        self.camera_frame.config(
            width=self.initial_width_cam, height=self.initial_height_cam
        )

        # Bind configure event to dynamically resize the camera frame
        self.bind("<Configure>", self.on_resize)

        # Initialize
        self.cap = None
        self.selected_window = None
        self.savePath = None

        def on_closing():
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("UPDATE userdata SET is_active = 0")
            conn.commit()
            conn.close()
            self.destroy()

        self.protocol("WM_DELETE_WINDOW", on_closing)

    def on_resize(self, event):
        new_width_cam = int(self.winfo_width() * 0.8)
        new_height_cam = int(self.winfo_height() * 1)
        new_width_output = int(self.winfo_width() * 0.2)
        new_height_output = int(self.winfo_height() * 1)
        self.output_frame.config(width=new_width_output, height=new_height_output)
        self.camera_frame.config(width=new_width_cam, height=new_height_cam)
        self.initial_width_cam = new_width_cam
        self.initial_height_cam = new_height_cam

    def refresh_all_sources(self):
        self.update_sources()
        self.update_camera_sources()

    def apiCall(self, keypoints_history):
        # Create an instance of the API
        genai.configure(api_key="AIzaSyD6hMP0Ywp0BU_FH_a5mosHzEDeHCR7Moc")

        generation_config = {
            "temperature": 0.9,
            "top_p": 1,
            "top_k": 0,
            "max_output_tokens": 2048,
            "response_mime_type": "text/plain",
        }
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]

        apiModel = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            safety_settings=safety_settings,
            generation_config=generation_config,
        )

        chat_session = apiModel.start_chat()

        prePrompt = """
Tha values are not normalize, the values are in pixels position, the 0,0 is the top left corner of a frame indicating that high value of y is at the lower point and high value of x is at the right side.

Imagine a human skeleton with the following keypoints:

0: Nose
1: Left Eye
2: Right Eye
3: Left Ear
4: Right Ear
5: Left Shoulder
6: Right Shoulder
7: Left Elbow
8: Right Elbow
9: Left Wrist
10: Right Wrist
11: Left Hip
12: Right Hip
13: Left Knee
14: Right Knee
15: Left Ankle
16: Right Ankle
As a doctor, I will analyze the person's fall based on the keypoints provided. I will carefully examine the positions of these keypoints to identify possible injuries sustained during the fall. This analysis will include the following components:

Possible Injuries: A list of potential injuries the person may have sustained based on the positions of their keypoints and the mechanics of the fall.
Conclusion: A summary of the overall condition of the person, including the most likely injuries and any patterns observed in the keypoints.
Warning: A cautionary note emphasizing that this analysis is not definitive and that the person must consult a medical professional immediately for an accurate diagnosis and treatment.
Note: This analysis is based on the provided keypoints and should be interpreted with caution. An in-person examination by a qualified medical professional is essential for an accurate diagnosis and appropriate treatment.

Example Analysis (however do not mention the keypoint number in the analysis):

Based on the positions of the keypoints provided, here is the analysis of the person's fall:

Possible Injuries:
Head and Face:

If the nose is significantly lower than the rest of the body, it suggests a face-first impact. Possible injuries include nasal fractures, facial lacerations, and concussions.
If the eyes and ears are at an unusual angle, it could indicate head rotation or tilting, leading to potential neck injuries or dislocation.
Upper Body:

If the left shoulder or right shoulder is lower or appears dislocated, there could be a shoulder dislocation or clavicle fracture.
If the elbows are bent at abnormal angles, possible elbow dislocations or fractures may have occurred.
If the wrists show signs of abnormal positioning, wrist fractures or sprains are likely.
Torso and Hips:

If the hips are misaligned or significantly lower than the shoulders, there may be hip dislocations, pelvic fractures, or lower back injuries.
Lower Body:

If the knees are at abnormal angles, knee dislocations or ligament tears could be present.
If the ankles show signs of unusual positioning, ankle sprains or fractures are possible.
Conclusion:
Based on the analysis of the keypoints, the person appears to have experienced a significant impact to their head and upper body, with potential injuries including nasal fractures, concussions, shoulder dislocations, and wrist fractures. The lower body may also have sustained injuries, such as knee dislocations and ankle sprains. The precise nature and extent of these injuries cannot be determined without a thorough physical examination and imaging studies.


The warning should be in a separate paragraph.
Warning:
This analysis is based on the provided keypoints and should be interpreted with caution. It is not a substitute for professional medical advice, diagnosis, or treatment. The person must consult a doctor immediately for a comprehensive evaluation and appropriate medical care. Delaying medical attention can result in serious complications.


Refrain from using tears, lacerations, fractures, and dislocations.
Make sure to consider that the values of the keypoints comes from a 1080p video with a cctv like angle.(do not mention this in the result)
Make sure to analyze as best as you can.


MAKE SURE TO LIMIT THE RESULT TO 300 WORDS OR BELOW
        """

        response = chat_session.send_message(keypoints_history + prePrompt)
        self.analysis = response.text.replace('*', '')
        #return response.text

    def toggle_camera(self):
        receiver_email = self.email
        receiver_number = self.number_entry.get()
        if not receiver_number:
            messagebox.showerror("Error", "Please enter the receiver's number.")
            return
        if not re.match(r'^\+63\d{10}$', receiver_number):
            messagebox.showerror("Error", "Please enter a valid Philippine phone number. (e.g. +639123456789)")
            return
        if receiver_email == "None" or receiver_email == "Please enter an email address":
            messagebox.showerror("Error", "Please enter the receiver's primary email address.")
            return

        if not self.camera_capturing:
            self.use_camera_button.config(text="Stop Camera", bg="#FF5733")
            self.camera_capturing = True
            self.use_source_button.config(state=tk.DISABLED)
            self.edit_email_button.config(state=tk.DISABLED)
            self.refresh_sources.config(state=tk.DISABLED)
            self.number_entry.config(state="readonly")
            self.source_dropdown.config(state="disabled")
            self.camera_source_dropdown.config(state="disabled")
            self.start_camera()

        else:
            self.stop_camera()

    def get_available_cameras(self):
        num_cameras = 0
        camera_list = []
        for i in range(10):  # Limiting to 10 cameras
            cap = cv2.VideoCapture(i)
            try:
                if not cap.read()[0]:
                    break
                num_cameras += 1
                camera_list.append(f"Camera Source {i}")
            except:
                break
            finally:
                cap.release()
        return camera_list

    def start_camera(self):
        if self.cap is None:
            selected_camera = self.camera_source_dropdown.get()
            if selected_camera:
                camera_index = int(selected_camera.split()[-1])
                self.cap = cv2.VideoCapture(camera_index)
        self.show_camera_frame()

    def update_camera_sources(self):
        available_cameras = self.get_available_cameras()
        if not available_cameras:
            messagebox.showerror("Error", "No cameras found")
        self.camera_source_dropdown["values"] = available_cameras
        if available_cameras:
            self.camera_source_dropdown.current(0)

    def stop_camera(self):
        self.use_camera_button.config(text="Use Camera", bg="#4CAF50")
        self.camera_capturing = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.camera_capturing = False
        self.camera_frame.delete("all")  # Clear the camera frame
        self.use_source_button.config(state=tk.NORMAL)
        self.edit_email_button.config(state=tk.NORMAL)
        self.refresh_sources.config(state=tk.NORMAL)
        self.number_entry.config(state="normal")
        self.source_dropdown.config(state="normal")
        self.camera_source_dropdown.config(state="normal")

    def show_camera_frame(self):
        if self.cap is not None and self.camera_capturing:
            ret, frame = self.cap.read()

            if ret:
                self.detect_fall(frame)
                # Resize the frame to match the size of the canvas
                frame = cv2.resize(
                    frame, (self.initial_width_cam, self.initial_height_cam)
                )

                # Convert frame from BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Create a Tkinter-compatible photo image
                img = Image.fromarray(frame)
                img = ImageTk.PhotoImage(image=img)

                # Display the image on the canvas
                self.camera_frame.create_image(0, 0, anchor=tk.NW, image=img)
                self.camera_frame.img = (
                    img  # Save reference to avoid garbage collection
                )
            else:
                messagebox.showerror("Error", "Failed to capture frame.")
                self.stop_camera()
        if self.camera_capturing:
            self.after(3, self.start_camera)  # Update every 10 milliseconds

    keypoints_history = []

    prev_upper_body = None
    prev_lower_body = None

    velocity_threshold = 0.135
    velocity_threshold_lower = 0.1

    fall_counter = 0
    start_time = None  # Initialize start_time to None

    fall_detected = False
    fall_countdown = None

    counter = 0
    counter_multiple = 0

    # Function to store latest keypoints
    def store_keypoints(self, keypoints):

        # Append the new keypoints to the history
        self.keypoints_history.append(keypoints)

        # Keep only the latest 30 entries
        if len(self.keypoints_history) > 30:
            self.keypoints_history = self.keypoints_history[-30:]

    def predict_action(self, image_path):
        cnn_results = self.cnn_model(
            source=image_path, show=False, conf=0.87, stream=True, verbose=False
        )

        for cnn_result in cnn_results:
            bounding_boxes = cnn_result.boxes.cpu().numpy()

            class_name = bounding_boxes.cls

            if class_name == 0:
                return "Sitting"
            elif class_name == 1:
                return "Standing"
            else:
                return "Unknown class"

    # Function to generate a unique filename
    def generate_filename(self, folder, prefix="fall_detected_", ext=".jpg"):
        existing_files = os.listdir(folder)
        existing_numbers = [
            int(f[len(prefix) : -len(ext)])
            for f in existing_files
            if f.startswith(prefix) and f.endswith(ext)
        ]
        if existing_numbers:
            new_number = max(existing_numbers) + 1
        else:
            new_number = 0
        return os.path.join(folder, f"{prefix}{new_number}{ext}")

    # Create results folder if it doesn't exist
    if not os.path.exists("results"):
        os.makedirs("results")

    timestamp = ''
    def process_fall(self, frame):
        receiver_num = self.number_entry.get()

        # Generate a unique filename
        filename = self.generate_filename("results")
        cv2.imwrite(filename, frame)

        # Predict action
        action = self.predict_action(filename)
        
        if action == "Unknown class":
            # Define red color tag
            self.output_text.tag_configure("red", foreground="red")
            #self.timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ")
            self.timestamp = time.strftime("%B %d, %Y at %I:%M %p")
            # Insert text with timestamp and red color
            self.output_text.insert(
                tk.END, "!!!FALL IS DETECTED!!!" + "\n" + self.timestamp + "\n", "red"
            )
            self.output_text.see(tk.END)
            thread_sms = threading.Thread(target=self.send_sms, args=(receiver_num,))
            thread_sms.start()
            
            self.analysis_thread.join()
            
            thread1 = threading.Thread(target=self.send_email, args=(self.analysis, filename))
            thread1.start()
            if self.email2 != "":
                thread2 = threading.Thread(target=self.send_email2, args=(self.analysis, filename))
                thread2.start()
            #print(str(self.keypoints_history))
            self.output_text.see(tk.END)
            

        self.fall_counter = 0
        self.fall_detected = False
        self.processing = True
        self.processing2 = True
        self.prev_upper_body = None
        self.prev_lower_body = None

    analysis = ""
    processing = True
    processing2 = True
    def detect_fall(self, frame):
        results = self.model(
            source=frame, show=False, conf=0.45, stream=True, verbose=False
        )

        if self.fall_detected:
            if self.processing2:
                keypointsHistory = str(self.keypoints_history)
                print(keypointsHistory)
                self.analysis = self.analysis_thread = threading.Thread(target=self.apiCall, args=(keypointsHistory,))
                self.analysis_thread.start()
                self.processing2 = False

            if time.time() - self.fall_countdown >= 2 and self.processing:
                thread = threading.Thread(target=self.process_fall, args=(frame,))
                thread.start()
                self.processing = False

        else:
                
            for result in results:
                keypoints = result.keypoints.cpu().numpy()
                xyn = keypoints.xyn

                # store the latest 30 keypoints
                self.store_keypoints(xyn)

                # Check if any keypoints are detected
                if xyn.size == 0:
                    self.counter += 1
                    if self.counter == 3:
                        self.prev_upper_body = None
                        self.prev_lower_body = None
                        self.counter = 0
                    continue

                if len(xyn) != 1:
                    self.counter_multiple += 1
                    if self.counter_multiple == 2:
                        self.prev_upper_body = None
                        self.prev_lower_body = None
                        self.counter = 0
                    continue
                
                self.counter = 0
                self.counter_multiple = 0

                # Reset fall_counter after 5 seconds if it's not zero
                if (
                    self.fall_counter != 0
                    and time.time() - self.start_time >= 5
                ):
                    self.fall_counter = 0
                    self.start_time = time.time()  # Reset timer
                    self.prev_upper_body = None
                    self.prev_lower_body = None

                for group in xyn:
                    if len(group) < 15:  # Ensure there are enough keypoints in the group
                        continue

                    left_shoulder = group[5][1]  # Accessing the y-coordinate of index 5
                    right_shoulder = group[6][1]

                    left_knee = group[13][1]
                    right_knee = group[14][1]

                    left_hip = group[11][1]
                    right_hip = group[12][1]

                    upper_body = left_shoulder + right_shoulder + left_hip + right_hip
                    lower_body = left_knee + right_knee + left_hip + right_hip

                    if (
                        left_shoulder != 0
                        and right_shoulder != 0
                        and left_knee != 0
                        and right_knee != 0
                    ):
                        if (
                            self.prev_upper_body is not None
                            and self.prev_lower_body is not None
                        ):
                            self.upper_body_velocity = abs(
                                upper_body - self.prev_upper_body
                            )
                            self.lower_body_velocity = abs(
                                lower_body - self.prev_lower_body
                            )

                            ubk_lbk = abs(upper_body - lower_body)

                            if (
                                self.upper_body_velocity > self.velocity_threshold
                                and self.lower_body_velocity > self.velocity_threshold_lower
                            ):
                                if self.fall_counter == 0:
                                    self.start_time = (
                                        time.time()
                                    )  # Initialize timer at the beginning

                                self.fall_counter += 1
                                if self.fall_counter >= 2:
                                    if ubk_lbk < 0.35 and self.fall_detected == False:
                                        self.fall_detected = True
                                        self.fall_countdown = (
                                            time.time()
                                        )  # Start countdown timer

                    self.prev_upper_body = upper_body
                    self.prev_lower_body = lower_body

    def update_sources(self):
        windows = gw.getWindowsWithTitle("")
        # Filter out blank titles
        window_titles = [win.title for win in windows if win.title.strip()]
        self.source_dropdown["values"] = window_titles

    def show_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.camera_frame.create_image(0, 0, anchor="nw", image=imgtk)
            self.camera_frame.imgtk = imgtk
        self.camera_frame.after(10, self.show_frame)

    def start_source_capture(self):
        receiver_email = self.email
        receiver_number = self.number_entry.get()
        if not receiver_number:
            messagebox.showerror("Error", "Please enter the receiver's number.")
            return
        if not re.match(r'^\+63\d{10}$', receiver_number):
            messagebox.showerror("Error", "Please enter a valid Philippine phone number. (e.g. +639123456789)")
            return
        if receiver_email == "None" or receiver_email == "Please enter an email address":
            messagebox.showerror("Error", "Please enter the receiver's primary email address.")
            return

        if self.streaming:
            self.streaming = False
            self.use_source_button.config(text="Use Source", bg="#4CAF50")
            self.use_camera_button.config(state=tk.NORMAL)
            self.edit_email_button.config(state=tk.NORMAL)
            self.refresh_sources.config(state=tk.NORMAL)
            self.number_entry.config(state="normal")
            self.source_dropdown.config(state="normal")
            self.camera_source_dropdown.config(state="normal")

        else:
            selected_source = self.source_dropdown.get()
            windows = gw.getWindowsWithTitle(selected_source)
            if windows and selected_source != "":
                self.streaming = True
                self.use_source_button.config(text="Stop Source", bg="#FF5733")

                self.selected_window = windows[0]

                self.use_camera_button.config(state=tk.DISABLED)
                self.edit_email_button.config(state=tk.DISABLED)
                self.refresh_sources.config(state=tk.DISABLED)
                self.number_entry.config(state="readonly")
                self.source_dropdown.config(state="disabled")
                self.camera_source_dropdown.config(state="disabled")
                self.capture_source_frame()
            else:
                messagebox.showerror("Error", "Please select a valid source.")

    def capture_source_frame(self):
        if self.selected_window:
            try:
                with mss() as sct:
                    monitor = {
                        "top": self.selected_window.top,
                        "left": self.selected_window.left,
                        "width": self.selected_window.width,
                        "height": self.selected_window.height,
                    }
                    sct_img = sct.grab(monitor)

                    # Convert the screen capture to a NumPy array
                    img_np = np.array(sct_img)
                    img_cv2 = cv2.cvtColor(
                        img_np, cv2.COLOR_BGRA2BGR
                    )  # Convert from BGRA to BGR for OpenCV

                    # Store the current frame
                    self.current_frame = img_cv2
                    self.detect_fall(img_cv2)

                    # Convert for Tkinter display
                    img_tk = cv2.cvtColor(
                        img_cv2, cv2.COLOR_BGR2RGB
                    )  # Convert from BGR to RGB for PIL
                    img_pil = Image.fromarray(img_tk)
                    imgtk = ImageTk.PhotoImage(image=img_pil)

                    self.camera_frame.create_image(0, 0, anchor="nw", image=imgtk)
                    self.camera_frame.imgtk = imgtk

            except Exception as e:
                # Display an error message
                messagebox.showerror("Error", f"An error occurred: {e}")
                self.streaming = False  # Stop streaming if there is an error
                self.use_source_button.config(text="Use Source", bg="#4CAF50")
                self.camera_frame.delete("all")
                self.use_camera_button.config(state=tk.NORMAL)
                self.edit_email_button.config(state=tk.NORMAL)
                self.refresh_sources.config(state=tk.NORMAL)
                self.number_entry.config(state="normal")
                self.source_dropdown.config(state="normal")
                self.camera_source_dropdown.config(state="normal")
        if self.streaming is True:
            self.camera_frame.after(10, self.capture_source_frame)
        else:
            self.camera_frame.delete("all")

    def send_email(self, analysis, filename):
        # Send an email notification with attached images
        email_sender = ""
        email_password = ""
        email_receiver = self.email

        subject = "URGENT: A FALL HAS BEEN DETECTED!"
        body = f"{self.timestamp}\nPLEASE CHECK YOUR CAMERA, OUR SYSTEM HAS DETECTED A FALL.\n\n"

        em = EmailMessage()
        em["From"] = f"IntelliWatch <{email_sender}>"
        em["To"] = email_receiver
        em["Subject"] = subject
        em.set_content(body + analysis)

        try:
            # Attach detected images to the email
            with open(filename, "rb") as img_file:
                img_data = img_file.read()
                em.add_attachment(
                    img_data,
                    maintype="image",
                    subtype=os.path.splitext(filename)[1][1:],
                    filename=filename,
                )
                self.output_text.insert(tk.END, "PRIMARY EMAIL SENT" + "\n")


        except PermissionError:
            messagebox.showerror("Error", "Permission denied: Unable to access file.")
            self.output_text.insert(tk.END, "FAILED TO SEND PRIMARY EMAIL" + "\n", "red")
            return

        context = ssl.create_default_context()

        # Send the email using SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(email_sender, email_password)
            smtp.sendmail(email_sender, email_receiver, em.as_string())

    def send_email2(self, analysis, filename):
        # Send an email notification with attached images
        email_sender = ""
        email_password = ""
        email_receiver = self.email2

        subject = "URGENT: A FALL HAS BEEN DETECTED!"
        body = f"{self.timestamp}\nPLEASE CHECK YOUR CAMERA, OUR SYSTEM HAS DETECTED A FALL.\n\n"

        em = EmailMessage()
        em["From"] = f"IntelliWatch <{email_sender}>"
        em["To"] = email_receiver
        em["Subject"] = subject
        em.set_content(body + analysis)

        try:
            # Attach detected images to the email
            with open(filename, "rb") as img_file:
                img_data = img_file.read()
                em.add_attachment(
                    img_data,
                    maintype="image",
                    subtype=os.path.splitext(filename)[1][1:],
                    filename=filename,
                )
                self.output_text.insert(tk.END, "SECONDARY EMAIL SENT" + "\n")

        except PermissionError:
            messagebox.showerror("Error", "Permission denied: Unable to access file.")
            self.output_text.insert(tk.END, "FAILED TO SEND SECONDARY EMAIL" + "\n", "red")
            return

        context = ssl.create_default_context()

        # Send the email using SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(email_sender, email_password)
            smtp.sendmail(email_sender, email_receiver, em.as_string())

    def send_sms(self, receiver_num):
        # Twilio authentication credentials
        account_sid = ""
        auth_token = ""

        # Create Twilio client
        client = Client(account_sid, auth_token)

        # Send SMS message
        try:
            message = client.messages.create(
                from_="+12072630281",
                body=f"{self.timestamp}\nALERT!: A fall has been detected!,\nPlease check your email for further details.",  # You can customize the body message here
                to=receiver_num,
            )
            self.output_text.insert(tk.END, "SMS SENT" + "\n")
        except Exception as e:
            self.output_text.insert(tk.END, "FAILED TO SEND SMS" + "\n", "red")

        self.output_text.see(tk.END)

    def email_window(self):

        def go_back():
            change_email.destroy()

        change_email = tk.Toplevel(self)
        change_email.title("Edit Email")
        change_email.resizable(False, False)

        # Calculate the position to center the window on the screen
        # get emails

        change_email.update_idletasks()  # Update "requested size" from geometry manager
        width = 450
        height = 175
        x = (change_email.winfo_screenwidth() // 2) - (width // 2)
        y = (change_email.winfo_screenheight() // 2) - (height // 2)
        change_email.geometry(f"{width}x{height}+{x}+{y}")

        def get_emails():
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("SELECT email, email2 FROM userdata WHERE id = 1")
            row = cur.fetchone()
            conn.close()

            if row:
                email, email2 = row  # Assuming the query returns exactly two columns
                return str(email), str(email2)

        self.email, self.email2 = get_emails()
        
        # Create and place the email entry
        self.email_label = tk.Label(change_email, text="Primary Email (Required):")
        self.email_label.grid(row=0, column=0, padx=10, pady=10)
        self.edit_email_entry = tk.Entry(change_email, width=30)
        self.edit_email_entry.grid(row=0, column=1, padx=10, pady=10)
        self.edit_email_entry.insert(0, self.email)

        # Create and place the update button
        update_button = tk.Button(
            change_email, text="Update", command=self.update_email
        )
        update_button.grid(row=0, column=2, padx=10, pady=10)

        self.email_label2 = tk.Label(change_email, text="Secondary Email:")
        self.email_label2.grid(row=1, column=0, padx=10, pady=10)
        self.edit_email_entry2 = tk.Entry(change_email, width=30)
        self.edit_email_entry2.grid(row=1, column=1, padx=10, pady=10)
        self.edit_email_entry2.insert(0, self.email2)
        # Create and place the update button
        update_button = tk.Button(
            change_email, text="Update", command=self.update_email2
        )
        update_button.grid(row=1, column=2, padx=10, pady=10)

        # Create and place the success label
        self.success_label = tk.Label(change_email, text="")
        self.success_label.grid(row=2, columnspan=3, pady=10)

        # Create and place the back button
        back_button = tk.Button(change_email, text="Back", command=go_back)
        back_button.grid(row=3, columnspan=3, pady=10)

    def update_email_label(self, new_email):
        self.email_entry.config(text=new_email)

    def update_email(self):
        self.email = self.edit_email_entry.get()
        if not self.email:
            self.success_label.config(
                text="Input Error, Please enter an email address", fg="red"
            )
            return
        if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email):
            self.success_label.config(
                text="Invalid Email Address, Please enter a valid email address", fg="red"
            )
            return
        if self.email:
            self.success_label.config(text="Primary Email Updated", fg="green")
            self.update_email_label(self.email)
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("UPDATE userdata SET email = ? WHERE id = 1", (self.email,))
            conn.commit()
            conn.close()
            return

    def update_email2(self):
        self.email2 = self.edit_email_entry2.get()

        if self.email2:  # You can add more validation for email if needed
            if not re.match(r"[^@]+@[^@]+\.[^@]+", self.email2):
                self.success_label.config(
                    text="Invalid Email Address, Please enter a valid email address", fg="red"
                )
                return
            self.success_label.config(text="Secondary Email Updated", fg="green")
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("UPDATE userdata SET email2 = ? WHERE id = 1", (self.email2,))
            conn.commit()
            conn.close()
            return
        elif not self.email2:
            self.success_label.config(text="Secondary Email Removed", fg="red")
            conn = sqlite3.connect("userdata.db")
            cur = conn.cursor()
            cur.execute("UPDATE userdata SET email2 = ? WHERE id = 1", (self.email2,))
            conn.commit()
            conn.close()
            return


# Function to handle back button click
def app():
    app = App()
    app.mainloop()
