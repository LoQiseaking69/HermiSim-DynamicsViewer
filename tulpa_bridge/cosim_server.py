"""Co-simulation server: lets a Tulpa program drive a MuJoCo model in lock-step.

Protocol (one JSON object per line, UTF-8, over TCP):

    request       {"id": 7, "method": "step", "params": {"ctrl": [...], "substeps": 5}}
    response      {"id": 7, "result": {...}}            or  {"id": 7, "error": "message"}
    notification  {"method": "plot", "params": {...}}   (no id, no response)

Methods: info, reset, observe, step, set_ctrl, set_state, apply_force, plus any method
registered with :meth:`CoSimServer.register`. The Tulpa side is ``cosim::connect()``.
"""

from __future__ import annotations

import json
import logging
import socket
import socketserver
import threading
import time
from typing import Any, Callable, Optional

import mujoco
import numpy as np

logger = logging.getLogger(__name__)

_JNT_TYPES = {0: "free", 1: "ball", 2: "slide", 3: "hinge"}


def _name(model, objtype, i: int, prefix: str) -> str:
    return mujoco.mj_id2name(model, objtype, i) or f"{prefix}{i}"


class CoSimSession:
    """Dispatches RPCs onto a :class:`physics_engine.engine.PhysicsEngine`."""

    def __init__(self, engine, realtime: float = 0.0,
                 on_frame: Optional[Callable[[dict], None]] = None,
                 on_notify: Optional[Callable[[str, dict], None]] = None,
                 frame_interval: float = 1 / 30) -> None:
        self.engine = engine
        self.realtime = realtime          # 0 = as fast as possible, 1 = real time, 2 = 2× ...
        self.on_frame = on_frame
        self.on_notify = on_notify
        self.frame_interval = frame_interval
        self._last_frame = 0.0
        self._wall0: Optional[float] = None
        self._sim0 = 0.0
        self.steps = 0
        self.extra: dict[str, Callable[[dict], Any]] = {}
        self.paused = threading.Event()
        self.paused.set()                 # set = running
        self.disturbances: list[dict] = []

    # ------------------------------------------------------------------ helpers
    @property
    def m(self):
        return self.engine.model

    @property
    def d(self):
        return self.engine.data

    def _info(self) -> dict:
        m = self.m
        O = mujoco.mjtObj
        acts = []
        for i in range(m.nu):
            j = int(m.actuator_trnid[i, 0])
            acts.append({
                "name": _name(m, O.mjOBJ_ACTUATOR, i, "act"),
                "joint": _name(m, O.mjOBJ_JOINT, j, "joint") if j >= 0 else None,
                "ctrlrange": [float(x) for x in m.actuator_ctrlrange[i]],
                "gear": float(m.actuator_gear[i, 0]),
                "qposadr": int(m.jnt_qposadr[j]) if j >= 0 else None,
                "dofadr": int(m.jnt_dofadr[j]) if j >= 0 else None,
            })
        joints = [{
            "name": _name(m, O.mjOBJ_JOINT, j, "joint"),
            "type": _JNT_TYPES.get(int(m.jnt_type[j]), "?"),
            "range": [float(x) for x in m.jnt_range[j]],
            "qposadr": int(m.jnt_qposadr[j]),
            "dofadr": int(m.jnt_dofadr[j]),
        } for j in range(m.njnt)]
        sensors = [{
            "name": _name(m, O.mjOBJ_SENSOR, s, "sensor"),
            "type": int(m.sensor_type[s]),
            "dim": int(m.sensor_dim[s]),
        } for s in range(m.nsensor)]
        keys = [_name(m, O.mjOBJ_KEY, k, "key") for k in range(m.nkey)]
        return {
            "model": mujoco.mj_id2name(m, O.mjOBJ_MODEL, 0) if hasattr(O, "mjOBJ_MODEL") else "",
            "timestep": float(m.opt.timestep),
            "gravity": [float(x) for x in m.opt.gravity],
            "nq": int(m.nq), "nv": int(m.nv), "nu": int(m.nu),
            "total_mass": float(sum(m.body_mass)),
            "actuators": acts, "joints": joints, "sensors": sensors,
            "bodies": [_name(m, O.mjOBJ_BODY, b, "body") for b in range(m.nbody)],
            "keyframes": keys,
        }

    def observe(self) -> dict:
        m, d = self.m, self.d
        O = mujoco.mjtObj
        mujoco.mj_subtreeVel(m, d)
        sensors = {}
        for s in range(m.nsensor):
            a, n = int(m.sensor_adr[s]), int(m.sensor_dim[s])
            sensors[_name(m, O.mjOBJ_SENSOR, s, "sensor")] = [float(x) for x in d.sensordata[a:a + n]]
        # per-body contact forces with the world (normal force + centre of pressure)
        contacts: dict[str, dict] = {}
        f6 = np.zeros(6)
        for c in range(d.ncon):
            con = d.contact[c]
            b1, b2 = int(m.geom_bodyid[con.geom1]), int(m.geom_bodyid[con.geom2])
            if b1 != 0 and b2 != 0:
                continue
            body = b2 if b1 == 0 else b1
            mujoco.mj_contactForce(m, d, c, f6)
            fn = abs(float(f6[0]))
            name = _name(m, O.mjOBJ_BODY, body, "body")
            e = contacts.setdefault(name, {"force": 0.0, "cop": [0.0, 0.0, 0.0], "n": 0})
            e["force"] += fn
            for k in range(3):
                e["cop"][k] += fn * float(con.pos[k])
            e["n"] += 1
        for e in contacts.values():
            if e["force"] > 1e-9:
                e["cop"] = [x / e["force"] for x in e["cop"]]
        root = 1 if m.nbody > 1 else 0
        return {
            "time": float(d.time),
            "qpos": d.qpos.tolist(),
            "qvel": d.qvel.tolist(),
            "ctrl": d.ctrl.tolist(),
            "act_force": d.actuator_force.tolist(),
            "sensors": sensors,
            "com": d.subtree_com[root].tolist(),
            "com_vel": d.subtree_linvel[root].tolist(),
            "root_pos": d.xpos[root].tolist(),
            "root_quat": d.xquat[root].tolist(),
            "bodies": {_name(m, O.mjOBJ_BODY, b, "body"): d.xpos[b].tolist() for b in range(1, m.nbody)},
            "contacts": contacts,
            "energy": [float(d.energy[0]), float(d.energy[1])] if m.opt.enableflags & mujoco.mjtEnableBit.mjENBL_ENERGY else None,
        }

    def _pace(self) -> None:
        if self.realtime <= 0:
            return
        now = time.perf_counter()
        if self._wall0 is None:
            self._wall0, self._sim0 = now, float(self.d.time)
            return
        target = self._wall0 + (float(self.d.time) - self._sim0) / self.realtime
        if target > now:
            time.sleep(min(target - now, 0.25))

    def _maybe_frame(self, force: bool = False) -> None:
        if self.on_frame is None:
            return
        now = time.perf_counter()
        if force or now - self._last_frame >= self.frame_interval:
            self._last_frame = now
            try:
                self.on_frame({"time": float(self.d.time), "steps": self.steps})
            except Exception:  # GUI callbacks must never kill the RPC loop
                logger.debug("frame callback failed", exc_info=True)

    # ------------------------------------------------------------------ dispatch
    def handle(self, method: str, params: Any) -> Any:
        p = params if isinstance(params, dict) else {}
        eng = self.engine
        if method == "info":
            return self._info()
        if method == "reset":
            with eng._lock:
                key = p.get("keyframe")
                if isinstance(key, str):
                    k = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_KEY, key)
                    if k < 0:
                        raise ValueError(f"no keyframe named '{key}'")
                    mujoco.mj_resetDataKeyframe(self.m, self.d, k)
                elif isinstance(key, int):
                    mujoco.mj_resetDataKeyframe(self.m, self.d, key)
                elif self.m.nkey > 0:
                    mujoco.mj_resetDataKeyframe(self.m, self.d, 0)
                else:
                    mujoco.mj_resetData(self.m, self.d)
                self.d.xfrc_applied[:] = 0
                mujoco.mj_forward(self.m, self.d)
                self._wall0 = None
            self._maybe_frame(force=True)
            return self.observe()
        if method == "observe":
            with eng._lock:
                return self.observe()
        if method in ("step", "set_ctrl"):
            ctrl = p.get("ctrl")
            with eng._lock:
                if ctrl is not None:
                    if len(ctrl) != self.m.nu:
                        raise ValueError(f"ctrl has {len(ctrl)} values, model has {self.m.nu} actuators")
                    lo, hi = self.m.actuator_ctrlrange[:, 0], self.m.actuator_ctrlrange[:, 1]
                    c = np.asarray(ctrl, dtype=float)
                    if not np.all(np.isfinite(c)):
                        raise ValueError("ctrl contains NaN/inf")
                    lim = self.m.actuator_ctrllimited.astype(bool)
                    c[lim] = np.clip(c[lim], lo[lim], hi[lim])
                    self.d.ctrl[:] = c
                if method == "set_ctrl":
                    return None
                n = max(1, int(p.get("substeps", 1)))
            for _ in range(n):
                self.paused.wait()
                with eng._lock:
                    self._apply_disturbances()
                    mujoco.mj_step(self.m, self.d)
                self.steps += 1
                self._pace()
            self._maybe_frame()
            with eng._lock:
                return self.observe()
        if method == "set_state":
            with eng._lock:
                if p.get("qpos") is not None:
                    self.d.qpos[:] = p["qpos"]
                if p.get("qvel") is not None:
                    self.d.qvel[:] = p["qvel"]
                mujoco.mj_forward(self.m, self.d)
                return self.observe()
        if method == "apply_force":
            body = p.get("body")
            with eng._lock:
                b = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, body or "")
                if b < 0:
                    raise ValueError(f"no body named '{body}'")
                self.d.xfrc_applied[b, :3] = p.get("force") or [0, 0, 0]
                self.d.xfrc_applied[b, 3:] = p.get("torque") or [0, 0, 0]
            return None
        if method in self.extra:
            return self.extra[method](p)
        raise ValueError(f"unknown method '{method}'")

    def push(self, body: str, force, duration: float) -> None:
        """Schedule an external push (from the GUI) applied for `duration` seconds."""
        self.disturbances.append({"body": body, "force": list(force), "until": None, "duration": duration})

    def _apply_disturbances(self) -> None:
        if not self.disturbances:
            return
        t = float(self.d.time)
        keep = []
        for dist in self.disturbances:
            b = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, dist["body"])
            if b < 0:
                continue
            if dist["until"] is None:
                dist["until"] = t + dist["duration"]
            if t < dist["until"]:
                self.d.xfrc_applied[b, :3] = dist["force"]
                keep.append(dist)
            else:
                self.d.xfrc_applied[b, :3] = 0
        self.disturbances = keep


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:  # noqa: D401
        server: CoSimServer = self.server  # type: ignore[assignment]
        server.client_connected()
        sess = server.session
        try:
            for raw in self.rfile:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._send({"id": None, "error": f"bad JSON: {exc}"})
                    continue
                method = msg.get("method", "")
                params = msg.get("params")
                if "id" not in msg:            # notification
                    if method == "bye":
                        break
                    if sess.on_notify:
                        try:
                            sess.on_notify(method, params or {})
                        except Exception:
                            logger.debug("notify callback failed", exc_info=True)
                    continue
                try:
                    result = sess.handle(method, params)
                    self._send({"id": msg["id"], "result": result})
                except Exception as exc:  # report to the Tulpa program as a runtime error
                    self._send({"id": msg["id"], "error": str(exc)})
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            server.client_disconnected()

    def _send(self, obj: dict) -> None:
        self.wfile.write((json.dumps(obj, separators=(",", ":")) + "\n").encode())
        self.wfile.flush()


class CoSimServer(socketserver.ThreadingTCPServer):
    """TCP server hosting one :class:`CoSimSession`. Bind port 0 for an ephemeral port."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, session: CoSimSession, host: str = "127.0.0.1", port: int = 0) -> None:
        super().__init__((host, port), _Handler)
        self.session = session
        self.clients = 0
        self._thread: Optional[threading.Thread] = None

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()

    @property
    def address(self) -> str:
        host, port = self.server_address[:2]
        return f"{host}:{port}"

    def client_connected(self) -> None:
        self.clients += 1
        logger.info("co-sim client connected (%d active)", self.clients)

    def client_disconnected(self) -> None:
        self.clients -= 1
        logger.info("co-sim client disconnected (%d active)", self.clients)

    def start(self) -> "CoSimServer":
        self._thread = threading.Thread(target=self.serve_forever, name="cosim", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self.session.paused.set()
        self.shutdown()
        self.server_close()
