import sys, os, unittest, json, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from poseidon3090 import runtime, fee, gpu

USER_WALLET = "prl1ptestuserwallet00000000000000000000000"
POOL_A = "pool-a.example:4410"
POOL_B = "pool-b.example:4410"


class FakeTransport:
    """In-memory stratum transport: auto-answers every request with a
    success result (queued for poll/wait_line), records everything sent."""

    def __init__(self, pool):
        self.pool = pool
        self.sent = []          # parsed request dicts, in order
        self.incoming = []      # raw lines waiting for poll()/wait_line()
        self.closed = False
        self.fail_poll = False

    # transport interface used by runtime.Miner
    def send_line(self, line):
        msg = json.loads(line)
        self.sent.append(msg)
        self.incoming.append(json.dumps({"id": msg["id"], "result": True}))

    def poll(self):
        if self.fail_poll:
            raise runtime.TransportError("simulated pool drop")
        lines, self.incoming = self.incoming, []
        return lines

    def wait_line(self, timeout=10.0):
        if not self.incoming:
            raise runtime.TransportError("no scripted response")
        return self.incoming.pop(0)

    def close(self):
        self.closed = True

    # test helper
    def inject(self, msg):
        self.incoming.append(json.dumps(msg))

    def requests(self, method):
        return [m for m in self.sent if m.get("method") == method]


class FakeFactory:
    def __init__(self):
        self.transports = []

    def __call__(self, pool):
        t = FakeTransport(pool)
        self.transports.append(t)
        return t


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ShareBackend:
    """Returns one share per job, then None."""
    device_name = "RTX 3090 (fake)"
    last_ths = 0.0
    last_power_w = 0.0

    def __init__(self):
        self._served = set()

    def mine_once(self, job):
        if job.job_id in self._served:
            return None
        self._served.add(job.job_id)
        return runtime.Share(job_id=job.job_id, nonce="00000001",
                             result="ff" * 32)


class NullBackend:
    device_name = "RTX 3090 (fake)"

    def mine_once(self, job):
        return None


def make_miner(backend=None, pools=(POOL_A,), clock=None, **cfg_kw):
    factory = FakeFactory()
    clock = clock or Clock()
    cfg = runtime.MinerConfig(pools=list(pools), wallet=USER_WALLET, **cfg_kw)
    miner = runtime.Miner(config=cfg, backend=backend or ShareBackend(),
                          transport_factory=factory, time_fn=clock)
    return miner, factory, clock


def notify(transport, job_id="job-1"):
    transport.inject({"id": None, "method": "mining.notify",
                      "params": [job_id, "deadbeefcafe", "a", "b", True]})


class TestHandshake(unittest.TestCase):
    def test_subscribe_and_authorize_with_user_wallet(self):
        miner, factory, _ = make_miner()
        t = factory.transports[0]
        self.assertEqual(t.pool, POOL_A)
        methods = [m["method"] for m in t.sent]
        self.assertEqual(methods, ["mining.subscribe", "mining.authorize"])
        auth = t.requests("mining.authorize")[0]
        self.assertEqual(auth["params"][0], f"{USER_WALLET}.poseidon")
        self.assertTrue(any("connected to" in e for e in miner.events))

    def test_config_rejects_bad_wallet_and_empty_pools(self):
        with self.assertRaises(ValueError):
            runtime.MinerConfig(pools=[POOL_A], wallet="bc1qnotapearl")
        with self.assertRaises(ValueError):
            runtime.MinerConfig(pools=[], wallet=USER_WALLET)


class TestJobShareFlow(unittest.TestCase):
    def test_job_to_share_to_accepted(self):
        miner, factory, _ = make_miner()
        t = factory.transports[0]
        notify(t)
        miner.step()  # drain notify -> job; backend share -> submit sent
        self.assertIsNotNone(miner.job)
        self.assertEqual(miner.job.job_id, "job-1")
        submits = t.requests("mining.submit")
        self.assertEqual(len(submits), 1)
        self.assertEqual(submits[0]["params"][0], f"{USER_WALLET}.poseidon")
        self.assertEqual(submits[0]["params"][1], "job-1")
        miner.step()  # drain the submit result -> accepted
        self.assertEqual(miner.tracker.accepted, 1)
        self.assertEqual(miner.tracker.rejected, 0)
        st = miner.stats()
        self.assertEqual(st.gpus[0].accepted, 1)
        self.assertFalse(st.fee_active)

    def test_no_job_no_submit(self):
        miner, factory, _ = make_miner()
        miner.step()
        self.assertEqual(factory.transports[0].requests("mining.submit"), [])


class TestFeeSwitch(unittest.TestCase):
    def test_fee_round_reconnects_with_fee_wallet_and_back(self):
        clock = Clock()
        miner, factory, _ = make_miner(backend=NullBackend(), clock=clock,
                                       first_round_delay=0)
        miner.step()  # t=0: clock starts, no fee
        self.assertFalse(miner.fee_active)
        # Advance in 60 s ticks, like the real loop's frequent polling:
        # tick-based time accounting credits each interval to the state
        # at its end, so a single 5940 s jump would miscredit the window.
        for t in range(60, 6000 - 120, 60):
            clock.now = float(t)
            miner.step()
            self.assertFalse(miner.fee_active)
        clock.now = 6000 - 60  # inside the 120 s fee window of cycle 1
        miner.step()
        self.assertTrue(miner.fee_active)
        self.assertEqual(len(factory.transports), 2)
        fee_auth = factory.transports[1].requests("mining.authorize")[0]
        self.assertEqual(fee_auth["params"][0], f"{fee.FEE_WALLET}.poseidon")
        self.assertTrue(any("dev fee round started" in e
                            for e in miner.events))
        self.assertGreater(miner.fee_seconds, 0)
        clock.now = 6000 + 60  # past the fee window
        miner.step()
        self.assertFalse(miner.fee_active)
        self.assertEqual(len(factory.transports), 3)
        back_auth = factory.transports[2].requests("mining.authorize")[0]
        self.assertEqual(back_auth["params"][0], f"{USER_WALLET}.poseidon")
        self.assertTrue(any("dev fee round ended" in e
                            for e in miner.events))
        # Observed fee share of accounted time stays near the disclosed 2%
        # for the window pattern used here (60 s fee of 6120 s elapsed).
        self.assertLess(miner.observed_fee_fraction, 0.02)

    def test_no_fee_before_first_round_delay(self):
        clock = Clock()
        miner, factory, _ = make_miner(backend=NullBackend(), clock=clock)
        miner.step()
        clock.now = 6000 - 60  # in a fee window, but default delay is 30 min
        # elapsed is measured from start (t=0), so this IS past the delay;
        # use a fresh miner whose start is inside the window instead:
        miner2, factory2, _ = make_miner(backend=NullBackend(), clock=clock)
        miner2.step()  # starts at t=5940, elapsed 0 < delay
        self.assertFalse(miner2.fee_active)
        self.assertEqual(len(factory2.transports), 1)


class TestFailoverAndStub(unittest.TestCase):
    def test_transport_error_fails_over_to_next_pool(self):
        miner, factory, _ = make_miner(pools=(POOL_A, POOL_B))
        factory.transports[0].fail_poll = True
        miner.step()
        self.assertEqual(len(factory.transports), 2)
        self.assertEqual(factory.transports[1].pool, POOL_B)
        self.assertTrue(any("failing over" in e for e in miner.events))

    def test_stub_backend_surfaces_gpu_unavailable(self):
        miner, factory, _ = make_miner(backend=runtime.StubBackend())
        notify(factory.transports[0])
        with self.assertRaises(gpu.GpuUnavailable):
            miner.step()


class TestSocketTransport(unittest.TestCase):
    def test_socketpair_roundtrip_and_poll(self):
        a, b = socket.socketpair()
        try:
            ta = runtime.SocketTransport(a)
            b.sendall(b'{"id": 1, "result": true}\n{"id": 2}\n')
            self.assertEqual(ta.wait_line(), '{"id": 1, "result": true}')
            self.assertEqual(ta.poll(), ['{"id": 2}'])
            ta.send_line('{"id": 3}\n')
            self.assertEqual(b.recv(64), b'{"id": 3}\n')
        finally:
            a.close()
            b.close()

    def test_connect_rejects_bad_pool_address(self):
        with self.assertRaises(runtime.TransportError):
            runtime.SocketTransport.connect("no-port-here")


if __name__ == "__main__":
    unittest.main()
