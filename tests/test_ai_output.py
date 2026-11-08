"""Regression tests for AI-output parsing and safe structured requests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ai_agents import model_research, model_vision, parse_json, vision_queue


class StructuredAIOutputTests(unittest.TestCase):
    def test_truncated_response_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, 'incomplete.*max_output_tokens'):
            parse_json({'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': []})

    def test_bad_model_json_fails_without_leaking_content(self):
        raw = {'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': '{"findings":[{"name":"oops"'}
        ]}]}
        with self.assertRaisesRegex(ValueError, 'invalid JSON') as caught:
            parse_json(raw)
        self.assertNotIn('oops', str(caught.exception))

    def test_vision_uses_curated_images_if_discovery_has_no_media(self):
        image = 'https://raw.githubusercontent.com/igawa6/eden-duo-companions/main/screenshots/metroid-dread/map.png'
        catalog = {'games': [{'id': 'metroid-dread', 'title': 'Metroid Dread', 'routes': [
            {'id': 'dread-duo', 'name': 'Eden Duo Companion', 'media': [
                {'url': image, 'caption': 'Map', 'sourceUrl': 'https://github.com/igawa6/eden-duo-companions'}]}]}]}
        queue = vision_queue({'candidates': []}, {'results': {}}, 2, catalog=catalog)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0][1]['gameTitle'], 'Metroid Dread')
        self.assertEqual(queue[0][1]['routeId'], 'dread-duo')
        self.assertEqual(queue[0][2]['url'], image)
        self.assertEqual(vision_queue({'candidates': []},
                         {'results': {queue[0][0]: {'verdict': 'plausible'}}}, 2, catalog=catalog), [])

    def test_curated_image_not_processed_without_allowed_url(self):
        catalog = {'games': [{'id': 'demo', 'title': 'Demo', 'routes': [
            {'id': 'demo-route', 'name': 'Demo port', 'media': [
                {'url': 'https://localhost:4567/exfil.png'}]}]}]}
        self.assertEqual(vision_queue({'candidates': []}, {'results': {}}, 2, catalog=catalog), [])

    def test_research_sends_strict_schema_and_high_context(self):
        seen = {}
        def fake(request, token):
            seen.update(request)
            return {'status': 'completed', 'output': []}
        with patch('ai_agents.response_request', side_effect=fake):
            model_research({'title': 'Minecraft'}, 'hidden-token')
        self.assertEqual(seen['tools'][0]['search_context_size'], 'high')
        self.assertEqual(seen['text']['format']['type'], 'json_schema')
        self.assertTrue(seen['text']['format']['strict'])
        self.assertGreater(seen['max_output_tokens'], 1300)
        self.assertIn('web_search_call.action.sources', seen['include'])

    def test_vision_requests_image_with_strict_schema(self):
        seen = {}
        def fake(request, token):
            seen.update(request)
            return {'status': 'completed', 'output': []}
        with patch('ai_agents.response_request', side_effect=fake):
            model_vision({'project': 'Demo'}, {'url': 'https://raw.githubusercontent.com/demo/atlas/main/shot.png'}, 'hidden-token')
        self.assertEqual(seen['text']['format']['type'], 'json_schema')
        self.assertEqual(seen['input'][0]['content'][1]['detail'], 'high')
        self.assertTrue(seen['text']['format']['strict'])


if __name__ == '__main__':
    unittest.main()
