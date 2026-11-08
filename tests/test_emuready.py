import json
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import emuready  # noqa: E402

DEVICES = {'devices': [
    {'id': 'd-thor', 'modelName': 'Thor', 'brandName': 'AYN', 'socName': 'Snapdragon 8 Gen 2'},
    {'id': 'd-odin', 'modelName': 'Odin 2', 'brandName': 'AYN', 'socName': 'Snapdragon 8 Gen 2'},
    {'id': 'd-rp4', 'modelName': 'Pocket 4 Pro', 'brandName': 'Retroid', 'socName': 'Dimensity 1100'}]}
GAMES = [{'id': 'g-ps2', 'title': 'Grand Theft Auto: San Andreas', 'system': {'name': 'Sony PlayStation 2'}},
         {'id': 'g-pc', 'title': 'Grand Theft Auto: San Andreas', 'system': {'name': 'Microsoft Windows'}},
         {'id': 'g-other', 'title': 'Grand Theft Auto: Vice City', 'system': {'name': 'Sony PlayStation 2'}}]


def listing(i, emu, label, rank, votes=0):
    return {'id': f'l{i}', 'notes': 'Läuft  gut\nmit 2x', 'createdAt': '2026-10-01T10:00:00Z', 'voteCount': votes,
            'device': {'modelName': 'Odin 2', 'brand': {'name': 'AYN'}}, 'emulator': {'name': emu},
            'performance': {'label': label, 'rank': rank}}


class FakeApi:
    def __init__(self):
        self.calls = []

    def __call__(self, url):
        proc = url.split('/trpc/')[1].split('?')[0]
        inp = json.loads(urllib.parse.unquote(url.split('input=')[1]))['json']
        self.calls.append((proc, inp))
        data = {
            'devices.get': lambda: DEVICES,
            'games.searchGames': lambda: GAMES,
            'listings.get': lambda: {'listings': [listing(1, 'NetherSX2', 'Great', 2, 5), listing(2, 'NetherSX2', 'Perfect', 1, 1),
                                          listing(3, 'NetherSX2', 'Poor', 4), listing(4, 'AetherSX2', 'Playable', 3)]
                             if inp['gameIds'] == ['g-ps2'] else [listing(9, 'GameNative', 'Playable', 3)]},
            'listings.byId': lambda: {'customFieldValues': [{'value': 'Turnip', 'customFieldDefinition': {'name': 'graphics_driver', 'label': 'Grafiktreiber'}},
                                                    {'value': 'https://youtu.be/x', 'customFieldDefinition': {'name': 'youtube', 'label': 'YouTube'}}]},
        }[proc]()
        return {'result': {'data': {'json': data}}}


class EmuReadyTest(unittest.TestCase):
    def test_same_soc_devices_and_reports_per_version(self):
        api = FakeApi()
        client = emuready.Client(pause=0, fetch=api)
        state = {}
        ids = emuready.reference_devices(client, state)
        self.assertEqual(ids, ['d-thor', 'd-odin'])        # Retroid with another SoC excluded
        game = {'id': 'gta-sa', 'title': 'Grand Theft Auto: San Andreas', 'versions': [
            {'id': 'ps2', 'name': 'PS2', 'type': 'original', 'platforms': ['PlayStation 2']},
            {'id': 'pc', 'name': 'PC', 'type': 'port', 'platforms': ['PC']},
            {'id': 'android', 'name': 'Android', 'type': 'android', 'platforms': ['Android']}]}
        n = emuready.sync_game(client, game, ids)
        self.assertEqual(n, 5)
        ps2 = game['versions'][0]['reports']
        self.assertEqual([r['rating'] for r in ps2], ['Perfect', 'Great', 'Playable', 'Poor'])  # best first
        self.assertEqual(ps2[0]['ratingDe'], 'Perfekt')
        self.assertEqual(ps2[0]['url'], 'https://www.emuready.com/listings/l2')
        self.assertEqual(ps2[0]['summary'], 'Läuft gut mit 2x')
        self.assertEqual(ps2[0]['settings'], {'Grafiktreiber': 'Turnip'})       # youtube field dropped
        self.assertNotIn('settings', ps2[3])                                       # only 2 best per emulator
        self.assertEqual(game['versions'][1]['reports'][0]['emulator'], 'GameNative')
        self.assertNotIn('reports', game['versions'][2])                          # Android: no EmuReady system
        self.assertFalse(any(c[1].get('gameIds') == ['g-other'] for c in api.calls))  # other title not used

    def test_platform_mapping(self):
        self.assertEqual(emuready.platform_of('Sony PlayStation Portable'), 'PSP')
        self.assertEqual(emuready.platform_of('Microsoft Xbox 360'), 'Xbox 360')
        self.assertEqual(emuready.platform_of('Nintendo Super Nintendo Entertainment System'), 'SNES')


if __name__ == '__main__':
    unittest.main()


class RateLimitTest(unittest.TestCase):
    def test_stops_after_second_429(self):
        import urllib.error
        calls = []

        def fetch(url):
            calls.append(url)
            raise urllib.error.HTTPError(url, 429, 'Too Many Requests', {}, None)
        client = emuready.Client(pause=0, fetch=fetch, backoff=0)
        with self.assertRaises(emuready.RateLimited):
            client.call('games.searchGames', {'query': 'x'})
        self.assertEqual(len(calls), 2)
