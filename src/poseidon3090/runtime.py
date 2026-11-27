"""Miner runtime: stratum client + fee slicer + telemetry in one host loop.

This wires the framework cores together into a runnable miner:

- ``stratum.py`` — message build/parse, Job, ShareTracker, PoolSet failover
- ``fee.py``     — the disclosed 2% time-sliced dev fee (fee rounds are
  announced in the event log when they start and end, per fee.py's contract)
- ``stats.py``   — FleetStats telemetry snapshot for the local API
- ``gpu.py``     — the GPU backend. On this build the backend is the honest
  stub: it raises :class:`gpu.GpuUnavailable`, and the runtime surfaces that
  instead of pretending to mine. A real backend only has to provide the
  ``mine_once(job) -> Share | None`` method used here.

The loop is transport- and clock-injected so the whole job -> work -> share
flow — including the fee switch — is testable end to end against a local
fake-pool fixture with no GPU and no network (see tests/test_runtime.py).

Honesty notes: the stratum submit parameter layout below follows the
conventions in stratum.py and is verified only against the local fixture.
Pool-exact Pearl wire details are board task SOL-1 (Sol's verification) and
no hashrate is claimed anywhere in this module — telemetry reports only
what the backend itself reports.
"""
from __future__ import annotations

import select
import socket
import time
from dataclasses import dataclass, field

from . import fee, gpu, stratum
from .stats import FleetStats, GpuStats

AGENT = "poseidon-3090/0.0.1"


class TransportError(RuntimeError):
    pass


class SocketTransport:
    """Newline-delimited JSON over a connected socket.

    Works over any connected socket object (TCP to a pool, or a
    socketpair in tests). Incoming bytes are buffered and split on
    newlines; ``poll()`` returns every complete message available right
    now without blocking.
    """

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = b""

    @classmethod
    def connect(cls, pool: str, timeout: float = 10.0) -> "SocketTransport":
        host, _, port = pool.rpartition(":")
        if not host or not port:
            raise TransportError(f"pool address must be host:port, got {pool!r}")
        return cls(socket.create_connection((host, int(port)), timeout=timeout))

    def send_line(self, line: str) -> None:
        try:
            self._sock.sendall(line.encode())
        except OSError as exc:
            raise TransportError(str(exc)) from exc

    def poll(self) -> list[str]:
        """Drain all complete lines currently available (non-blocking).

        Lines already sitting in the internal buffer (e.g. a notify that
        arrived in the same chunk as the handshake replies and was left
        behind by wait_line) are returned first — they must not wait for
        the next chunk from the pool.
        """
        lines: list[str] = []
        while True:
            while b"\n" in self._buf:
                raw, self._buf = self._buf.split(b"\n", 1)
                if raw.strip():
                    lines.append(raw.decode())
            ready, _, _ = select.select([self._sock], [], [], 0)
            if not ready:
                break
            try:
                chunk = self._sock.recv(65536)
            except OSError as exc:
                raise TransportError(str(exc)) from exc
            if not chunk:
                raise TransportError("pool closed the connection")
            self._buf += chunk
        return lines

    def wait_line(self, timeout: float = 10.0) -> str:
        """Block until one complete line arrives (handshake use)."""
        deadline = time.monotonic() + timeout
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("timed out waiting for pool response")
            ready, _, _ = select.select([self._sock], [], [], remaining)
            if not ready:
                raise TransportError("timed out waiting for pool response")
            chunk = self._sock.recv(65536)
            if not chunk:
                raise TransportError("pool closed the connection")
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\n", 1)
        return raw.decode()

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


@dataclass
class Share:
    """One share found by the backend for the current job."""
    job_id: str
    nonce: str
    result: str


@dataclass
class MinerConfig:
    pools: list[str]
    wallet: str
    worker: str = "poseidon"
    # Dev-fee connection: defaults to the user's own pool endpoint with the
    # fee wallet (the standard time-sliced switch); set dev_pool only if the
    # dev fee is ever collected through a different endpoint.
    dev_pool: str | None = None
    first_round_delay: float = 30 * 60  # mirrors fee.is_fee_time default

    def __post_init__(self):
        if not self.pools:
            raise ValueError("at least one pool is required")
        stratum.validate_prl_wallet(self.wallet)


@dataclass
class Miner:
    """One runnable host loop. ``step()`` is one iteration; ``run()`` loops
    it. All time comes from ``time_fn`` so tests control the fee clock."""

    config: MinerConfig
    backend: object  # provides mine_once(job) -> Share | None
    transport_factory: object = SocketTransport.connect  # pool -> transport
    time_fn: object = time.monotonic
    events: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.pool_set = stratum.PoolSet(list(self.config.pools))
        self.tracker = stratum.ShareTracker()
        self.transport: SocketTransport | None = None
        self.job: stratum.Job | None = None
        self.difficulty: float = 1.0
        self.fee_active = False
        self.user_seconds = 0.0
        self.fee_seconds = 0.0
        self._req_id = 0
        self._pending: dict[int, str] = {}  # submit request id -> job_id
        self._started_at: float | None = None
        self._last_tick: float | None = None
        self._connect(self._active_pool(), self._active_wallet())

    # -- connection management -------------------------------------------

    def _active_pool(self) -> str:
        if self.fee_active and self.config.dev_pool:
            return self.config.dev_pool
        return self.pool_set.current()

    def _active_wallet(self) -> str:
        return fee.FEE_WALLET if self.fee_active else self.config.wallet

    def _username(self) -> str:
        return f"{self._active_wallet()}.{self.config.worker}"

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _connect(self, pool: str, wallet: str) -> None:
        if self.transport is not None:
            self.transport.close()
        self.transport = self.transport_factory(pool)
        sub_id = self._next_id()
        self.transport.send_line(stratum.build_request(
            sub_id, "mining.subscribe", [AGENT]))
        auth_id = self._next_id()
        self.transport.send_line(stratum.build_request(
            auth_id, "mining.authorize", [f"{wallet}.{self.config.worker}", "x"]))
        answered = set()
        while answered != {sub_id, auth_id}:
            msg = stratum.parse_message(self.transport.wait_line())
            if msg.get("id") in (sub_id, auth_id):
                if msg.get("error"):
                    raise TransportError(f"pool rejected handshake: {msg['error']}")
                answered.add(msg["id"])
            else:
                self._handle_message(msg)
        self.events.append(f"connected to {pool} as {wallet}.{self.config.worker}")

    def _reconnect(self) -> None:
        self._connect(self._active_pool(), self._active_wallet())

    def _failover(self) -> None:
        pool = self.pool_set.failover()
        self.events.append(f"pool unreachable — failing over to {pool}")
        self._connect(pool, self._active_wallet())

    # -- pool messages -----------------------------------------------------

    def _handle_message(self, msg: dict) -> None:
        method = msg.get("method")
        if method == "mining.notify":
            self.job = stratum.Job.from_notify(msg.get("params") or [],
                                               difficulty=self.difficulty)
            self.tracker.on_new_job(self.job.job_id)
        elif method == "mining.set_difficulty":
            params = msg.get("params") or []
            if params:
                self.difficulty = float(params[0])
        elif method is None and msg.get("id") in self._pending:
            job_id = self._pending.pop(msg["id"])
            accepted = bool(msg.get("result")) and not msg.get("error")
            outcome = self.tracker.record_submit(job_id, accepted)
            self.events.append(f"share for job {job_id}: {outcome}")

    def _drain(self) -> None:
        for line in self.transport.poll():
            self._handle_message(stratum.parse_message(line))

    # -- fee switching -----------------------------------------------------

    def _account_time(self, now: float) -> None:
        if self._started_at is None:
            self._started_at = now
            self._last_tick = now
            return
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        elapsed = now - self._started_at
        in_fee = fee.is_fee_time(elapsed, self.config.first_round_delay)
        if in_fee:
            self.fee_seconds += dt
        else:
            self.user_seconds += dt
        if in_fee != self.fee_active:
            self.fee_active = in_fee
            if in_fee:
                self.events.append(
                    "dev fee round started: mining to the Poseidon 3090 "
                    "fee wallet (disclosed 2%, time-sliced)")
            else:
                self.events.append("dev fee round ended: back to user wallet")
            # The wallet (and pool, if a separate dev pool is configured)
            # changes with the round — reconnect so the pool sees the
            # switch, exactly like the incumbent miners do.
            self._reconnect()

    # -- main loop -----------------------------------------------------------

    def step(self) -> None:
        now = self.time_fn()
        try:
            self._drain()
            self._account_time(now)
            if self.job is None:
                return
            share = self.backend.mine_once(self.job)
            if share is None:
                return
            req_id = self._next_id()
            self._pending[req_id] = share.job_id
            self.transport.send_line(stratum.build_request(
                req_id, "mining.submit",
                [self._username(), share.job_id, share.nonce, share.result]))
        except TransportError:
            self._failover()

    def run(self, steps: int | None = None, poll_interval: float = 0.1) -> None:
        """Run the loop. Bounded by ``steps`` when given (tests, one-shot
        checks); otherwise runs until interrupted."""
        done = 0
        while steps is None or done < steps:
            self.step()
            done += 1
            if steps is None:
                time.sleep(poll_interval)

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    # -- telemetry -----------------------------------------------------------

    def stats(self) -> FleetStats:
        gpu_stats = GpuStats(
            name=getattr(self.backend, "device_name", "RTX 3090"),
            ths=float(getattr(self.backend, "last_ths", 0.0)),
            power_w=float(getattr(self.backend, "last_power_w", 0.0)),
            accepted=self.tracker.accepted,
            rejected=self.tracker.rejected,
            stale=self.tracker.stale)
        uptime = 0.0
        if self._started_at is not None:
            uptime = max(0.0, self.time_fn() - self._started_at)
        return FleetStats(gpus=[gpu_stats], uptime_s=uptime,
                          fee_active=self.fee_active)

    @property
    def observed_fee_fraction(self) -> float:
        return fee.effective_fee_fraction(self.user_seconds, self.fee_seconds)


class StubBackend:
    """The backend this build ships with: gpu.py's honest stub. mine_once
    raises GpuUnavailable — the runtime must surface that, never fake it."""

    device_name = "RTX 3090"

    def mine_once(self, job):
        return gpu.mine_once(job)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="poseidon-miner",
        description="Poseidon 3090 — Pearl-only miner for the RTX 3090. "
                    "Dev fee: disclosed 2%, time-sliced, to the Poseidon "
                    "3090 fee wallet.")
    parser.add_argument("--pool", action="append", required=True,
                        help="pool host:port (repeat for failover)")
    parser.add_argument("--wallet", required=True, help="your prl1... wallet")
    parser.add_argument("--worker", default="poseidon")
    parser.add_argument("--dev-pool", default=None)
    args = parser.parse_args(argv)

    config = MinerConfig(pools=args.pool, wallet=args.wallet,
                         worker=args.worker, dev_pool=args.dev_pool)
    miner = Miner(config=config, backend=StubBackend())
    try:
        miner.run()
    except gpu.GpuUnavailable as exc:
        print(f"poseidon-3090: {exc}")
        print("The CUDA kernel backend is not built in this build yet — "
              "see cuda/README.md. No hashrate is claimed until a "
              "docs/BENCH.md run on a real 3090 is published.")
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        miner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
