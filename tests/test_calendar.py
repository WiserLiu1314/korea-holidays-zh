import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('calendar_builder', Path(__file__).resolve().parents[1] / 'scripts/update_calendar.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CalendarTests(unittest.TestCase):
    def test_verified_dates_and_full_calendar(self):
        payload = json.loads((module.ROOT / 'data/source.json').read_text())
        days = module.normalize(payload, 2026)
        self.assertGreaterEqual(len([d for d in days if d.startswith('2026')]), 22)
        self.assertGreaterEqual(len([d for d in days if d.startswith('2027')]), 24)
        self.assertEqual(days['2027-02-07'], ['春节'])
        self.assertEqual(days['2027-05-03'], ['劳动节补假'])
        self.assertEqual(days['2027-07-19'], ['制宪节补假'])
        self.assertEqual(days['2026-06-03'], ['全国地方选举日'])
        self.assertNotIn('2026-04-05', days)

    def test_translation_and_unknown_name(self):
        self.assertEqual(module.translate('대체공휴일(부처님 오신 날)'), '佛诞节补假')
        self.assertEqual(module.translate('임시공휴일(대통령선거)'), '临时公休日（总统选举日）')
        self.assertEqual(module.translate('제22대국회의원선거'), '国会议员选举日')
        with self.assertRaises(ValueError):
            module.translate('알 수 없는 기념일')

    def test_stable_uid_and_no_repeat_changes(self):
        days = {'2026-10-09': ['韩文日'], '2027-01-01': ['元旦']}
        first, state = module.build_calendar(days, {}, '20261007T070000Z')
        second, state2 = module.build_calendar(days, state, '20261008T070000Z')
        self.assertEqual(first, second)
        self.assertEqual(state, state2)
        text = first.decode()
        self.assertIn('DTEND;VALUE=DATE:20261010', text)
        self.assertNotIn('BEGIN:VALARM', text)
        self.assertTrue(all(len(line) <= 75 for line in first.split(b'\r\n')))
        changed, state3 = module.build_calendar({'2026-10-09': ['韩文日', '临时公休日']}, state, '20261009T070000Z')
        self.assertEqual(state3['2026-10-09']['sequence'], 1)
        self.assertIn(b'UID:kr-20261009@korea-holidays-zh', changed)
        self.assertEqual(changed.count(b'BEGIN:VEVENT'), 1)

    def test_year_end_exclusive_date(self):
        output, _ = module.build_calendar({'2026-12-31': ['临时公休日']}, {}, '20261007T070000Z')
        self.assertIn(b'DTEND;VALUE=DATE:20270101', output)

    def test_failure_does_not_overwrite_published_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'docs').mkdir()
            target = root / 'docs/korea-zh.ics'
            target.write_bytes(b'previous-good-calendar')
            with patch.object(module, 'ROOT', root), patch.object(module, 'fetch_source', side_effect=RuntimeError('network failed')):
                with self.assertRaises(RuntimeError):
                    module.update()
            self.assertEqual(target.read_bytes(), b'previous-good-calendar')

    def test_invalid_payload_rejected(self):
        with self.assertRaises(ValueError):
            module.normalize({'2026': {}}, 2026)
        with self.assertRaises(ValueError):
            module.normalize([], 2026)


if __name__ == '__main__':
    unittest.main()
