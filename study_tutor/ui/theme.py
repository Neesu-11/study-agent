"""Shared Tkinter styling."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PAPER = "#f6f3ec"
INK = "#1c2430"
TEAL = "#1f4e5f"
TEAL_DARK = "#173e4c"
MUTED = "#5e6872"
LINE = "#d9d3c7"
CARD = "#fffdf9"
WEAK = "#8c2f2f"
OK = "#1f4e5f"


def apply_theme(root: tk.Misc) -> None:
    root.configure(background=PAPER)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=PAPER, foreground=INK, font=("Segoe UI", 10))
    style.configure("TFrame", background=PAPER)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=PAPER, foreground=INK)
    style.configure("Muted.TLabel", background=PAPER, foreground=MUTED)
    style.configure("Header.TLabel", background=PAPER, foreground=TEAL, font=("Segoe UI", 20, "bold"))
    style.configure("Subhead.TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 12, "bold"))
    style.configure("Topic.TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 16, "bold"))
    style.configure("Eyebrow.TLabel", background=PAPER, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("TButton", padding=(12, 6))
    style.configure("Quiet.TButton", padding=(8, 4))
    style.configure("Accent.TButton", background=TEAL, foreground="#ffffff", padding=(12, 6))
    style.map(
        "Accent.TButton",
        background=[("pressed", TEAL_DARK), ("active", "#2a6578"), ("disabled", "#9aadae")],
        foreground=[("disabled", "#f4f7f7")],
    )
    style.configure("Treeview", rowheight=28, font=("Segoe UI", 10), background=CARD, fieldbackground=CARD)
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    style.configure("TEntry", padding=4)
    style.configure("TLabelframe", background=PAPER, bordercolor=LINE, relief="solid")
    style.configure("TLabelframe.Label", background=PAPER, foreground=TEAL, font=("Segoe UI", 9, "bold"))
    style.configure("Horizontal.TProgressbar", background=TEAL, troughcolor=LINE)
