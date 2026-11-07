"""Minimal iOS shell: one button that runs the smoke test and shows timings.

Results are also printed with the prefix KYORO_POC so they show up in the
`briefcase run` log.
"""
import time
import traceback
from pathlib import Path

_T_IMPORT = time.perf_counter()

import toga
from toga.style.pack import COLUMN, Pack

from kyoro_poc import smoke


class KyoroPoc(toga.App):
    def startup(self):
        self.output = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))
        button = toga.Button("Test starten", on_press=self.run_test, style=Pack(margin=8))
        box = toga.Box(children=[button, self.output], style=Pack(direction=COLUMN))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = box
        self.main_window.show()
        ready = (time.perf_counter() - _T_IMPORT) * 1000
        self._report(f"UI bereit nach {ready:.0f} ms ab App-Modul")

    def _report(self, line):
        print(f"KYORO_POC {line}", flush=True)
        self.output.value = (self.output.value + "\n" + line).strip()

    def run_test(self, widget):
        scripts = Path(__file__).resolve().parent.parent / "kyoro_scripts"
        work = Path(self.paths.data) / "poc_run_{}".format(int(time.time()))
        try:
            total = 0.0
            for name, secs, detail in smoke.run(scripts, work):
                total += secs
                self._report(f"{name}: {secs * 1000:.0f} ms ({detail[:60]})")
            self._report(f"Gesamt: {total * 1000:.0f} ms")
        except BaseException:
            self._report("FEHLER\n" + traceback.format_exc())


def main():
    return KyoroPoc()
