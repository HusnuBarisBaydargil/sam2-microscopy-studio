"""Guard the alternate presentation against silently dropping existing controls."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'static'


class PageControls(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.ids = []
        self.controls = {}
        self.scripts = []
        self.stylesheets = []
        self.feed((STATIC / filename).read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        identifier = attrs.get('id')
        if identifier:
            self.ids.append(identifier)
        if identifier and tag in ('button', 'input', 'select', 'textarea'):
            self.controls[identifier] = (tag, {
                k: v for k, v in attrs.items()
                if k in ('type', 'accept', 'multiple', 'min', 'max', 'step', 'checked')
            })
        if tag == 'script':
            self.scripts.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.stylesheets.append(attrs['href'])


def test_refined_ui_retains_original_controls_and_event_targets():
    original = PageControls('index.html')
    refined = PageControls('index-refined.html')
    assert set(original.ids) <= set(refined.ids)
    assert all(count == 1 for count in Counter(refined.ids).values())
    for identifier, contract in original.controls.items():
        assert refined.controls[identifier] == contract, identifier
    # Shared controllers must keep their original initialization order.
    expected = [s.replace('static/classUiController.js', 'static/classUiController-refined.js').replace('static/apiClient.js', 'static/apiClient-refined.js').replace('static/canvasRenderer.js', 'static/canvasRenderer-refined.js').replace('static/classManager.js', 'static/classManager-refined.js')
                for s in original.scripts[:-1]]
    assert refined.scripts == expected + [
        'static/manualClassPicker.js', 'static/script-refined.js', 'static/refinedUi.js'
    ]
    assert refined.stylesheets == ['static/style-refined.css']
    for asset in refined.scripts + refined.stylesheets:
        assert (STATIC.parent / asset).is_file()


def test_default_route_uses_refined_presentation(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == (STATIC / 'index-refined.html').read_bytes()


def test_original_presentation_remains_available(client):
    response = client.get('/?ui=original')
    assert response.status_code == 200
    assert response.data == (STATIC / 'index.html').read_bytes()
    assert client.get('/static/style.css').status_code == 200


def test_ui_query_cannot_select_arbitrary_files(client):
    response = client.get('/?ui=../../app.py')
    assert response.status_code == 200
    assert response.data == (STATIC / 'index-refined.html').read_bytes()
