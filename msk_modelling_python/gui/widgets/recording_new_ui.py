    def _create_ui(self):
        """Create the user interface with horizontal layout (left settings, right camera preview)."""
        # Main container with two columns
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== LEFT PANEL (SETTINGS) ==========
        left_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=False, padx=(0, 10))

        # Title
        title_label = ctk.CTkLabel(
            left_panel,
            text="Video Recording & Analysis",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(padx=10, pady=(0, 10), anchor="w")

        # Scrollable settings area
        settings_scroll = ctk.CTkScrollableFrame(left_panel, width=300, fg_color="transparent")
        settings_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== OUTPUT DIRECTORY =====
        output_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        output_frame.pack(fill="x", pady=5)

        output_title = ctk.CTkLabel(
            output_frame,
            text="💾 Output Directory",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        output_title.pack(padx=15, pady=(10, 5), anchor="w")

        dir_button_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        dir_button_frame.pack(padx=15, pady=5, fill="x")

        self.dir_entry = ctk.CTkEntry(
            dir_button_frame,
            placeholder_text="C:\\Videos\\Recordings",
            font=("Consolas", 9),
            width=200
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.dir_entry.insert(0, str(self.output_dir))

        browse_btn = ctk.CTkButton(
            dir_button_frame,
            text="Browse",
            command=self._choose_directory,
            width=80,
            font=("Segoe UI", 9)
        )
        browse_btn.pack(side="right", padx=0)

        # ===== VIDEO SOURCE =====
        source_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        source_frame.pack(fill="x", pady=5)

        source_title = ctk.CTkLabel(
            source_frame,
            text="📹 Video Source",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        source_title.pack(padx=15, pady=(10, 5), anchor="w")

        self.camera_var = ctk.StringVar(value="webcam")

        webcam_btn = ctk.CTkRadioButton(
            source_frame,
            text="Webcam (USB Camera)",
            variable=self.camera_var,
            value="webcam",
            command=self._on_camera_changed,
            font=("Segoe UI", 10)
        )
        webcam_btn.pack(padx=15, pady=2, anchor="w")

        ip_btn = ctk.CTkRadioButton(
            source_frame,
            text="IP Camera",
            variable=self.camera_var,
            value="ip",
            command=self._on_camera_changed,
            font=("Segoe UI", 10)
        )
        ip_btn.pack(padx=15, pady=2, anchor="w")

        # IP Address input
        self.ip_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
        self.ip_frame.pack(padx=15, pady=5, fill="x")

        ip_label = ctk.CTkLabel(
            self.ip_frame,
            text="IP Address:",
            font=("Segoe UI", 9),
            text_color="#aaaaaa"
        )
        ip_label.pack(side="left", padx=(0, 5))

        self.ip_entry = ctk.CTkEntry(
            self.ip_frame,
            placeholder_text="http://192.168.x.x:8080/video",
            font=("Segoe UI", 9),
            width=180
        )
        self.ip_entry.pack(side="left", fill="x", expand=True, padx=0)
        self.ip_entry.insert(0, self.ip_address)
        self.ip_entry.bind("<FocusOut>", lambda e: self._update_camera_preview())

        self.ip_frame.pack_forget()

        # ===== OPENSIM MODEL =====
        model_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        model_frame.pack(fill="x", pady=5)

        model_title = ctk.CTkLabel(
            model_frame,
            text="🦴 OpenSim Model",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        model_title.pack(padx=15, pady=(10, 5), anchor="w")

        self.model_var = ctk.StringVar(value="arm26_ball")

        models = [
            ("Arm26 Ball (Right Arm + Ball)", "arm26_ball"),
            ("Full Body with Ball", "full_body_with_ball"),
        ]

        for label, value in models:
            radio = ctk.CTkRadioButton(
                model_frame,
                text=label,
                variable=self.model_var,
                value=value,
                font=("Segoe UI", 10)
            )
            radio.pack(padx=15, pady=2, anchor="w")

        # ===== RECORDING DURATION =====
        duration_frame = ctk.CTkFrame(settings_scroll, fg_color="#2d2d2d", corner_radius=8)
        duration_frame.pack(fill="x", pady=5)

        duration_title = ctk.CTkLabel(
            duration_frame,
            text="⏱ Recording Duration",
            font=("Segoe UI", 11, "bold"),
            text_color="#ffffff"
        )
        duration_title.pack(padx=15, pady=(10, 5), anchor="w")

        duration_input_frame = ctk.CTkFrame(duration_frame, fg_color="transparent")
        duration_input_frame.pack(padx=15, pady=5, fill="x", anchor="w")

        duration_label = ctk.CTkLabel(
            duration_input_frame,
            text="Seconds:",
            font=("Segoe UI", 10),
            text_color="#aaaaaa"
        )
        duration_label.pack(side="left", padx=(0, 10))

        self.duration_entry = ctk.CTkEntry(
            duration_input_frame,
            placeholder_text="10",
            font=("Segoe UI", 10),
            width=80
        )
        self.duration_entry.pack(side="left", padx=5)
        self.duration_entry.insert(0, str(self.recording_duration))

        # ===== STATUS =====
        self.status_label = ctk.CTkLabel(
            settings_scroll,
            text="Ready to record",
            font=("Segoe UI", 10),
            text_color="#666666"
        )
        self.status_label.pack(padx=15, pady=(20, 10), anchor="w")

        # ===== ANALYZE BUTTON =====
        analyze_btn = ctk.CTkButton(
            settings_scroll,
            text="📊 Analyze Recording",
            command=self._analyze_recording,
            font=("Segoe UI", 11),
            height=35
        )
        analyze_btn.pack(fill="x", padx=15, pady=5)

        # ========== RIGHT PANEL (CAMERA PREVIEW + RECORD BUTTON) ==========
        right_panel = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Camera preview area
        camera_frame = ctk.CTkFrame(right_panel, fg_color="#1e1e1e", corner_radius=8, border_width=2, border_color="#404040")
        camera_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.camera_preview_label = ctk.CTkLabel(
            camera_frame,
            text="📷 Camera Preview\nWebcam Ready",
            text_color="#888888",
            font=("Segoe UI", 14),
            fg_color="#1e1e1e"
        )
        self.camera_preview_label.pack(fill="both", expand=True, padx=20, pady=20)

        # Recording controls frame
        controls_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        controls_frame.pack(fill="x")

        # Start Recording button (large and prominent)
        record_btn = ctk.CTkButton(
            controls_frame,
            text="🔴 Start Recording",
            command=self._start_recording,
            font=("Segoe UI", 14, "bold"),
            height=50,
            fg_color="#c62828",
            hover_color="#7f0000"
        )
        record_btn.pack(fill="x", pady=5)

        # Initialize camera preview
        self._update_camera_preview()
        self._refresh_output_list()
