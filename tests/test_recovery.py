"""Execute the documented restore procedure with harmless command substitutes."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


class RecoveryProcedure(unittest.TestCase):
    def test_failures_stop_before_data_moves_or_service_restart(self):
        guide = (Path(__file__).resolve().parents[1] / 'docs/RECOVERY.md').read_text()
        procedure = next(block for block in re.findall(r'```sh\n(.*?)```', guide, re.S)
                         if 'restore_stamp=' in block).replace('sudo bash', 'bash', 1)
        for failure in ('gzip', 'listing', 'extract', ''):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                log = root / 'commands'
                environment = root / 'environment.sh'
                environment.write_text('''
record() { printf '%s\\n' "$*" >> "$RECOVERY_LOG"; }
gzip() { record verified; test "$RECOVERY_FAILURE" != gzip; }
tar() {
  if [[ "$1" == -t* ]]; then record listed; test "$RECOVERY_FAILURE" != listing;
  else record extracted; test "$RECOVERY_FAILURE" != extract; fi
}
systemctl() { record "$1"; }
mv() { record moved; }
chown() { :; }
chmod() { :; }
''')
                result = subprocess.run(['bash'], input=procedure, text=True, capture_output=True,
                    env=os.environ | {'BASH_ENV': str(environment), 'RECOVERY_LOG': str(log), 'RECOVERY_FAILURE': failure})
                commands = log.read_text().splitlines()
                self.assertEqual(result.returncode == 0, failure == '')
                if failure in ('gzip', 'listing'):
                    self.assertNotIn('moved', commands)
                    self.assertNotIn('stop', commands)
                self.assertEqual('start' in commands, failure == '')
