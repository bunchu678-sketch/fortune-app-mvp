"""Draft generation tests: output only, no scheduler APIs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
import xml.etree.ElementTree as ET
from research.home_backup_task_draft import draft
from research.home_backup_storage import BackupSchedule

SCHEDULE=BackupSchedule.parse('07:00,12:00,17:00,23:00',10)


class TaskDraftCases(unittest.TestCase):
    def test_explicit_jst_draft_escapes_paths_and_contains_restart_controls(self):
        python=str(Path(sys.executable).resolve())
        node=str(Path(sys.executable).parent/'A & B'/'node.exe')
        xml=draft(python,node,'2026-10-28T00:00:00+09:00',schedule=SCHEDULE)
        root=ET.fromstring(xml); ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        for tag,value in [('MultipleInstancesPolicy','IgnoreNew'),('StartWhenAvailable','true'),
                          ('WakeToRun','true'),('ExecutionTimeLimit','PT30M')]:
            self.assertEqual(root.find('.//t:'+tag,ns).text,value)
        self.assertIn('--node "'+node+'"',root.find('.//t:Arguments',ns).text)
        self.assertIn('home_backup_demo.py',root.find('.//t:Arguments',ns).text)
        self.assertEqual(len(root.findall('.//t:BootTrigger',ns)),1)
        boundaries=[element.text for element in root.findall('.//t:CalendarTrigger/t:StartBoundary',ns)]
        self.assertEqual(boundaries,['2026-10-28T'+value+':00+09:00' for value in ('07:10','12:10','17:10','23:10')])

    def test_missing_jst_or_unsafe_argument_refused(self):
        for start in ('2026-10-28T04:15:00','2026-10-28T04:15:00+00:00'):
            with self.assertRaises(ValueError): draft(sys.executable,sys.executable,start,schedule=SCHEDULE)
        for path in ('relative','C:\\bad"path\\python.exe','C:\\bad\npath\\python.exe'):
            with self.assertRaises(ValueError): draft(path,sys.executable,'2026-10-28T04:15:00+09:00',schedule=SCHEDULE)

    def test_changed_configuration_and_midnight_delay_are_reflected(self):
        plan=BackupSchedule.parse('06:00,11:00,16:00,23:55',10)
        root=ET.fromstring(draft(sys.executable,sys.executable,'2026-10-28T00:00:00+09:00',schedule=plan))
        ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        self.assertEqual(root.findall('.//t:CalendarTrigger/t:StartBoundary',ns)[-1].text,'2026-10-29T00:05:00+09:00')


if __name__=='__main__': unittest.main(verbosity=2)
