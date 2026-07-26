"""Textual TUI shell for exploring a Meeseeks execution package.

This package only renders an already-loaded `meeseeks.plan.ExecutionPackage`.
It never discovers or loads a plan from disk itself — that is a CLI-layer
concern. See `meeseeks.plan_tui.app.PlanApp`.
"""

from meeseeks.plan_tui.app import PlanApp

__all__ = ["PlanApp"]
