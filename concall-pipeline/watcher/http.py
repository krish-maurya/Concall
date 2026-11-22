"""Browser-like sessions + retries for NSE/BSE (they reject bare clients)."""
import time, httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
class Throttled:
    def __init__(self, base_headers, warm_url=None, min_gap=1.0):
        self.h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9", **base_headers}
        self.warm_url, self.gap, self.last = warm_url, min_gap, 0.0
        self.client = None
    def _new(self):
        self.client = httpx.Client(headers=self.h, timeout=30, follow_redirects=True)
        if self.warm_url: self.client.get(self.warm_url)  # collect cookies
    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30), retry=retry_if_exception_type(httpx.HTTPError), reraise=True)
    def get(self, url, **kw):
        if self.client is None: self._new()
        wait = self.gap - (time.time() - self.last)
        if wait > 0: time.sleep(wait)
        self.last = time.time()
        r = self.client.get(url, **kw)
        if r.status_code in (401, 429) or r.status_code >= 500:  # 403 is returned as-is: retrying a WAF block just burns time
            self._new()  # refresh cookies, then tenacity retries
            raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
        return r
