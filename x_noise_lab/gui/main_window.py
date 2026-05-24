#!/usr/bin/env python3
"""FX Noise Lab - Main Window."""

from __future__ import annotations

from tkinter import BooleanVar, StringVar, filedialog

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
        self.pair_controls = {"A": {}, "B": {}}
        self.playback_widgets = {}

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

        left_panel = ctk.CTkFrame(control_container, fg_color="#4a4a4a", corner_radius=8)
        left_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        right_panel = ctk.CTkFrame(control_container, fg_color="#4a4a4a", corner_radius=8)
        right_panel.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        center_panel = ctk.CTkFrame(control_container, fg_color="#5a5a5a", corner_radius=8)
        center_panel.pack(side="bottom", fill="x", pady=5)

        self._create_pair_controls(left_panel, "A")
        self._create_pair_controls(right_panel, "B")
        self._create_playback_controls(center_panel)

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
        snapshot = self.controller.get_runtime_status()
        for key, label in self.status_widgets.items():
            label.configure(text=snapshot.get(key, "-"))
        self.after(200, self._poll_runtime_status)

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
        self._status_vars["rows"] = f"Rows: {metadata['rows']}"
        self._status_vars["state"] = "Ready to play"
        self._update_status_display()

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

    def _on_mode_change(self, mode: str):
        """Handle playback mode changes."""
        self.controller.set_playback_mode(mode)
        self._status_vars["mode"] = f"Mode: {mode}"
        self._update_status_display()

    def _on_speed_change(self, speed: str):
        """Handle playback speed changes."""
        self.controller.set_playback_speed(speed)
        self._status_vars["speed"] = f"Speed: {speed}"
        self._update_status_display()

    def _on_render_mode_change(self, mode: str):
        """Handle render-mode changes."""
        self.controller.set_render_mode(mode)
        self._status_vars["render"] = f"Render: {mode}"
        self._update_status_display()

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

    def _on_volume_change(self, pair_name: str, value: float):
        """Handle volume slider changes."""
        self.controller.set_pair_volume_percent(pair_name, value)
        self._status_vars[f"{pair_name}_volume"] = (
            f"Pair {pair_name} volume: {value / 100:.0%}"
        )
        self._update_status_display()

    def _on_pitch_change(self, pair_name: str, value: float):
        """Handle pitch sensitivity changes."""
        self.controller.set_pair_pitch_slider_value(pair_name, value)
        self._status_vars[f"{pair_name}_pitch"] = (
            f"Pair {pair_name} pitch: {value:.0f}/10"
        )
        self._update_status_display()

    def _on_noise_change(self, pair_name: str, value: float):
        """Handle noise sensitivity changes."""
        self.controller.set_pair_noise_percent(pair_name, value)
        self._status_vars[f"{pair_name}_noise"] = (
            f"Pair {pair_name} noise: {value:.0f}%"
        )
        self._update_status_display()

    def _on_base_pitch_change(self, value: float):
        """Handle base-pitch slider changes."""
        self.controller.set_base_pitch(value)
        self._status_vars["base_pitch"] = f"Base pitch: {value:.0f} Hz"
        self._update_status_display()

    def _on_smoothness_change(self, value: float):
        """Handle smoothing changes."""
        self.controller.set_smoothness_percent(value)
        self._status_vars["smooth"] = f"Smoothness: {value:.0f}%"
        self._update_status_display()

    def _on_gate_change(self, value: float):
        """Handle gate-threshold changes."""
        self.controller.set_gate_threshold_percent(value)
        self._status_vars["gate"] = f"Gate: {value:.0f}%"
        self._update_status_display()

    def _on_trust_toggle(self):
        """Handle trust-to-volume toggles."""
        self.controller.set_trust_volume_enabled(self.trust_volume_var.get())
        self._status_vars["trust_mode"] = (
            "Trust->Volume: on"
            if self.trust_volume_var.get()
            else "Trust->Volume: off"
        )
        self._update_status_display()

    def _on_spread_toggle(self):
        """Handle spread-layer mute toggles."""
        self.controller.set_spread_muted(self.spread_mute_var.get())
        self._status_vars["spread_mode"] = (
            "Spread layer: muted"
            if self.spread_mute_var.get()
            else "Spread layer: active"
        )
        self._update_status_display()

    def _on_regime_toggle(self):
        """Handle regime-layer mute toggles."""
        self.controller.set_regime_muted(self.regime_mute_var.get())
        self._status_vars["regime_mode"] = (
            "Regime layer: muted"
            if self.regime_mute_var.get()
            else "Regime layer: active"
        )
        self._update_status_display()

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
