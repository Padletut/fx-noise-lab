#!/usr/bin/env python3
"""FX Noise Lab - Main Window."""

from __future__ import annotations

from tkinter import BooleanVar, Canvas, StringVar, TclError, filedialog

import customtkinter as ctk

from x_noise_lab.controller import SonificationController

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    """Main application window."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, controller: SonificationController):
        super().__init__()

        self.controller = controller
        self._status_vars = {}
        self.status_label = None
        self.status_widgets = {}
        self.chart_canvas = None
        self.chart_info_label = None
        self.chart_data = None
        self._chart_bounds = (0, 0, 0, 0)
        self.pair_controls = {"A": {}, "B": {}}
        self.playback_widgets = {}
        self._is_closing = False
        self._status_poll_after_id = None
        self._live_audio_refresh_after_id = None

        self.loop_var = BooleanVar(value=self.controller.loop_enabled)
        self.trust_volume_var = BooleanVar(
            value=self.controller.get_settings()["trust_volume_enabled"]
        )
        self.spread_mute_var = BooleanVar(
            value=self.controller.get_settings()["spread_muted"]
        )
        self.regime_mute_var = BooleanVar(
            value=self.controller.get_settings()["regime_muted"]
        )
        self.right_channel_var = BooleanVar(value=self.controller.right_channel_enabled)
        self.api_key_var = StringVar(value=self.controller.api_key)
        self.api_key_var.trace_add("write", self._on_api_key_change)

        self.title("FX Noise Lab 🎧📈")
        self.geometry("1180x820")

        self._create_menu()
        self._create_status_bar()
        self._create_controls()
        self._sync_controls_from_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_runtime_status()

    def _create_menu(self):
        """Create the top action bar."""
        menubar = ctk.CTkFrame(self, fg_color="transparent")
        menubar.pack(fill="x", padx=5, pady=5)

        file_menu = ctk.CTkFrame(menubar, width=200, height=30, corner_radius=0)
        file_menu.pack(side="left", padx=2)
        ctk.CTkLabel(file_menu, text="File", font=ctk.CTkFont(size=12)).pack(
            pady=(5, 0), padx=5
        )
        ctk.CTkButton(
            file_menu,
            text="Open CSV",
            width=130,
            command=self._on_open_file,
        ).pack(padx=5, pady=5)

        playback_menu = ctk.CTkFrame(menubar, width=280, height=30, corner_radius=0)
        playback_menu.pack(side="left", padx=2)
        ctk.CTkLabel(
            playback_menu, text="Playback", font=ctk.CTkFont(size=12)
        ).pack(pady=(5, 0), padx=5)
        ctk.CTkLabel(
            playback_menu,
            text="Step mode is tick-like. Continuous mode interpolates between rows.",
            font=ctk.CTkFont(size=11),
        ).pack(padx=10, pady=5)

        help_menu = ctk.CTkFrame(menubar, width=260, height=30, corner_radius=0)
        help_menu.pack(side="right", padx=2)
        ctk.CTkLabel(help_menu, text="Help", font=ctk.CTkFont(size=12)).pack(
            pady=(5, 0), padx=5
        )
        ctk.CTkLabel(
            help_menu,
            text="Quality sets pitch, trust scales loudness, spread colors distortion.",
            font=ctk.CTkFont(size=11),
        ).pack(padx=10, pady=5)

    def _create_status_bar(self):
        """Create the bottom status bar."""
        status_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", height=30, corner_radius=0)
        status_frame.pack(fill="x", padx=5, pady=5)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready. Load CSV to begin.",
            font=ctk.CTkFont(size=11),
            text_color="#ffffff",
        )
        self.status_label.pack(side="left", padx=10)
        self._update_status_display()

    def _create_controls(self):
        """Create the main control surface."""
        control_container = ctk.CTkFrame(self, fg_color="#3a3a3a", corner_radius=10)
        control_container.pack(fill="both", expand=True, padx=10, pady=10)

        left_panel = ctk.CTkFrame(
            control_container,
            fg_color="#4a4a4a",
            width=250,
            corner_radius=8,
        )
        left_panel.pack(side="left", fill="y", padx=5, pady=5)

        right_panel = ctk.CTkFrame(
            control_container,
            fg_color="#4a4a4a",
            width=250,
            corner_radius=8,
        )
        right_panel.pack(side="right", fill="y", padx=5, pady=5)

        center_panel = ctk.CTkFrame(
            control_container,
            fg_color="#5a5a5a",
            corner_radius=8,
        )
        center_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self._create_pair_controls(left_panel, "A")
        self._create_pair_controls(right_panel, "B")
        self._create_chart_panel(center_panel)
        self._create_playback_controls(center_panel)

    def _create_chart_panel(self, parent):
        """Create the market chart and playback playhead display."""
        chart_frame = ctk.CTkFrame(parent, fg_color="#20262b", corner_radius=6)
        chart_frame.pack(fill="x", padx=5, pady=5)

        header_frame = ctk.CTkFrame(chart_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            header_frame,
            text="Market View",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")
        self.chart_info_label = ctk.CTkLabel(
            header_frame,
            text="Load CSV to view chart",
            font=ctk.CTkFont(size=11),
            anchor="e",
        )
        self.chart_info_label.pack(side="right", fill="x", expand=True)

        self.chart_canvas = Canvas(
            chart_frame,
            height=230,
            bg="#111418",
            highlightthickness=0,
        )
        self.chart_canvas.pack(fill="x", padx=8, pady=(0, 8))
        self.chart_canvas.bind("<Configure>", lambda _event: self._draw_chart_static())

    def _create_pair_controls(self, panel, pair_name: str):
        """Create controls for a pair panel."""
        pair_frame = ctk.CTkFrame(panel, fg_color="#3a3a3a", corner_radius=6)
        pair_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            pair_frame,
            text=f"Pair {pair_name} Controls",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=5)

        pair_select = ctk.CTkComboBox(
            panel,
            values=["All"],
            state="readonly",
            command=lambda choice, slot=pair_name: self._on_pair_select(slot, choice),
        )
        pair_select.pack(pady=5)
        pair_select.set("All")

        volume_frame = ctk.CTkFrame(panel, fg_color="#3a3a3a", corner_radius=6)
        volume_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(volume_frame, text="Volume", font=ctk.CTkFont(size=12)).pack(
            pady=5
        )
        volume_slider = ctk.CTkSlider(
            panel,
            from_=0,
            to=100,
            number_of_steps=100,
            command=lambda value, slot=pair_name: self._on_volume_change(slot, value),
        )
        volume_slider.pack(pady=5)

        pitch_frame = ctk.CTkFrame(panel, fg_color="#3a3a3a", corner_radius=6)
        pitch_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            pitch_frame, text="Pitch Sensitivity", font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        pitch_slider = ctk.CTkSlider(
            panel,
            from_=1,
            to=10,
            number_of_steps=10,
            command=lambda value, slot=pair_name: self._on_pitch_change(slot, value),
        )
        pitch_slider.pack(pady=5)

        noise_frame = ctk.CTkFrame(panel, fg_color="#3a3a3a", corner_radius=6)
        noise_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            noise_frame, text="Noise Sensitivity", font=ctk.CTkFont(size=12)
        ).pack(pady=5)
        noise_slider = ctk.CTkSlider(
            panel,
            from_=0,
            to=100,
            number_of_steps=100,
            command=lambda value, slot=pair_name: self._on_noise_change(slot, value),
        )
        noise_slider.pack(pady=5)

        controls = {
            "pair_select": pair_select,
            "volume_slider": volume_slider,
            "pitch_slider": pitch_slider,
            "noise_slider": noise_slider,
        }

        if pair_name == "B":
            right_channel_checkbox = ctk.CTkCheckBox(
                panel,
                text="Enable as right channel",
                variable=self.right_channel_var,
                command=self._on_right_channel_toggle,
            )
            right_channel_checkbox.pack(pady=10)
            controls["right_channel_checkbox"] = right_channel_checkbox

        self.pair_controls[pair_name] = controls

    def _create_playback_controls(self, center_panel):
        """Create playback, advanced controls, and status widgets."""
        # pylint: disable=too-many-locals,too-many-statements
        playback_frame = ctk.CTkFrame(center_panel, fg_color="#3a3a3a", corner_radius=6)
        playback_frame.pack(fill="x", padx=5, pady=5)

        selectors_frame = ctk.CTkFrame(
            playback_frame, fg_color="#2b2b2b", corner_radius=4
        )
        selectors_frame.pack(fill="x", padx=5, pady=5)

        mode_select = ctk.CTkComboBox(
            selectors_frame,
            values=["Single", "Stereo"],
            state="readonly",
            command=self._on_mode_change,
        )
        mode_select.pack(side="left", padx=8, pady=8)
        mode_select.set("Single")

        speed_select = ctk.CTkComboBox(
            selectors_frame,
            values=["0.25x", "0.5x", "1x", "2x", "4x", "8x"],
            state="readonly",
            command=self._on_speed_change,
        )
        speed_select.pack(side="left", padx=8, pady=8)
        speed_select.set("1x")

        render_mode_select = ctk.CTkComboBox(
            selectors_frame,
            values=["Step", "Continuous"],
            state="readonly",
            command=self._on_render_mode_change,
        )
        render_mode_select.pack(side="left", padx=8, pady=8)
        render_mode_select.set("Step")

        loop_checkbox = ctk.CTkCheckBox(
            selectors_frame,
            text="Loop playback",
            variable=self.loop_var,
            command=self._on_loop_toggle,
        )
        loop_checkbox.pack(side="left", padx=8, pady=8)

        control_frame = ctk.CTkFrame(playback_frame, fg_color="#2b2b2b", corner_radius=4)
        control_frame.pack(fill="x", padx=5, pady=5)

        play_button = ctk.CTkButton(
            control_frame,
            text="▶ Play",
            width=90,
            height=40,
            command=self._on_play,
        )
        play_button.pack(side="left", padx=5, pady=5)

        pause_button = ctk.CTkButton(
            control_frame,
            text="⏸ / ▶",
            width=90,
            height=40,
            command=self._on_pause,
        )
        pause_button.pack(side="left", padx=5, pady=5)

        stop_button = ctk.CTkButton(
            control_frame,
            text="⏹ Stop",
            width=90,
            height=40,
            command=self._on_stop,
        )
        stop_button.pack(side="left", padx=5, pady=5)

        record_button = ctk.CTkButton(
            control_frame,
            text="🔴 Record",
            width=130,
            height=40,
            command=self._on_record,
        )
        record_button.pack(side="right", padx=5, pady=5)

        advanced_frame = ctk.CTkFrame(playback_frame, fg_color="#2b2b2b", corner_radius=4)
        advanced_frame.pack(fill="x", padx=5, pady=5)

        base_pitch_slider = self._add_labeled_slider(
            advanced_frame,
            "Base Pitch",
            (200, 1200, 100),
            self._on_base_pitch_change,
        )
        smoothness_slider = self._add_labeled_slider(
            advanced_frame,
            "Smoothness",
            (0, 100, 100),
            self._on_smoothness_change,
        )
        gate_slider = self._add_labeled_slider(
            advanced_frame,
            "Gate Threshold",
            (0, 100, 100),
            self._on_gate_change,
        )

        toggle_frame = ctk.CTkFrame(playback_frame, fg_color="#2b2b2b", corner_radius=4)
        toggle_frame.pack(fill="x", padx=5, pady=5)

        trust_checkbox = ctk.CTkCheckBox(
            toggle_frame,
            text="Trust -> Volume",
            variable=self.trust_volume_var,
            command=self._on_trust_toggle,
        )
        trust_checkbox.pack(side="left", padx=8, pady=8)

        spread_checkbox = ctk.CTkCheckBox(
            toggle_frame,
            text="Mute Spread Layer",
            variable=self.spread_mute_var,
            command=self._on_spread_toggle,
        )
        spread_checkbox.pack(side="left", padx=8, pady=8)

        regime_checkbox = ctk.CTkCheckBox(
            toggle_frame,
            text="Mute Regime Layer",
            variable=self.regime_mute_var,
            command=self._on_regime_toggle,
        )
        regime_checkbox.pack(side="left", padx=8, pady=8)

        api_frame = ctk.CTkFrame(playback_frame, fg_color="#2b2b2b", corner_radius=4)
        api_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(api_frame, text="API Key (future use)").pack(
            side="left", padx=(10, 6), pady=8
        )
        api_key_entry = ctk.CTkEntry(
            api_frame,
            textvariable=self.api_key_var,
            placeholder_text="Optional Finnhub key",
            width=280,
        )
        api_key_entry.pack(side="left", padx=6, pady=8)

        runtime_frame = ctk.CTkFrame(playback_frame, fg_color="#1f1f1f", corner_radius=6)
        runtime_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(
            runtime_frame,
            text="Status Box",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 4))

        status_grid = ctk.CTkFrame(runtime_frame, fg_color="transparent")
        status_grid.pack(fill="x", padx=10, pady=(0, 10))

        for label_text, key in (
            ("Current Timestamp", "timestamp"),
            ("Current Spread", "spread"),
            ("Trade Eligible", "trade_eligible"),
            ("Trust Value", "trust"),
            ("Playback Time", "playback_time"),
        ):
            row = ctk.CTkFrame(status_grid, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"{label_text}:", width=140, anchor="w").pack(
                side="left"
            )
            value_label = ctk.CTkLabel(row, text="-", anchor="w")
            value_label.pack(side="left", padx=6)
            self.status_widgets[key] = value_label

        self.playback_widgets = {
            "mode_select": mode_select,
            "speed_select": speed_select,
            "render_mode_select": render_mode_select,
            "loop_checkbox": loop_checkbox,
            "play_button": play_button,
            "pause_button": pause_button,
            "stop_button": stop_button,
            "record_button": record_button,
            "base_pitch_slider": base_pitch_slider,
            "smoothness_slider": smoothness_slider,
            "gate_slider": gate_slider,
            "trust_checkbox": trust_checkbox,
            "spread_checkbox": spread_checkbox,
            "regime_checkbox": regime_checkbox,
            "api_key_entry": api_key_entry,
        }

    def _add_labeled_slider(self, parent, label, slider_range, command):
        """Create a slider row with a label."""
        start, end, steps = slider_range
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(frame, text=label, width=120, anchor="w").pack(side="left")
        slider = ctk.CTkSlider(
            frame,
            from_=start,
            to=end,
            number_of_steps=steps,
            command=command,
        )
        slider.pack(side="left", fill="x", expand=True, padx=8)
        return slider

    def _price_to_y(self, value: float, price_min: float, price_max: float) -> float:
        """Map a price-like value into the chart canvas Y coordinate."""
        _left, top, _right, bottom = self._chart_bounds
        if price_max <= price_min:
            return (top + bottom) / 2
        return bottom - ((value - price_min) / (price_max - price_min)) * (bottom - top)

    def _index_to_x(self, index: int, point_count: int) -> float:
        """Map a chart row index into the chart canvas X coordinate."""
        left, _top, right, _bottom = self._chart_bounds
        if point_count <= 1:
            return (left + right) / 2
        return left + (index / (point_count - 1)) * (right - left)

    def _intensity_color(self, value: float) -> str:
        """Return a dark blue color scaled by audio intensity."""
        clamped_value = max(0.0, min(float(value), 1.0))
        red = int(20 + clamped_value * 20)
        green = int(31 + clamped_value * 70)
        blue = int(45 + clamped_value * 130)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _refresh_chart_data(self):
        """Reload chart data from the controller and redraw the chart."""
        self.chart_data = self.controller.get_chart_data()
        self._draw_chart_static()
        self._update_chart_playhead(self.chart_data.get("current_index", 0))

    def _draw_chart_static(self):
        """Draw the static chart layer."""
        if self.chart_canvas is None:
            return

        self.chart_canvas.delete("all")
        width = max(self.chart_canvas.winfo_width(), 640)
        height = max(self.chart_canvas.winfo_height(), 220)
        left, right = 48, width - 14
        top, bottom = 16, height - 42
        self._chart_bounds = (left, top, right, bottom)

        points = (self.chart_data or {}).get("points", [])
        if not points:
            self.chart_canvas.create_text(
                width / 2,
                height / 2,
                text="Load CSV to view market chart",
                fill="#9aa7b2",
                font=("TkDefaultFont", 11),
            )
            return

        lows = [point["low"] for point in points]
        highs = [point["high"] for point in points]
        price_min = min(lows)
        price_max = max(highs)
        if price_max <= price_min:
            price_min -= 0.5
            price_max += 0.5

        for grid_index in range(5):
            y = top + (grid_index / 4) * (bottom - top)
            self.chart_canvas.create_line(left, y, right, y, fill="#25313a")

        point_count = len(points)
        step = (right - left) / max(point_count - 1, 1)
        body_width = max(1, min(8, step * 0.65))
        intensity_top = bottom + 8
        intensity_bottom = height - 12

        for index, point in enumerate(points):
            x = self._index_to_x(index, point_count)
            intensity_color = self._intensity_color(point["intensity"])
            self.chart_canvas.create_rectangle(
                x - max(step / 2, 0.5),
                intensity_top,
                x + max(step / 2, 0.5),
                intensity_bottom,
                fill=intensity_color,
                outline="",
            )

            open_y = self._price_to_y(point["open"], price_min, price_max)
            high_y = self._price_to_y(point["high"], price_min, price_max)
            low_y = self._price_to_y(point["low"], price_min, price_max)
            close_y = self._price_to_y(point["close"], price_min, price_max)
            up_color = "#4cc38a"
            down_color = "#f06d5f"
            candle_color = up_color if point["close"] >= point["open"] else down_color

            if self.chart_data.get("chart_type") == "candles":
                self.chart_canvas.create_line(x, high_y, x, low_y, fill="#94a3ad")
                self.chart_canvas.create_rectangle(
                    x - body_width / 2,
                    min(open_y, close_y),
                    x + body_width / 2,
                    max(open_y, close_y) + 1,
                    fill=candle_color,
                    outline=candle_color,
                )
            else:
                self.chart_canvas.create_line(x, bottom, x, close_y, fill=candle_color)

        self._update_chart_playhead((self.chart_data or {}).get("current_index", 0))

    def _update_chart_playhead(self, event_index=0):
        """Move the playhead and current-row info on the chart."""
        if self.chart_canvas is None or not self.chart_data:
            return

        points = self.chart_data.get("points", [])
        if not points:
            return

        try:
            index = int(event_index)
        except (TypeError, ValueError):
            index = 0
        index = max(0, min(index, len(points) - 1))
        point = points[index]
        x = self._index_to_x(index, len(points))
        left, top, right, bottom = self._chart_bounds

        self.chart_canvas.delete("playhead")
        self.chart_canvas.create_line(
            x,
            top,
            x,
            bottom + 30,
            fill="#f6d365",
            width=2,
            tags="playhead",
        )
        self.chart_canvas.create_rectangle(
            max(left, x - 4),
            top,
            min(right, x + 4),
            bottom,
            outline="#f6d365",
            tags="playhead",
        )

        if self.chart_info_label is not None:
            self.chart_info_label.configure(
                text=(
                    f"{point['timestamp']} | close {point['close']:.5f} | "
                    f"spread {point['spread']:.2f} | vol {point['volatility']:.2f} | "
                    f"intensity {point['intensity']:.2f}"
                )
            )

    def _schedule_live_audio_refresh(self):
        """Debounce a live audio re-render while playback is running."""
        if self._is_closing:
            return
        if not self.controller.playback.is_playing():
            return
        if self.controller.playback.is_paused():
            return

        if self._live_audio_refresh_after_id is not None:
            try:
                self.after_cancel(self._live_audio_refresh_after_id)
            except (TclError, ValueError):
                pass

        self._live_audio_refresh_after_id = self.after(
            350,
            self._run_live_audio_refresh,
        )

    def _run_live_audio_refresh(self):
        """Apply current slider settings to active playback."""
        self._live_audio_refresh_after_id = None
        try:
            did_refresh = self.controller.refresh_active_playback()
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
            self._status_vars["state"] = f"Live update failed: {exc}"
            self._update_status_display()
            return

        if did_refresh:
            self._status_vars["state"] = "Playback: updated"
            self._update_status_display()
        else:
            self._status_vars["state"] = "Playback: restart needed for this change"
            self._update_status_display()

    def _sync_controls_from_settings(self):
        """Populate the UI from the controller's active settings."""
        global_settings = self.controller.get_settings()

        for pair_name in ("A", "B"):
            pair_settings = self.controller.get_pair_settings(pair_name)
            self.pair_controls[pair_name]["volume_slider"].set(pair_settings["volume"] * 100)
            self.pair_controls[pair_name]["pitch_slider"].set(
                1 + ((pair_settings["pitch_sensitivity"] - 0.5) * (9.0 / 2.5))
            )
            self.pair_controls[pair_name]["noise_slider"].set(
                pair_settings["noise_sensitivity"] / 3.0 * 100
            )

        self.playback_widgets["mode_select"].set(self.controller.playback_mode)
        self.playback_widgets["speed_select"].set("1x")
        self.playback_widgets["render_mode_select"].set(self.controller.render_mode)
        self.playback_widgets["base_pitch_slider"].set(global_settings["base_pitch"])
        self.playback_widgets["smoothness_slider"].set(global_settings["smoothness"] * 100)
        self.playback_widgets["gate_slider"].set(global_settings["gate_threshold"] * 100)

    def _poll_runtime_status(self):
        """Refresh the runtime status box on a timer."""
        if self._is_closing:
            return

        snapshot = self.controller.get_runtime_status()
        for key, label in self.status_widgets.items():
            label.configure(text=snapshot.get(key, "-"))
        self._update_chart_playhead(snapshot.get("event_index", 0))
        self._status_poll_after_id = self.after(200, self._poll_runtime_status)

    def _on_open_file(self):
        """Open a CSV file and load it into the controller."""
        initial_dir = self.controller.project_root.parent
        file_path = filedialog.askopenfilename(
            title="Open backtest CSV",
            initialdir=str(initial_dir),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            metadata = self.controller.load_csv(file_path)
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
            self._status_vars["state"] = f"Load failed: {exc}"
            self._update_status_display()
            return

        self._update_pair_options(metadata["pair_options"])
        self._status_vars["file"] = f"Loaded: {metadata['file_path']}"
        if metadata.get("processed_rows") != metadata["rows"]:
            self._status_vars["rows"] = (
                f"Rows: {metadata['rows']} -> audio: {metadata['processed_rows']}"
            )
        else:
            self._status_vars["rows"] = f"Rows: {metadata['rows']}"
        self._status_vars["state"] = "Ready to play"
        self._update_status_display()
        self._refresh_chart_data()

    def _update_pair_options(self, pair_options):
        """Update combo-box options after data load."""
        for pair_name, values in pair_options.items():
            selector = self.pair_controls[pair_name]["pair_select"]
            selector.configure(values=values)
            selector.set(values[0])
            self.controller.set_pair_selection(pair_name, values[0])

    def _on_pair_select(self, pair_name: str, choice: str):
        """Handle pair selector updates."""
        self.controller.set_pair_selection(pair_name, choice)
        self._status_vars[f"{pair_name}_pair"] = f"Pair {pair_name}: {choice}"
        self._update_status_display()
        self._refresh_chart_data()
        self._schedule_live_audio_refresh()

    def _on_mode_change(self, mode: str):
        """Handle playback mode changes."""
        self.controller.set_playback_mode(mode)
        self._status_vars["mode"] = f"Mode: {mode}"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_speed_change(self, speed: str):
        """Handle playback speed changes."""
        self.controller.set_playback_speed(speed)
        self._status_vars["speed"] = f"Speed: {speed}"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_render_mode_change(self, mode: str):
        """Handle render-mode changes."""
        self.controller.set_render_mode(mode)
        self._status_vars["render"] = f"Render: {mode}"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_loop_toggle(self):
        """Handle loop toggles."""
        self.controller.set_loop_enabled(self.loop_var.get())
        self._status_vars["loop"] = (
            "Loop: on" if self.loop_var.get() else "Loop: off"
        )
        self._update_status_display()

    def _on_right_channel_toggle(self):
        """Handle Pair B stereo enable/disable."""
        self.controller.set_right_channel_enabled(self.right_channel_var.get())
        self._status_vars["right"] = (
            "Pair B: active" if self.right_channel_var.get() else "Pair B: muted"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_volume_change(self, pair_name: str, value: float):
        """Handle volume slider changes."""
        self.controller.set_pair_volume_percent(pair_name, value)
        self._status_vars[f"{pair_name}_volume"] = (
            f"Pair {pair_name} volume: {value / 100:.0%}"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_pitch_change(self, pair_name: str, value: float):
        """Handle pitch sensitivity changes."""
        self.controller.set_pair_pitch_slider_value(pair_name, value)
        self._status_vars[f"{pair_name}_pitch"] = (
            f"Pair {pair_name} pitch: {value:.0f}/10"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_noise_change(self, pair_name: str, value: float):
        """Handle noise sensitivity changes."""
        self.controller.set_pair_noise_percent(pair_name, value)
        self._status_vars[f"{pair_name}_noise"] = (
            f"Pair {pair_name} noise: {value:.0f}%"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_base_pitch_change(self, value: float):
        """Handle base-pitch slider changes."""
        self.controller.set_base_pitch(value)
        self._status_vars["base_pitch"] = f"Base pitch: {value:.0f} Hz"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_smoothness_change(self, value: float):
        """Handle smoothing changes."""
        self.controller.set_smoothness_percent(value)
        self._status_vars["smooth"] = f"Smoothness: {value:.0f}%"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_gate_change(self, value: float):
        """Handle gate-threshold changes."""
        self.controller.set_gate_threshold_percent(value)
        self._status_vars["gate"] = f"Gate: {value:.0f}%"
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_trust_toggle(self):
        """Handle trust-to-volume toggles."""
        self.controller.set_trust_volume_enabled(self.trust_volume_var.get())
        self._status_vars["trust_mode"] = (
            "Trust->Volume: on"
            if self.trust_volume_var.get()
            else "Trust->Volume: off"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_spread_toggle(self):
        """Handle spread-layer mute toggles."""
        self.controller.set_spread_muted(self.spread_mute_var.get())
        self._status_vars["spread_mode"] = (
            "Spread layer: muted"
            if self.spread_mute_var.get()
            else "Spread layer: active"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_regime_toggle(self):
        """Handle regime-layer mute toggles."""
        self.controller.set_regime_muted(self.regime_mute_var.get())
        self._status_vars["regime_mode"] = (
            "Regime layer: muted"
            if self.regime_mute_var.get()
            else "Regime layer: active"
        )
        self._update_status_display()
        self._schedule_live_audio_refresh()

    def _on_api_key_change(self, *_args):
        """Handle API key entry changes."""
        self.controller.set_api_key(self.api_key_var.get())

    def _on_play(self):
        """Handle play button presses."""
        try:
            self.controller.play()
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
            self._status_vars["state"] = f"Playback failed: {exc}"
            self._update_status_display()
            return

        self._status_vars["state"] = "Playback: running"
        self._update_status_display()
        self._update_chart_playhead(self.controller.current_event_index)

    def _on_pause(self):
        """Handle pause/resume button presses."""
        if self.controller.playback.is_paused():
            self.controller.play()
            self._status_vars["state"] = "Playback: resumed"
        else:
            self.controller.pause()
            self._status_vars["state"] = "Playback: paused"
        self._update_status_display()

    def _on_stop(self):
        """Handle stop button presses."""
        recording_path = self.controller.stop()
        if recording_path:
            self._status_vars["recording"] = f"Saved: {recording_path}"
            self.playback_widgets["record_button"].configure(text="🔴 Record")

        self._status_vars["state"] = "Playback: stopped"
        self._update_status_display()
        self._update_chart_playhead(0)

    def _on_record(self):
        """Handle record button presses."""
        if self.controller.is_recording():
            recording_path = self.controller.stop_recording()
            if recording_path:
                self._status_vars["recording"] = f"Saved: {recording_path}"
            self.playback_widgets["record_button"].configure(text="🔴 Record")
            self._status_vars["state"] = "Recording stopped"
        else:
            self.controller.start_recording()
            self.playback_widgets["record_button"].configure(text="■ Save Recording")
            self._status_vars["state"] = "Recording armed"

        self._update_status_display()

    def _on_close(self):
        """Stop runtime resources before closing the Tk window."""
        if self._is_closing:
            return

        self._is_closing = True
        if self._status_poll_after_id is not None:
            try:
                self.after_cancel(self._status_poll_after_id)
            except (TclError, ValueError):
                pass
            self._status_poll_after_id = None
        if self._live_audio_refresh_after_id is not None:
            try:
                self.after_cancel(self._live_audio_refresh_after_id)
            except (TclError, ValueError):
                pass
            self._live_audio_refresh_after_id = None

        self.controller.shutdown()
        self.destroy()

    def _update_status_display(self):
        """Refresh the status-bar text."""
        if not self._status_vars:
            status_text = "Ready. Load CSV to begin."
        else:
            status_text = " | ".join(self._status_vars.values())

        if self.status_label is not None:
            self.status_label.configure(text=status_text)


def create_main_window(controller: SonificationController) -> MainWindow:
    """Create and return the main window."""
    return MainWindow(controller=controller)
