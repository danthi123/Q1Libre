# printopt — PC-Assisted Print Optimization for Klipper CoreXY Printers

**Date:** 2026-03-25
**Status:** Approved

## Overview

`printopt` is a desktop-side toolkit that connects to Klipper-based CoreXY printers via Moonraker's API to provide advanced print optimization through three features: enhanced vibration analysis, predictive flow compensation, and real-time thermal simulation. It runs on the user's PC and communicates over the local network — no hardware mods or printer-side changes required.

**Target:** Any CoreXY printer running Klipper + Moonraker. Not printer-specific — tested on Qidi Q1 Pro, designed to work universally (Voron, Ratrig, etc.).

**Requirements:**
- Klipper + Moonraker (all features)
- ADXL345 accelerometer (vibration analysis only)
- Python 3.10+
- Optional: NVIDIA GPU with CUDA for high-resolution thermal simulation

## Architecture

Plugin-based architecture. Single process with isolated plugins running in separate threads. Core handles Moonraker connection and web dashboard. Plugins register for printer state events and dashboard widgets. One plugin crashing does not affect others.

```
┌─────────────────────────────────────────────┐
│                printopt process              │
│                                             │
│  ┌─────────┐  ┌─────────────────────────┐  │
│  │   CLI   │  │     Web Dashboard       │  │
│  │         │  │  (FastAPI + WebSocket)   │  │
│  └────┬────┘  └────────────┬────────────┘  │
│       │                    │                │
│  ┌────┴────────────────────┴────────────┐  │
│  │            Plugin Manager            │  │
│  │  ┌──────────┬──────────┬──────────┐  │  │
│  │  │Vibration │  Flow    │ Thermal  │  │  │
│  │  │ (thread) │ (thread) │ (thread) │  │  │
│  │  └──────────┴──────────┴──────────┘  │  │
│  └──────────────────┬───────────────────┘  │
│                     │                       │
│  ┌──────────────────┴───────────────────┐  │
│  │           Core Library               │  │
│  │  moonraker.py | gcode.py | plugin.py │  │
│  │  printer.py   | materials.py         │  │
│  └──────────────────┬───────────────────┘  │
└─────────────────────┼───────────────────────┘
                      │ WebSocket (JSON-RPC)
                      ▼
               ┌──────────────┐
               │  Moonraker   │
               │  (printer)   │
               └──────────────┘
```

## Project Structure

```
printopt/
├── pyproject.toml
├── src/
│   └── printopt/
│       ├── core/
│       │   ├── moonraker.py    # Async Moonraker websocket client
│       │   ├── gcode.py        # Gcode parser + geometric analysis
│       │   ├── printer.py      # Printer config model (auto-discovered)
│       │   ├── plugin.py       # Plugin base class + lifecycle
│       │   └── materials.py    # Filament material properties database
│       ├── dashboard/
│       │   ├── server.py       # FastAPI + websocket to browser
│       │   ├── static/         # JS, CSS
│       │   └── templates/      # HTML
│       ├── plugins/
│       │   ├── vibration/      # Enhanced vibration analysis
│       │   ├── flow/           # Predictive flow compensation
│       │   └── thermal/        # Real-time thermal simulation
│       └── cli.py              # CLI entry point
├── tests/
└── docs/
```

## Core Infrastructure

### Moonraker Client (`core/moonraker.py`)

Async websocket client using JSON-RPC 2.0:
- **Subscribe** — real-time printer state (position, temps, fan speed, print progress)
- **Inject** — send gcode commands with timing guarantees
- **Query** — pull printer config, file list, print metadata
- Auto-reconnect on connection loss
- Rate limiting on gcode injection to avoid flooding Klipper's command queue

### Gcode Parser (`core/gcode.py`)

Parses a full gcode file into a structured feature map:
- Geometric analysis: corners (direction change angle), thin walls, bridges, overhangs, small perimeters
- Time estimation per line — maps gcode line numbers to wall-clock time
- Shared by all three plugins: vibration correlates moves with resonance, flow uses it for lookahead, thermal uses it for heat deposition

### Printer Model (`core/printer.py`)

On `printopt connect <ip>`, queries Moonraker for:
- Bed size, kinematics type (CoreXY/cartesian)
- Accelerometer presence and config
- Input shaper current settings
- Extruder type (direct/bowden), nozzle diameter
- Available fans and heaters

Cached locally as JSON, re-validated on each `printopt run`.

### Plugin System (`core/plugin.py`)

- Base class with lifecycle hooks: `on_start`, `on_print_start`, `on_layer`, `on_print_end`, `on_stop`
- Each plugin runs in its own thread with an async event loop
- Plugins receive printer state updates via a shared event bus
- If a plugin crashes, the core catches it, logs the error, continues — other plugins unaffected
- Plugins register dashboard widgets (charts, heatmaps, controls) with the web server

### Materials Database (`core/materials.py`)

Per-filament profiles with properties needed by thermal simulation:
- Thermal conductivity, specific heat, density, glass transition temperature, CTE
- Ships with defaults for PLA, PETG, ABS, ASA, TPU
- User creates custom profiles via `printopt profile create`

## Plugin: Vibration Analysis

**Mode:** One-shot CLI command.

**Workflow:**
1. `printopt vibration analyze` starts test movements via Moonraker
2. X-axis and Y-axis frequency sweeps at increasing speeds
3. Optional: repeat at multiple bed positions (`--positions 9` for 3x3 grid)
4. Raw ADXL345 CSV captured by Klipper, pulled to PC via Moonraker file API
5. PC analysis:
   - High-resolution FFT using Welch's method (4x more frequency bins than Klipper default)
   - Multi-peak detection with prominence filtering (scipy.signal.find_peaks)
   - For each peak: evaluate all shaper types, score by remaining vibration vs. max acceleration loss
   - Multi-position: build resonance heatmap showing position-dependent frequency response
6. Results displayed in dashboard with interactive plots
7. `printopt vibration apply` writes optimized `[input_shaper]` config to printer

**Advantages over Klipper's built-in:**
- Higher FFT resolution reveals secondary resonance peaks
- Tests all shaper combinations per peak, not just top-scoring preset
- Multi-position analysis reveals gantry resonance variation across the bed
- Visual report with before/after simulation

## Plugin: Predictive Flow Compensation

**Mode:** Real-time daemon, active during printing.

**Workflow:**
1. On print start, parses full gcode file and builds feature map with every corner, bridge, thin wall, overhang, and speed transition tagged with line number and estimated time
2. Subscribes to Moonraker print status, tracks current position/line in real-time
3. Maintains 5-10 second lookahead window
4. For each upcoming feature, computes and injects compensating adjustments:

| Feature | Compensation | Mechanism |
|---|---|---|
| Sharp corner (>60°) | Boost PA 10-30%, restore after | `SET_PRESSURE_ADVANCE` |
| Thin wall (<2 perimeters) | Reduce speed 20%, slight flow boost | `M220` + `M221` |
| Bridge start | Reduce flow 5%, boost fan | `M221` + `SET_FAN_SPEED` |
| Overhang transition | Ramp fan up, slow outer wall | `SET_FAN_SPEED` + `M220` |
| Small perimeter (<4mm) | Slow down for cooling time | `M220` |
| Layer change on small feature | Brief dwell for thermal equalization | `G4` pause |

5. Commands injected 2-3 seconds before printer reaches each feature
6. All adjustments relative to slicer baseline — enhances, never overrides
7. Dashboard shows live timeline of upcoming features and active adjustments

**Calibration:**
- Ships with sensible defaults per filament type
- User prints calibration object, grades each feature
- Plugin tunes compensation weights based on feedback
- Profiles saved per filament

**Safety:**
- Bounded adjustments: PA max 2x baseline, flow ±15%, speed ±30%
- Dashboard kill switch disables all compensation instantly
- Plugin crash = slicer defaults continue (fail-safe)

## Plugin: Thermal Simulation

**Mode:** Real-time daemon, tightly coupled with flow plugin.

**Model:**
- 2D grid overlaid on bed at 1mm resolution (scales to any bed size)
- Each cell tracks accumulated heat over rolling 30-60 second window
- Updated every 0.5 seconds based on nozzle position and extrusion state

**Heat input per cell:**
`Q_in = volumetric_flow × (T_nozzle - T_glass) × specific_heat × density`

**Heat loss per cell per timestep:**
- Conduction to 4 neighboring cells (proportional to temperature difference)
- Convection to air (proportional to fan speed)
- Bed conduction (cells near bed temp equilibrate faster)
- Chamber ambient (enclosed printers lose heat slower)

**Predictions and actions:**

| Condition | Detection | Action (fed to flow plugin) |
|---|---|---|
| Heat accumulation on small feature | Cell temp rising above Tg | Slow down, boost fan |
| Thermal gradient across part | Adjacent cells differ >15°C | Warping risk — slow hot side |
| Island cooling too fast | Isolated cells losing heat | Reduce fan, speed up |
| Consistent overheating zone | Same cells hot across layers | Persistent slow-down zone |

**GPU acceleration:**
- Grid update is a parallel stencil operation — ideal for CUDA
- 1mm resolution: 60K cells — trivial for any GPU
- Optional 0.5mm (240K cells) or full 3D with Z-depth for capable GPUs
- Falls back to numpy on CPU — still fast enough at 1mm

**Integration with flow plugin:**
- Publishes thermal state grid every 0.5 seconds
- Flow plugin reads it during lookahead — if next feature is in a hot zone, factors into speed/fan decisions
- Combined is more powerful than either alone

## Web Dashboard

**Stack:** FastAPI backend, vanilla HTML/JS/Canvas frontend. No framework.

**Layout:**
- Left sidebar: plugin status indicators + live printer stats (temps, fan, Z, progress)
- Main panel: switches per active plugin (thermal heatmap / flow timeline / resonance plots)
- Bottom: scrolling event log of adjustments, warnings, feature detections
- Footer: Kill switch, pause all, reset compensation buttons — always visible

**Implementation:**
- WebSocket from browser to FastAPI — live updates at 2-5 Hz
- Thermal heatmap rendered on Canvas, updated every 0.5s
- Flow timeline: scrolling Gantt-style chart of upcoming features + active adjustments
- Vibration: interactive FFT plots with zoom and hover
- Mobile-responsive for phone monitoring on same network

## CLI Interface

```bash
# Setup
pip install printopt                      # CPU only
pip install printopt[gpu]                 # With CUDA support
printopt connect 192.168.0.248            # Auto-discover, cache config

# Vibration (one-shot)
printopt vibration analyze                # Standard analysis
printopt vibration analyze --positions 9  # 3x3 position grid
printopt vibration report                 # View results in dashboard
printopt vibration apply                  # Write config to printer

# Real-time (during prints)
printopt run                              # All plugins + dashboard
printopt run --plugins flow               # Flow only
printopt run --plugins flow,thermal       # Flow + thermal
printopt run --port 8080                  # Custom dashboard port

# Profiles
printopt profile create petg-elegoo       # Interactive creation
printopt profile list                     # List saved profiles
printopt run --profile petg-elegoo        # Use specific profile

# Dashboard at http://localhost:8484
```

## Implementation Priority

| Phase | Deliverable | Depends On |
|---|---|---|
| 0 | Project scaffolding, pyproject.toml, CI | Nothing |
| 1 | Core: Moonraker client, printer model, plugin system | Phase 0 |
| 2 | Core: Gcode parser with geometric analysis | Phase 0 |
| 3 | Dashboard skeleton (FastAPI + live printer status) | Phase 1 |
| 4 | Vibration analysis plugin | Phases 1, 2, 3 |
| 5 | Flow compensation plugin (basic: corners + bridges) | Phases 1, 2, 3 |
| 6 | Thermal simulation plugin (CPU, 2D grid) | Phases 1, 2, 3 |
| 7 | Flow + thermal integration | Phases 5, 6 |
| 8 | GPU acceleration for thermal | Phase 6 |
| 9 | Calibration workflow + filament profiles | Phase 5 |

Phases 4, 5, 6 can be developed in parallel once the core (Phases 1-3) is complete.
