import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import build_ps4_catalog as b

META = '''Title_ID,Name,Editions
CUSA00001,The Playroom,
CUSA00002,Example German Edition,
CUSA00003,The English Adventure,
CUSA00004,Missing Download Game,
CUSA00005,English and French Game,
'''

SOURCE = '''{
 "DATA": {
  "https://example.org/good-game-[EN].pkg": {"title_id":"CUSA00003","name":"The English Adventure","size":1200,"region":"USA","version":"01.00"},
  "https://example.org/good-mirror.pkg": {"title_id":"CUSA00003","name":"The English Adventure","size":1200,"region":"USA","version":"01.00"},
  "https://example.org/black-ops-(German).pkg": {"title_id":"CUSA00006","name":"Call of Duty Black Ops (German)","size":2000},
  "https://example.org/dual-language.pkg": {"title_id":"CUSA00005","name":"English and French Game (English/French)","size":3000},
  "https://example.org/no-size.pkg": {"title_id":"CUSA00001","name":"The Playroom","size":0}
 }
}'''

class CatalogTests(unittest.TestCase):
    def test_language(self):
        self.assertTrue(b.non_english_edition('Call of Duty (German)'))
        self.assertTrue(b.non_english_edition('Black Ops (Italy/Spain)'))
        self.assertTrue(b.non_english_edition('Black Ops 2 - German'))
        self.assertTrue(b.non_english_edition('Example', 'file-[GER].pkg'))
        self.assertFalse(b.non_english_edition('Game (English/French)'))
        self.assertFalse(b.non_english_edition('Game', 'file-[EU][EN].pkg'))
        self.assertFalse(b.non_english_edition('Game', 'file-[EU].pkg'))
    def test_metadata_only_not_lost(self):
        games, library, excludes, report = b.build(META, [('fixture', SOURCE)], set())
        data = games['DATA']
        self.assertEqual(len(data), 2)
        self.assertTrue(any('good-game' in u for u in data))
        self.assertFalse(any('German' in v['name'] for v in data.values()))
        self.assertEqual(len(excludes), 2) # german metadata + German PKG
        miss = next(e for e in library if e['title_id'] == 'CUSA00004')
        self.assertFalse(miss['download_available'])
        self.assertEqual(report['skipped_reasons']['duplicate_mirror'], 1)
    def test_required_size(self):
        self.assertFalse(b.parse_size(None))
        self.assertFalse(b.parse_size('12.5 GB'))
        self.assertEqual(b.parse_size('123'), 123)

if __name__ == '__main__':
    unittest.main()
