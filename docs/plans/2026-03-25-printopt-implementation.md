# printopt Implementation Plan — Phases 0-3 (Core Infrastructure)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the core infrastructure for printopt — a PC-side print optimization toolkit for Klipper CoreXY printers. This plan covers project scaffolding, Moonraker client, gcode parser, printer model, plugin system, and dashboard skeleton.

**Architecture:** Plugin-based single process. Core handles Moonraker connection via async websocket. Plugins run in isolated threads. FastAPI serves a live web dashboard. All communication to the printer is via Moonraker's JSON-RPC API over the local network.

**Tech Stack:** Python 3.10+, asyncio, websockets, numpy, scipy, FastAPI, uvicorn, pytest, pytest-asyncio

**Repo:** New repo `printopt` (separate from q1libre). Tested on Qidi Q1 Pro but designed for any Klipper CoreXY.

**Design doc:** `docs/plans/2026-03-25-printopt-design.md` in the q1libre repo.

---

## Phase 0: Project Scaffolding

### Task 1: Initialize repo and project structure

**Files:**
- Create: `pyproject.toml`
- Create: `src/printopt/__init__.py`
- Create: `src/printopt/core/__init__.py`
- Create: `src/printopt/plugins/__init__.py`
- Create: `src/printopt/dashboard/__init__.py`
- Create: `src/printopt/cli.py`
- Create: `tests/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `.gitignore`

**Step 1: Create repo and directory structure**

```bash
mkdir printopt && cd printopt
git init
mkdir -p src/printopt/core src/printopt/plugins/vibration src/printopt/plugins/flow src/printopt/plugins/thermal src/printopt/dashboard/static src/printopt/dashboard/templates tests/core tests/plugins
```

**Step 2: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "printopt"
version = "0.1.0"
description = "PC-assisted print optimization for Klipper CoreXY printers"
requires-python = ">=3.10"
dependencies = [
    "websockets>=12.0",
    "numpy>=1.24",
    "scipy>=1.10",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]

[project.optional-dependencies]
gpu = ["cupy-cuda12x>=13.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "pytest-cov"]

[project.scripts]
printopt = "printopt.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Write .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
.pytest_cache/
*.so
.DS_Store
Thumbs.db
.vscode/
.idea/
```

**Step 4: Write minimal __init__.py files**

```python
# src/printopt/__init__.py
"""printopt — PC-assisted print optimization for Klipper CoreXY printers."""
__version__ = "0.1.0"
```

All other `__init__.py` files are empty.

**Step 5: Write CLI skeleton**

```python
# src/printopt/cli.py
"""CLI entry point for printopt."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="printopt",
        description="PC-assisted print optimization for Klipper CoreXY printers.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # printopt connect <host>
    connect_parser = subparsers.add_parser("connect", help="Connect to a printer")
    connect_parser.add_argument("host", help="Printer IP or hostname")

    # printopt run
    run_parser = subparsers.add_parser("run", help="Start optimization daemon")
    run_parser.add_argument("--plugins", default="all", help="Comma-separated plugin list or 'all'")
    run_parser.add_argument("--port", type=int, default=8484, help="Dashboard port")
    run_parser.add_argument("--profile", default=None, help="Filament profile name")

    # printopt vibration
    vib_parser = subparsers.add_parser("vibration", help="Vibration analysis")
    vib_sub = vib_parser.add_subparsers(dest="vib_command")
    analyze = vib_sub.add_parser("analyze", help="Run vibration analysis")
    analyze.add_argument("--positions", type=int, default=1, help="Number of bed positions to test")
    vib_sub.add_parser("report", help="View analysis results")
    vib_sub.add_parser("apply", help="Apply optimized input shaper config")

    # printopt profile
    prof_parser = subparsers.add_parser("profile", help="Filament profiles")
    prof_sub = prof_parser.add_subparsers(dest="prof_command")
    prof_sub.add_parser("list", help="List saved profiles")
    create = prof_sub.add_parser("create", help="Create a new profile")
    create.add_argument("name", help="Profile name")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    print(f"printopt: {args.command} (not yet implemented)")


if __name__ == "__main__":
    main()
```

**Step 6: Verify the skeleton works**

```bash
pip install -e ".[dev]"
printopt --help
printopt connect 192.168.0.248
```

Expected: help text prints, connect prints "not yet implemented".

**Step 7: Write initial test**

```python
# tests/test_cli.py
"""Smoke test for CLI entry point."""

import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "printopt.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "printopt" in result.stdout


def test_cli_no_args():
    result = subprocess.run(
        [sys.executable, "-m", "printopt.cli"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
```

**Step 8: Run tests**

```bash
pytest tests/test_cli.py -v
```

Expected: 2 passed.

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding — pyproject.toml, CLI skeleton, initial tests"
```

---

## Phase 1: Moonraker Client

### Task 2: Moonraker websocket client — connection and query

**Files:**
- Create: `src/printopt/core/moonraker.py`
- Create: `tests/core/test_moonraker.py`

**Step 1: Write failing tests for connection and query**

```python
# tests/core/test_moonraker.py
"""Tests for Moonraker websocket client."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from printopt.core.moonraker import MoonrakerClient


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.recv = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestMoonrakerClient:
    def test_init(self):
        client = MoonrakerClient("192.168.0.248")
        assert client.host == "192.168.0.248"
        assert client.port == 7125
        assert not client.connected

    @pytest.mark.asyncio
    async def test_query_server_info(self, mock_ws):
        client = MoonrakerClient("192.168.0.248")
        client._ws = mock_ws
        client._connected = True
        client._request_id = 0

        response = {"jsonrpc": "2.0", "result": {"klippy_state": "ready"}, "id": 1}
        mock_ws.recv.return_value = json.dumps(response)

        result = await client.query("server.info")
        assert result["klippy_state"] == "ready"
        mock_ws.send.assert_called_once()
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["method"] == "server.info"

    @pytest.mark.asyncio
    async def test_inject_gcode(self, mock_ws):
        client = MoonrakerClient("192.168.0.248")
        client._ws = mock_ws
        client._connected = True
        client._request_id = 0

        response = {"jsonrpc": "2.0", "result": "ok", "id": 1}
        mock_ws.recv.return_value = json.dumps(response)

        result = await client.inject("G28")
        assert result == "ok"
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["method"] == "printer.gcode.script"
        assert sent["params"]["script"] == "G28"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_moonraker.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'printopt.core.moonraker'`

**Step 3: Implement MoonrakerClient**

```python
# src/printopt/core/moonraker.py
"""Async Moonraker websocket client."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import websockets
import websockets.client

logger = logging.getLogger(__name__)


class MoonrakerClient:
    """WebSocket client for Moonraker JSON-RPC API."""

    def __init__(self, host: str, port: int = 7125) -> None:
        self.host = host
        self.port = port
        self._ws: websockets.client.WebSocketClientProtocol | None = None
        self._connected = False
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._subscriptions: dict[str, list[Callable]] = {}
        self._listen_task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/websocket"

    async def connect(self) -> None:
        """Establish websocket connection to Moonraker."""
        self._ws = await websockets.connect(self.url)
        self._connected = True
        self._listen_task = asyncio.create_task(self._listen())

    async def disconnect(self) -> None:
        """Close the websocket connection."""
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws:
            await self._ws.close()

    async def query(self, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": req_id,
        }
        if params:
            request["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        await self._ws.send(json.dumps(request))

        # For tests with mock ws, handle direct recv
        if not self._listen_task or self._listen_task.done():
            raw = await self._ws.recv()
            msg = json.loads(raw)
            if "result" in msg:
                return msg["result"]
            if "error" in msg:
                raise MoonrakerError(msg["error"])

        return await asyncio.wait_for(future, timeout=10.0)

    async def inject(self, gcode: str) -> Any:
        """Send a gcode command to the printer."""
        return await self.query("printer.gcode.script", {"script": gcode})

    async def subscribe(
        self, objects: dict[str, list[str] | None], callback: Callable
    ) -> Any:
        """Subscribe to printer object updates."""
        result = await self.query("printer.objects.subscribe", {"objects": objects})
        for obj_name in objects:
            self._subscriptions.setdefault(obj_name, []).append(callback)
        return result

    async def _listen(self) -> None:
        """Background task: read messages and dispatch responses/notifications."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self._pending:
                    future = self._pending.pop(msg["id"])
                    if "result" in msg:
                        future.set_result(msg["result"])
                    elif "error" in msg:
                        future.set_exception(MoonrakerError(msg["error"]))
                elif "method" in msg and msg["method"] == "notify_status_update":
                    params = msg.get("params", [{}])
                    status = params[0] if params else {}
                    for obj_name, callbacks in self._subscriptions.items():
                        if obj_name in status:
                            for cb in callbacks:
                                cb(obj_name, status[obj_name])
        except websockets.exceptions.ConnectionClosed:
            self._connected = False


class MoonrakerError(Exception):
    """Error returned by Moonraker API."""
    pass
```

**Step 4: Run tests**

```bash
pytest tests/core/test_moonraker.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add src/printopt/core/moonraker.py tests/core/test_moonraker.py
git commit -m "feat: Moonraker websocket client — connect, query, inject, subscribe"
```

---

### Task 3: Printer model — auto-discovery from Moonraker

**Files:**
- Create: `src/printopt/core/printer.py`
- Create: `tests/core/test_printer.py`

**Step 1: Write failing tests**

```python
# tests/core/test_printer.py
"""Tests for printer model auto-discovery."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from printopt.core.printer import PrinterConfig, discover_printer


MOCK_SERVER_INFO = {
    "klippy_state": "ready",
    "klippy_connected": True,
}

MOCK_PRINTER_CONFIG = {
    "config": {
        "stepper_x": {"position_max": "245", "position_min": "-5.5"},
        "stepper_y": {"position_max": "258", "position_min": "-4.5"},
        "stepper_z": {"position_max": "248"},
        "extruder": {"nozzle_diameter": "0.400", "filament_diameter": "1.750"},
        "printer": {"kinematics": "corexy", "max_velocity": "600"},
        "adxl345": {"cs_pin": "gpio13"},
        "input_shaper": {
            "shaper_type_x": "ei",
            "shaper_freq_x": "81.6",
            "shaper_type_y": "ei",
            "shaper_freq_y": "39.8",
        },
        "heater_bed": {"max_temp": "120"},
    }
}


class TestPrinterConfig:
    def test_from_moonraker_data(self):
        config = PrinterConfig.from_moonraker_data(
            MOCK_SERVER_INFO, MOCK_PRINTER_CONFIG
        )
        assert config.kinematics == "corexy"
        assert config.bed_x == 245
        assert config.bed_y == 258
        assert config.bed_z == 248
        assert config.nozzle_diameter == 0.4
        assert config.has_accelerometer is True
        assert config.shaper_x == ("ei", 81.6)
        assert config.shaper_y == ("ei", 39.8)

    def test_save_and_load(self, tmp_path):
        config = PrinterConfig.from_moonraker_data(
            MOCK_SERVER_INFO, MOCK_PRINTER_CONFIG
        )
        path = tmp_path / "printer.json"
        config.save(path)
        loaded = PrinterConfig.load(path)
        assert loaded.kinematics == config.kinematics
        assert loaded.bed_x == config.bed_x
        assert loaded.has_accelerometer == config.has_accelerometer


@pytest.mark.asyncio
async def test_discover_printer():
    mock_client = AsyncMock()
    mock_client.query = AsyncMock(side_effect=[
        MOCK_SERVER_INFO,
        MOCK_PRINTER_CONFIG,
    ])
    mock_client.host = "192.168.0.248"
    config = await discover_printer(mock_client)
    assert config.kinematics == "corexy"
    assert config.bed_x == 245
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_printer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement PrinterConfig**

```python
# src/printopt/core/printer.py
"""Printer configuration model with auto-discovery from Moonraker."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from printopt.core.moonraker import MoonrakerClient


@dataclass
class PrinterConfig:
    """Printer configuration discovered from Moonraker."""

    host: str = ""
    kinematics: str = "corexy"
    bed_x: float = 0
    bed_y: float = 0
    bed_z: float = 0
    nozzle_diameter: float = 0.4
    filament_diameter: float = 1.75
    max_velocity: float = 300
    has_accelerometer: bool = False
    shaper_x: tuple[str, float] = ("", 0.0)
    shaper_y: tuple[str, float] = ("", 0.0)

    @classmethod
    def from_moonraker_data(cls, server_info: dict, printer_config: dict) -> PrinterConfig:
        """Build PrinterConfig from Moonraker API responses."""
        cfg = printer_config.get("config", {})
        bed_x = float(cfg.get("stepper_x", {}).get("position_max", 0))
        bed_y = float(cfg.get("stepper_y", {}).get("position_max", 0))
        bed_z = float(cfg.get("stepper_z", {}).get("position_max", 0))
        ext = cfg.get("extruder", {})
        nozzle = float(ext.get("nozzle_diameter", 0.4))
        filament = float(ext.get("filament_diameter", 1.75))
        printer = cfg.get("printer", {})
        kinematics = printer.get("kinematics", "corexy")
        max_vel = float(printer.get("max_velocity", 300))
        has_accel = "adxl345" in cfg
        shaper = cfg.get("input_shaper", {})
        shaper_x = (
            shaper.get("shaper_type_x", ""),
            float(shaper.get("shaper_freq_x", 0)),
        )
        shaper_y = (
            shaper.get("shaper_type_y", ""),
            float(shaper.get("shaper_freq_y", 0)),
        )
        return cls(
            kinematics=kinematics, bed_x=bed_x, bed_y=bed_y, bed_z=bed_z,
            nozzle_diameter=nozzle, filament_diameter=filament,
            max_velocity=max_vel, has_accelerometer=has_accel,
            shaper_x=shaper_x, shaper_y=shaper_y,
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> PrinterConfig:
        data = json.loads(path.read_text())
        data["shaper_x"] = tuple(data["shaper_x"])
        data["shaper_y"] = tuple(data["shaper_y"])
        return cls(**data)


async def discover_printer(client: MoonrakerClient) -> PrinterConfig:
    """Query Moonraker and build a PrinterConfig."""
    server_info = await client.query("server.info")
    printer_config = await client.query(
        "printer.objects.query",
        {"objects": {"configfile": ["config"]}},
    )
    cfg_data = printer_config.get("status", {}).get("configfile", printer_config)
    config = PrinterConfig.from_moonraker_data(server_info, cfg_data)
    config.host = client.host
    return config
```

**Step 4: Run tests**

```bash
pytest tests/core/test_printer.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add src/printopt/core/printer.py tests/core/test_printer.py
git commit -m "feat: printer config model with auto-discovery from Moonraker"
```

---

## Phase 2: Gcode Parser

### Task 4: Gcode parser — parse moves and detect corners

**Files:**
- Create: `src/printopt/core/gcode.py`
- Create: `tests/core/test_gcode.py`

**Step 1: Write failing tests**

```python
# tests/core/test_gcode.py
"""Tests for gcode parser and feature detection."""

import math
import pytest
from printopt.core.gcode import GcodeParser, Move, Feature, FeatureType


SAMPLE_GCODE = """
G28
M104 S248
G1 Z0.2 F3000
G1 X10 Y10 E0.5 F1500
G1 X50 Y10 E2.0
G1 X50 Y50 E4.0
G1 X10 Y50 E6.0
G1 X10 Y10 E8.0
""".strip()


class TestGcodeParser:
    def test_parse_moves(self):
        parser = GcodeParser()
        result = parser.parse(SAMPLE_GCODE)
        moves = [m for m in result.moves if m.is_extrusion]
        assert len(moves) > 0
        assert moves[0].x == 10
        assert moves[0].y == 10

    def test_detect_corners(self):
        parser = GcodeParser()
        result = parser.parse(SAMPLE_GCODE)
        corners = [f for f in result.features if f.type == FeatureType.CORNER]
        assert len(corners) > 0
        assert any(f.angle >= 80 for f in corners)

    def test_line_time_estimation(self):
        parser = GcodeParser()
        result = parser.parse(SAMPLE_GCODE)
        extrusions = [m for m in result.moves if m.is_extrusion]
        for move in extrusions:
            assert move.estimated_time >= 0

    def test_empty_gcode(self):
        parser = GcodeParser()
        result = parser.parse("")
        assert len(result.moves) == 0
        assert len(result.features) == 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_gcode.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement GcodeParser**

```python
# src/printopt/core/gcode.py
"""Gcode parser with geometric analysis and feature detection."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum, auto


class FeatureType(Enum):
    CORNER = auto()
    BRIDGE = auto()
    OVERHANG = auto()
    THIN_WALL = auto()
    SMALL_PERIMETER = auto()
    LAYER_CHANGE = auto()
    SPEED_CHANGE = auto()


@dataclass
class Move:
    """A single parsed gcode move."""
    line_number: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0
    feedrate: float = 0.0
    is_extrusion: bool = False
    distance: float = 0.0
    direction: float = 0.0
    estimated_time: float = 0.0
    cumulative_time: float = 0.0


@dataclass
class Feature:
    """A detected geometric feature in the gcode."""
    type: FeatureType
    line_number: int
    estimated_time: float = 0.0
    angle: float = 0.0
    length: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    """Complete parsed gcode with moves and detected features."""
    moves: list[Move] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)
    total_time: float = 0.0
    layer_count: int = 0


_GCODE_RE = re.compile(r"([GXYZEFMST])(-?\d+\.?\d*)", re.IGNORECASE)


class GcodeParser:
    """Parse gcode into moves and detect geometric features."""

    def __init__(self, corner_threshold: float = 45.0) -> None:
        self.corner_threshold = corner_threshold

    def parse(self, gcode: str) -> ParseResult:
        result = ParseResult()
        state_x, state_y, state_z, state_e = 0.0, 0.0, 0.0, 0.0
        state_f = 1500.0
        cumulative_time = 0.0
        current_z = 0.0
        layer_count = 0

        for line_num, line in enumerate(gcode.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith(";"):
                continue

            params = {}
            for match in _GCODE_RE.finditer(line):
                params[match.group(1).upper()] = float(match.group(2))

            g_code = params.get("G")
            if g_code not in (0, 1):
                continue

            new_x = params.get("X", state_x)
            new_y = params.get("Y", state_y)
            new_z = params.get("Z", state_z)
            new_e = params.get("E", state_e)
            new_f = params.get("F", state_f)

            dx = new_x - state_x
            dy = new_y - state_y
            dist = math.hypot(dx, dy)
            is_extrusion = new_e > state_e and dist > 0.01
            direction = math.atan2(dy, dx) if dist > 0.01 else 0.0

            speed_mm_s = new_f / 60.0
            move_time = dist / speed_mm_s if speed_mm_s > 0 and dist > 0 else 0.0
            cumulative_time += move_time

            if new_z != current_z and new_z > current_z:
                layer_count += 1
                result.features.append(Feature(
                    type=FeatureType.LAYER_CHANGE,
                    line_number=line_num,
                    estimated_time=cumulative_time,
                    metadata={"z": new_z, "layer": layer_count},
                ))
                current_z = new_z

            move = Move(
                line_number=line_num,
                x=new_x, y=new_y, z=new_z, e=new_e,
                feedrate=new_f, is_extrusion=is_extrusion,
                distance=dist, direction=direction,
                estimated_time=move_time, cumulative_time=cumulative_time,
            )
            result.moves.append(move)
            state_x, state_y, state_z, state_e, state_f = (
                new_x, new_y, new_z, new_e, new_f,
            )

        extrusions = [m for m in result.moves if m.is_extrusion]
        for i in range(1, len(extrusions)):
            prev = extrusions[i - 1]
            curr = extrusions[i]
            angle_diff = abs(math.degrees(curr.direction - prev.direction))
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            if angle_diff >= self.corner_threshold:
                result.features.append(Feature(
                    type=FeatureType.CORNER,
                    line_number=curr.line_number,
                    estimated_time=curr.cumulative_time,
                    angle=angle_diff,
                ))

        result.total_time = cumulative_time
        result.layer_count = layer_count
        return result
```

**Step 4: Run tests**

```bash
pytest tests/core/test_gcode.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/printopt/core/gcode.py tests/core/test_gcode.py
git commit -m "feat: gcode parser with move extraction and corner detection"
```

---

### Task 5: Gcode parser — bridge, thin wall, and small perimeter detection

Extends the parser with additional feature detectors. Same pattern: iterate extrusion moves, apply geometric heuristics, emit Feature objects. Deferred to implementation time — the core architecture is validated by Task 4.

```bash
git commit -m "feat: gcode parser — bridge, thin wall, small perimeter detection"
```

---

## Phase 3: Plugin System + Dashboard Skeleton

### Task 6: Plugin base class and lifecycle

**Files:**
- Create: `src/printopt/core/plugin.py`
- Create: `tests/core/test_plugin.py`

**Step 1: Write failing tests**

```python
# tests/core/test_plugin.py
"""Tests for plugin base class and lifecycle."""

import pytest
from printopt.core.plugin import Plugin, PluginManager


class DummyPlugin(Plugin):
    name = "dummy"
    def __init__(self):
        super().__init__()
        self.started = False
        self.stopped = False
        self.layers = []
    async def on_start(self):
        self.started = True
    async def on_layer(self, layer: int, z: float):
        self.layers.append(layer)
    async def on_stop(self):
        self.stopped = True


class CrashPlugin(Plugin):
    name = "crash"
    async def on_start(self):
        raise RuntimeError("plugin crashed")


class TestPlugin:
    def test_plugin_name(self):
        p = DummyPlugin()
        assert p.name == "dummy"

    @pytest.mark.asyncio
    async def test_lifecycle(self):
        p = DummyPlugin()
        await p.on_start()
        assert p.started
        await p.on_layer(1, 0.2)
        assert p.layers == [1]
        await p.on_stop()
        assert p.stopped


class TestPluginManager:
    @pytest.mark.asyncio
    async def test_register_and_start(self):
        mgr = PluginManager()
        dummy = DummyPlugin()
        mgr.register(dummy)
        assert "dummy" in mgr.plugins
        await mgr.start_all()
        assert dummy.started

    @pytest.mark.asyncio
    async def test_crash_isolation(self):
        mgr = PluginManager()
        crash = CrashPlugin()
        dummy = DummyPlugin()
        mgr.register(crash)
        mgr.register(dummy)
        await mgr.start_all()
        assert dummy.started

    @pytest.mark.asyncio
    async def test_stop_all(self):
        mgr = PluginManager()
        dummy = DummyPlugin()
        mgr.register(dummy)
        await mgr.start_all()
        await mgr.stop_all()
        assert dummy.stopped
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/core/test_plugin.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement Plugin and PluginManager**

```python
# src/printopt/core/plugin.py
"""Plugin base class and lifecycle management."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for printopt plugins."""
    name: str = "unnamed"

    def __init__(self) -> None:
        self.enabled = True
        self._error: Exception | None = None

    async def on_start(self) -> None:
        pass
    async def on_print_start(self, filename: str, gcode: str) -> None:
        pass
    async def on_layer(self, layer: int, z: float) -> None:
        pass
    async def on_status_update(self, status: dict) -> None:
        pass
    async def on_print_end(self) -> None:
        pass
    async def on_stop(self) -> None:
        pass
    def get_dashboard_data(self) -> dict:
        return {}


class PluginManager:
    """Manages plugin lifecycle with crash isolation."""

    def __init__(self) -> None:
        self.plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        self.plugins[plugin.name] = plugin

    async def start_all(self) -> None:
        for name, plugin in self.plugins.items():
            try:
                await plugin.on_start()
                logger.info("Plugin '%s' started", name)
            except Exception as e:
                logger.error("Plugin '%s' failed to start: %s", name, e)
                plugin.enabled = False
                plugin._error = e

    async def stop_all(self) -> None:
        for name, plugin in self.plugins.items():
            try:
                await plugin.on_stop()
            except Exception as e:
                logger.error("Plugin '%s' failed to stop: %s", name, e)

    async def broadcast_status(self, status: dict) -> None:
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    await plugin.on_status_update(status)
                except Exception as e:
                    logger.error("Plugin '%s' error on status: %s", plugin.name, e)

    async def broadcast_layer(self, layer: int, z: float) -> None:
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    await plugin.on_layer(layer, z)
                except Exception as e:
                    logger.error("Plugin '%s' error on layer: %s", plugin.name, e)
```

**Step 4: Run tests**

```bash
pytest tests/core/test_plugin.py -v
```

Expected: 5 passed.

**Step 5: Commit**

```bash
git add src/printopt/core/plugin.py tests/core/test_plugin.py
git commit -m "feat: plugin base class with crash-isolated lifecycle management"
```

---

### Task 7: Dashboard skeleton — FastAPI + live printer status

**Files:**
- Create: `src/printopt/dashboard/server.py`
- Create: `src/printopt/dashboard/templates/index.html`
- Create: `src/printopt/dashboard/static/main.js`
- Create: `src/printopt/dashboard/static/style.css`
- Create: `tests/test_dashboard.py`

**Step 1: Write failing tests**

```python
# tests/test_dashboard.py
"""Tests for dashboard server."""

from fastapi.testclient import TestClient
from printopt.dashboard.server import create_app


def test_dashboard_index():
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "printopt" in response.text.lower()


def test_dashboard_api_status():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "plugins" in data
    assert "printer" in data
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dashboard.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement dashboard server, HTML, JS, CSS**

See design doc Section 6 for layout. FastAPI app with:
- `GET /` — serves index.html
- `GET /api/status` — returns current state JSON
- `WS /ws` — websocket for live browser updates
- Static files mounted at `/static`

Dashboard uses vanilla JS with Canvas for heatmap rendering. DOM updates use `textContent` for text and safe DOM methods for structured content. WebSocket auto-reconnects on disconnect.

**Step 4: Run tests**

```bash
pip install httpx
pytest tests/test_dashboard.py -v
```

Expected: 2 passed.

**Step 5: Commit**

```bash
git add src/printopt/dashboard/ tests/test_dashboard.py
git commit -m "feat: dashboard skeleton — FastAPI server, live status, websocket"
```

---

### Task 8: Materials database

**Files:**
- Create: `src/printopt/core/materials.py`
- Create: `tests/core/test_materials.py`

**Step 1: Write failing test**

```python
# tests/core/test_materials.py
"""Tests for material properties database."""

from printopt.core.materials import MaterialProfile, get_profile, list_profiles


def test_builtin_petg():
    profile = get_profile("petg")
    assert profile.name == "petg"
    assert profile.density > 0
    assert profile.glass_transition > 0


def test_list_profiles():
    profiles = list_profiles()
    assert "pla" in profiles
    assert "petg" in profiles
    assert "abs" in profiles


def test_custom_profile(tmp_path):
    custom = MaterialProfile(
        name="petg-elegoo", density=1.27, specific_heat=1.2,
        thermal_conductivity=0.20, glass_transition=78, cte=60e-6,
    )
    path = tmp_path / "petg-elegoo.json"
    custom.save(path)
    loaded = MaterialProfile.load(path)
    assert loaded.name == "petg-elegoo"
    assert loaded.density == 1.27
```

**Step 2: Implement**

```python
# src/printopt/core/materials.py
"""Filament material properties database."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class MaterialProfile:
    name: str
    density: float              # g/cm3
    specific_heat: float        # J/(g*K)
    thermal_conductivity: float # W/(m*K)
    glass_transition: float     # C
    cte: float = 0.0            # m/(m*K)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> MaterialProfile:
        return cls(**json.loads(path.read_text()))


_BUILTINS: dict[str, MaterialProfile] = {
    "pla": MaterialProfile("pla", 1.24, 1.8, 0.13, 60, 68e-6),
    "petg": MaterialProfile("petg", 1.27, 1.2, 0.20, 78, 60e-6),
    "abs": MaterialProfile("abs", 1.04, 1.4, 0.17, 105, 90e-6),
    "asa": MaterialProfile("asa", 1.07, 1.3, 0.18, 100, 95e-6),
    "tpu": MaterialProfile("tpu", 1.21, 1.5, 0.19, 55, 150e-6),
}


def get_profile(name: str) -> MaterialProfile:
    key = name.lower()
    if key in _BUILTINS:
        return _BUILTINS[key]
    raise KeyError(f"Unknown material profile: {name}")


def list_profiles() -> list[str]:
    return list(_BUILTINS.keys())
```

**Step 3: Run tests**

```bash
pytest tests/core/test_materials.py -v
```

Expected: 3 passed.

**Step 4: Commit**

```bash
git add src/printopt/core/materials.py tests/core/test_materials.py
git commit -m "feat: material properties database with PLA/PETG/ABS/ASA/TPU defaults"
```

---

### Task 9: Wire CLI connect command

**Files:**
- Modify: `src/printopt/cli.py`
- Create: `tests/test_connect.py`

Wires `printopt connect <host>` to query Moonraker, discover printer config, save locally. TDD: test with mocked Moonraker client, verify config file created.

```bash
git commit -m "feat: wire CLI connect — auto-discover and cache printer config"
```

---

### Task 10: Wire CLI run command with plugin manager + dashboard

**Files:**
- Modify: `src/printopt/cli.py`
- Modify: `src/printopt/dashboard/server.py`

Wires `printopt run` to: load cached config, connect Moonraker, init PluginManager, start dashboard, subscribe to printer status, broadcast to plugins + browser.

```bash
git commit -m "feat: wire CLI run — plugin manager + dashboard integration"
```

---

## End of Phases 0-3

After these 10 tasks, the core infrastructure is complete:
- Moonraker websocket client (connect, query, inject, subscribe)
- Printer auto-discovery and config caching
- Gcode parser with corner detection (extensible for bridges, thin walls)
- Plugin system with crash isolation
- Web dashboard with live printer status
- CLI with connect and run commands
- Materials database

**Next:** Plan Phases 4-9 (vibration, flow, thermal plugins) once the core is validated against the real printer.
