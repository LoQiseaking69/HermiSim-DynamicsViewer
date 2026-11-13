"""Bridge between HermiSim and the TulpaLang toolchain.

* :mod:`toolchain`     — locate / invoke the ``tulpa`` binary and its standard library
* :mod:`cosim_server`  — JSON-lines co-simulation server (``cosim::`` in Tulpa) over MuJoCo
* :mod:`runner`        — run a Tulpa program against a model, headless or from the IDE
* :mod:`telemetry`     — parse ``@@tlm`` telemetry lines emitted by ``tlm::``
* :mod:`lsp_client`    — minimal Language Server Protocol client for ``tulpa lsp``
"""


# Select MuJoCo's GL backend before anything imports mujoco.
from physics_engine import gl_backend as _gl  # noqa: E402

_gl.configure()
