import subprocess
import attr

from .common import Driver
from ..factory import target_factory
from ..step import step


def _connect_callback(element, pad, target):
    pad.link(target)


@target_factory.reg_driver
@attr.s(eq=False)
class USBAudioInputDriver(Driver):
    """
    This driver provides access to a USB audio input device using ALSA and gstreamer.

    When using this driver in a Python venv, you may need to allow access to
    the gi (GObject Introspection) module from the system. This can be done by
    crating a symlink:
    ln -s /usr/lib/python3/dist-packages/gi $VENV/lib/python*/site-packages/
    """
    bindings = {
        "res": {"USBAudioInput", "NetworkUSBAudioInput"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._prepared = False

    def _get_pipeline(self):
        return [
            "alsasrc", f"device={self.res.alsa_name}", "!",
            "matroskamux", "streamable=true", "!",
            "fdsink"
        ]

    def _prepare(self):
        if self._prepared:
            return

        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GLib', '2.0')
        gi.require_version('GObject', '2.0')
        from gi.repository import GLib, GObject, Gst

        self._GLib = GLib
        self._GObject = GObject
        self._Gst = Gst

        Gst.init(None)

        class USBAudioInputBin(Gst.Bin):
            def __init__(self, *, sender, logger):
                super(Gst.Bin, self).__init__()
                self._sender = sender
                self._logger = logger

                assert sender.poll() is None, "sender must be running"
                src = Gst.ElementFactory.make('fdsrc')
                src.set_property('fd', sender.stdout.fileno())
                demux = Gst.ElementFactory.make('matroskademux')
                convert = Gst.ElementFactory.make('audioconvert')

                self.add(src, demux, convert)

                src.link(demux)

                demux.connect("pad-added", _connect_callback, convert.get_static_pad("sink"))

                self.add_pad(Gst.GhostPad.new("src", convert.srcpads[0]))

            def __del__(self):
                self._logger.debug("stopping sender")
                self._sender.terminate()
                try:
                    self._sender.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass

                self._sender.kill()
                del self._sender

        self._USBAudioInputBin = USBAudioInputBin

    @Driver.check_active
    @step()
    def start_sender(self):
        """Return a subprocess which provides audio data in a matroska container on stdout"""
        tx_cmd = self.res.command_prefix + ["gst-launch-1.0", "-q"]
        tx_cmd += self._get_pipeline()

        tx = subprocess.Popen(
            tx_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )

        return tx

    @Driver.check_active
    @step()
    def create_gst_src(self):
        """Returns a newly create gstreamer bin with a single audio output pad."""
        self._prepare()

        tx = self.start_sender()
        return self._USBAudioInputBin(sender=tx, logger=self.logger)

    @Driver.check_active
    @step(result=True)
    def measure_level(self):
        """Returns the current peak and rms value (measured with the gst level element)"""
        self._prepare()
        Gst = self._Gst
        GLib = self._GLib

        src = self.create_gst_src()

        pipe = Gst.Pipeline.new('dynamic')
        level = Gst.ElementFactory.make('level')
        sink = Gst.ElementFactory.make('fakesink')

        pipe.add(src, level, sink)

        src.link(level)
        level.link(sink)

        loop = GLib.MainLoop()

        stats = {}

        def bus_call(bus, message, loop):
            t = message.type
            if t == Gst.MessageType.EOS:
                self.logger.info("End-of-stream")
                loop.quit()
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                self.logger.error("Error: %s: %s", err, debug)
                loop.quit()
            elif t == Gst.MessageType.ELEMENT:
                self.logger.debug('peak %s', message.get_structure()['peak'])
                self.logger.debug('rms %s', message.get_structure()['rms'])
                stats.update(dict(message.get_structure()))
                loop.quit()
            else:
                self.logger.debug('gst message %s', t)
            return True
        bus = pipe.get_bus()
        bus.add_signal_watch()
        bus.connect("message", bus_call, loop)

        def timeout(*args):
            self.logger.error("loop timed out")
            stats['timeout'] = True
            loop.quit()
        GLib.timeout_add_seconds(15, timeout, None)

        # start play back and listen to events
        pipe.set_state(Gst.State.PLAYING)
        try:
            loop.run()
        finally:
            pipe.set_state(Gst.State.NULL)

        if stats.get('timeout'):
            raise TimeoutError("no data received before timeout")
        return stats

    @Driver.check_active
    @step()
    def play(self):
        """Plays the captured audio via gstreamer's autoaudiosink"""
        tx = self.start_sender()

        rx_cmd = ["gst-launch-1.0"]
        rx_cmd += "fdsrc ! matroskademux ! audioconvert ! autoaudiosink".split()
        rx = subprocess.Popen(
            rx_cmd,
            stdin=tx.stdout,
            stdout=subprocess.DEVNULL,
        )

        # wait until one subprocess has termianted
        while True:
            try:
                tx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
            try:
                rx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass

        rx.terminate()
        tx.terminate()

        rx.communicate()
        tx.communicate()

        return tx.returncode or rx.returncode
