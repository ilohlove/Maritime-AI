"""Actual local-model acceptance. Prints evidence; never substitutes a mock."""
import argparse
import json
import time
import urllib.error
import urllib.request
from uuid import uuid4

from create_synthetic_pdf import create_pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    base = f'http://127.0.0.1:{args.port}/api'
    local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path, data=None, content_type='application/json'):
        request = urllib.request.Request(base + path, data=data, headers={'Content-Type': content_type})
        try:
            with local.open(request, timeout=610) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'UNVERIFIED: HTTP {error.code}: {error.read().decode()}') from None
    state = call('/ai/status')
    if not state['configured'] or state['provider'] != 'llama.cpp-local':
        raise SystemExit('UNVERIFIED: ' + state['detail'])
    before = call('/vessels')
    doc = call('/documents?filename=synthetic-acceptance.pdf', create_pdf(), 'application/pdf')
    started = time.monotonic()
    result = call('/questions', json.dumps({'request_id': str(uuid4()), 'document_id': doc['id'],
        'question': 'When do lifejacket inspections take place?'}).encode())
    assert result['status'] == 'answered', result
    assert result['provider'] == 'llama.cpp-local'
    assert 'friday' in result['answer'].lower(), result
    assert result['citations'], result
    for citation in result['citations']:
        page = call(f"/documents/{doc['id']}/pages/{citation['page_number']}")
        assert citation['document_id'] == doc['id']
        assert citation['quote'] in page['text']
    # Contains a retrieved keyword, so insufficient evidence must be decided by the model.
    unsupported = call('/questions', json.dumps({'request_id': str(uuid4()), 'document_id': doc['id'],
        'question': 'What is the SOLAS regulation number requiring these lifejacket inspections?'}).encode())
    assert unsupported['status'] == 'insufficient_evidence', unsupported
    assert unsupported['citations'] == []
    assert call('/vessels') == before, 'Ship Profile changed unexpectedly'
    print(json.dumps({'result': 'REAL LOCAL MODEL ACCEPTANCE PASSED', 'elapsed_seconds': round(time.monotonic()-started, 2),
        'supported': result, 'unsupported': unsupported}, indent=2, ensure_ascii=False))
    print('Also inspect evidence in the UI. This does not certify maritime correctness or Windows performance.')


if __name__ == '__main__':
    main()
