import unittest

from app.denomination_doctrine import download_official_source, validate_resolved_host


class Response304:
    status = 304
    headers = {'ETag': '"same"', 'Last-Modified': 'Wed, 02 Sep 2026 00:00:00 GMT'}
    def __enter__(self): return self
    def __exit__(self, *_): return False


class Opener304:
    def open(self, request, timeout=20):
        self.request = request
        return Response304()


class SecureIngestionTests(unittest.TestCase):
    def test_private_dns_result_is_rejected(self):
        def resolver(*args, **kwargs):
            return [(None, None, None, None, ('10.0.0.5', 443))]
        with self.assertRaisesRegex(ValueError, '사설'):
            validate_resolved_host('https://www.kmc.or.kr/doc', resolver)

    def test_etag_conditional_response_returns_not_modified(self):
        opener = Opener304()
        result = download_official_source('https://www.kmc.or.kr/doc', opener=opener, request_headers={'If-None-Match': '"same"'}, resolver=lambda *a, **k: [(None, None, None, None, ('93.184.216.34', 443))])
        self.assertEqual(result['status'], 304)
        self.assertEqual(opener.request.headers['If-none-match'], '"same"')


if __name__ == '__main__':
    unittest.main()
