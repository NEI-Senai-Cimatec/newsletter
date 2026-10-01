# Fix: JSON-LD node discovery, sitemap parsing, and scraper fallbacks

Branch: `fix/jsonld-sitemap-parsers`

## Context

Four quantum-news scrapers assume fixed positions inside JSON-LD payloads
(`@graph[0]`, `@graph[1]`, `ld+json[1]`) and a fixed sitemap shape
(`.text[8:-3]`). The sites changed their schema graphs and formats, so:

- **Quantum Zeitgeist**: `rank-math-schema-pro` now emits 8 graph nodes and
  `NewsArticle` sits at index 7; the scraper reads index 0 (`Place`), gets an
  empty `articleSection`, and rejects all 916 URLs with "Category invalid".
- **Inside Quantum Technology**: `[8:-3]` corrupts `loc` and `lastmod`
  (`BeautifulSoup.text` already strips CDATA), so `datetime.fromisoformat`
  raises and every entry is dropped → 0 articles. Its `aioseo-schema` graph
  starts with `BreadcrumbList`, and `div.entry-content` no longer exists.
- **The Quantum Inspector**: `yoast-schema-graph` is gone; the fallback
  `ld+json[1]` only works by accident.
- **Quanta Magazine**: `metadata`/`metadata_2` can stay unbound, and
  `sidebar__tag-wrap` can be missing.
- **`core.utils.get_cached_page`**: the `except` block re-raises, so the
  Selenium fallback below it is dead code. IQT is Cloudflare-protected
  (cloudscraper → 403), so the portal cannot fetch pages at all.

Approach: locate JSON-LD nodes by `@type` instead of index, share one
metadata extractor across portals, make every scraper's parsing testable as a
pure function, and repair the fetch fallback.

Decisions already taken with the human partner:
1. Fix all four portals plus shared infrastructure.
2. Broaden the Quantum Zeitgeist relevance filter (case-insensitive match on
   categories + title + keywords), instead of the strict `'Quantum' in
   category.split(' ')` rule.
3. Fix `get_cached_page` so the Selenium fallback actually runs.
4. Keep the Quanta Magazine kicker/category filter exactly as it is.

## Global constraints

- TDD: every test is written and observed failing before the implementation.
- Test command (whole suite, end of every task):
  `.venv\Scripts\python.exe -m pytest tests -q`
- Baseline: 157 passed. The suite must be green before any task completes.
- No comment changes beyond what a step names; match existing code style.
- Do not touch the date filter, GUI, or `task_runner` — already delivered.

## Pre-flight: shared interfaces

| Tasks | Interface | Finding |
|---|---|---|
| 1 → 3,4,5,6 | `core.utils.find_ld_node` / `extract_article_metadata` | Task 1 Produces the exact names Tasks 3–6 consume; agreed. |
| 2 → 4 | `get_cached_page` fallback | Task 4 (IQT) needs the Selenium path live; Task 2 produces it. |
| 1 → 3 | `category` type | Task 1 returns `list[str]`; Task 3 template call must join. Recorded in Task 3 step. |

---

## Task 1: `core/utils.py` — JSON-LD node discovery and metadata extraction

### Produces
- `iter_ld_json(soup)` → iterator of parsed dict documents
- `collect_ld_nodes(soup)` → list of dict nodes (graphs flattened)
- `ld_type_matches(node, type_name)` → bool
- `find_ld_node(nodes, *types)` → dict | None
- `extract_article_metadata(soup, script_class=None)` → dict

### Steps

**Step 1 — write the failing tests** in `tests/test_jsonld.py`.

Cases (one test per behavior, real JSON payloads, no mocks):

1. `test_find_ld_node_locates_article_at_any_position` — a `@graph` whose
   `NewsArticle` is the 8th element (index 7), preceded by `Place`,
   `NewsMediaOrganization`, `WebSite`, `ImageObject`, `BreadcrumbList`,
   `WebPage`, `Person`. Assert `find_ld_node(...)` returns the article node
   with its `headline`.
2. `test_find_ld_node_matches_type_list` — `@type: ["Article", "NewsArticle"]`.
3. `test_find_ld_node_respects_type_priority` — graph contains both
   `WebPage` (index 0) and `NewsArticle` (index 1); requesting
   `('NewsArticle', 'WebPage')` returns the article.
4. `test_find_ld_node_returns_none_when_absent` — graph with only
   `WebSite`/`Organization`.
5. `test_collect_ld_nodes_flattens_graph_and_keeps_plain_documents` — one
   script with `@graph`, one plain `{"@type": "NewsArticle"}` document.
6. `test_iter_ld_json_repairs_malformed_payload` — payload with a trailing
   comma; still yields a dict (uses `repair_json`).
7. `test_iter_ld_json_ignores_non_ld_json_scripts` — `type="application/ld+json"`
   only; a `text/javascript` script containing `'@graph'` is not yielded.
8. `test_extract_article_metadata_reads_headline_author_and_dates` —
   `NewsArticle` with `headline`, `author: {"name": ...}`, `datePublished`,
   `dateModified`, `articleSection` as a string → returns
   `category == ['Deep Tech, Emerging Technology']` and a parsed
   `datePublished` ISO timestamp.
9. `test_extract_article_metadata_normalizes_author_variants` — author as
   dict, as list of dicts, and as plain string.
10. `test_extract_article_metadata_normalizes_keywords_variants` —
    `keywords` as string `"a, b"` and as list `["a", "b"]` both yield
    `['a', 'b']`.
11. `test_extract_article_metadata_prefers_script_class` — two `ld+json`
    scripts; the one with `class="rank-math-schema-pro"` wins even when the
    other is a `NewsArticle`.
12. `test_extract_article_metadata_falls_back_to_meta_tags` — no JSON-LD at
    all, but `meta[property="og:title"]`,
    `meta[property="article:published_time"]`, `meta[name="author"]` →
    title/author/datePublished filled.
13. `test_extract_article_metadata_returns_empty_strings_not_none` — empty
    document → `title == ''`, `date == ''`, `datePublished == ''`,
    `dateModified == ''`, `category == []`, `keywords == []`.
14. `test_extract_article_metadata_returns_none_without_any_source` — no
    JSON-LD and no meta tags → `None`.

Expected: `FAILED`, `ImportError: cannot import name 'find_ld_node'` (or
`AttributeError`) — the feature is missing, not a typo.

**Step 2 — run the tests.**
`.venv\Scripts\python.exe -m pytest tests/test_jsonld.py -q`
Expected: all 14 fail on import/name error.

**Step 3 — implement in `core/utils.py`** next to the other scraping helpers
(after `parse_article_date`, ~line 522):

```python
def iter_ld_json(soup):
    """Yield every parsed JSON-LD document in *soup* (malformed ones repaired)."""

def collect_ld_nodes(soup):
    """Flatten every document's @graph into one list of nodes."""

def ld_type_matches(node, type_name):
    """@type may be a string or a list of strings."""

def find_ld_node(nodes, *types):
    """First node whose @type matches, honouring the priority in *types*."""

def extract_article_metadata(soup, script_class=None):
    """Normalize article metadata from JSON-LD (and <meta> tags as fallback)."""
```

Behavior contract for `extract_article_metadata`:
- nodes come from `script_class`'s script first (parsed with the
  `json.loads` → `repair_json` fallback), then from `collect_ld_nodes(soup)`;
- node priority: `NewsArticle`, `Article`, `BlogPosting`, `ScholarlyArticle`,
  `TechArticle`, `WebPage`;
- `title` = `headline` or `name` (stripped);
- `author` = `author.name` for a dict, first dict for a list, the string
  itself for a string, otherwise `''`;
- `date` = `parse_article_date(datePublished)[0]`, `datePublished` = `[1]`,
  `dateModified` = `parse_article_date(dateModified)[1]` (falls back to
  `datePublished` when `dateModified` is absent) — all `''` on failure;
- `category` = list of strings from `articleSection` (string → 1-element
  list, missing → `[]`);
- `keywords` = list of strings, splitting a comma-bearing string;
- any still-empty field is filled from `og:title`,
  `article:published_time`, `article:modified_time`, `meta[name=author]`;
- returns `None` when neither JSON-LD nor meta tags yield anything.

**Step 4 — verify GREEN.**
`.venv\Scripts\python.exe -m pytest tests/test_jsonld.py -q` → 14 passed.

**Step 5 — full suite.**
`.venv\Scripts\python.exe -m pytest tests -q` → 171 passed (157 + 14).

**Step 6 — commit.**
`git add core/utils.py tests/test_jsonld.py`
`git commit -m "feat: locate JSON-LD article nodes by @type and share metadata extraction"`

---

## Task 2: `get_cached_page` — make the Selenium fallback reachable

### Produces
`core.utils.get_cached_page(url, ignore_cache, driver, type_)` returns page
source when cloudscraper fails, instead of raising.

### Consumed by
Task 4 (IQT is Cloudflare-protected and needs this path).

### Steps

**Step 1 — write the failing tests** in `tests/test_utils.py` (append).

1. `test_get_cached_page_falls_back_to_selenium_when_cloudscraper_fails`
   - monkeypatch `cu.scraper.get` to raise `Exception('403')`;
   - monkeypatch `cu.CACHE_DIR` / `cu.CACHE_JSON` into `tmp_path` and create
     the directory;
   - pass a fake driver exposing `get(url)` (records the url),
     `page_source = '<html>rendered</html>'`, and `find_element(by, value)`
     returning a plain object (so `WebDriverWait`'s EC condition passes);
   - assert the returned source is `'<html>rendered</html>'` and
     `fake.got == url`;
   - assert a cache file now exists and `CACHE_JSON` has one entry.
2. `test_get_cached_page_does_not_cache_cloudflare_challenge`
   - same, but `page_source` contains `challenge-error-text`;
   - assert the source is still returned (so the caller degrades gracefully
     instead of receiving `None`) and **no** cache file / cache entry was
     written.
3. `test_get_cached_page_without_driver_raises`
   - cloudscraper fails and `driver is None` → raises a `RuntimeError`
     mentioning the url (today: bare re-raise of the cloudscraper error).

Expected: test 1 and 2 fail because `get_cached_page` re-raises
(`Exception: 403`); test 3 may pass already — check the failure reason.

**Step 2 — run.**
`.venv\Scripts\python.exe -m pytest tests/test_utils.py -q`

**Step 3 — implement.** In `core/utils.py:297-348`:
- add `timeout=30` to `scraper.get(url)`;
- change the `except` body from `raise` to a `logger.warning` that says
  cloudscraper failed and Selenium will be tried;
- add an explicit guard `if driver is None: raise RuntimeError(...)`;
- in the Selenium block, return `page_source` when the Cloudflare marker is
  present (without caching) and keep the existing cache-and-return path
  otherwise;
- keep the outer `except` logging Selenium failures, and re-raise so callers
  still see a hard failure when both transports fail.

**Step 4 — GREEN.** `.venv\Scripts\python.exe -m pytest tests/test_utils.py -q`

**Step 5 — full suite.** `.venv\Scripts\python.exe -m pytest tests -q` → 174 passed.

**Step 6 — commit.**
`git commit -am "fix: reach the Selenium fallback when cloudscraper fails"`

---

## Task 3: Quantum Zeitgeist — node by @type + broadened relevance filter

### Consumes
`core.utils.extract_article_metadata`, `core.utils.find_ld_node` (Task 1).

### Steps

**Step 1 — capture a real fixture.** Fetch one live Quantum Zeitgeist
article (cloudscraper works for that host) and store a trimmed copy of its
`rank-math-schema-pro` payload plus the article `<div class="tags-section">`
markup under `tests/fixtures/qz_article.html`. Read it back and print the
node order so the fixture is real data, not an illustration.

**Step 2 — write the failing tests** in `tests/test_scrapers_parse.py`
(new file):

1. `test_qz_metadata_extracts_article_at_graph_index_7` — loads the fixture
   and asserts `qz_extract_metadata(soup)` returns a non-empty `title`,
   `author`, `datePublished`, and `category` containing the portal's own
   section text.
2. `test_qz_relevance_accepts_section_without_quantum_word_when_title_matches`
   — `articleSection == 'Deep Tech, Emerging Technology'` with a `title`
   containing "quantum" → accepted.
3. `test_qz_relevance_rejects_non_quantum_article` — no occurrence of
   "quantum" (case-insensitive) in categories, title, or keywords →
   rejected (`None`).
4. `test_qz_relevance_is_case_insensitive` — `articleSection == 'Quantum
   Algorithms'` written in lowercase still passes.
5. `test_qz_metadata_tags_section_provides_keywords` — fixture keywords end
   up in `metadata['keywords']`.

Expected: `AttributeError: module 'scrapers.quantumzeitgeist' has no
attribute 'qz_extract_metadata'`.

**Step 3 — extract and fix.** In `scrapers/quantumzeitgeist.py`:

- add a module-level pure function
  `qz_extract_metadata(soup)` returning the
  `extract_article_metadata(soup, script_class='rank-math-schema-pro')`
  result plus `keywords` collected from
  `post_content.find('div', class_='tags-section')`, or `None`;
- add `qz_is_relevant(metadata)` → true when `'quantum'` appears in
  `' '.join(category + [title] + keywords).lower()`;
- in `qz_generate_article_html`, replace lines 135-162 with calls to these
  two functions; when `qz_extract_metadata` or `qz_is_relevant` fails,
  `logger.warning(...)` and `return None` (same message shape as today);
- template call becomes `categories=', '.join(article_data['category'])`
  (the extractor normalizes to a list);
- `articles_dict[...]['category']` stores the normalized list.

**Step 4 — GREEN.** `.venv\Scripts\python.exe -m pytest tests/test_scrapers_parse.py -q`

**Step 5 — full suite.** `.venv\Scripts\python.exe -m pytest tests -q` → 179 passed.

**Step 6 — commit.** `git commit -am "fix: parse Quantum Zeitgeist schema by node type and broaden relevance filter"`

---

## Task 4: Inside Quantum Technology — sitemap, schema, content container

### Consumes
Task 1 helpers; Task 2 fallback (Cloudflare → Selenium).

### Steps

**Step 1 — capture fixtures.** The site is Cloudflare-protected for
cloudscraper, so fetch an article page through `initialize_driver()` and
save `tests/fixtures/iqt_article.html`. Save `tests/fixtures/iqt_sitemap.xml`
with a `<![CDATA[...]]>` `loc` and a CDATA `lastmod`. Print the class names
of the content container inside `<article class="single_post_article">` so
the selector in Step 3 is based on the live DOM.

**Step 2 — write the failing tests** in `tests/test_scrapers_parse.py`:

1. `test_iqt_sitemap_keeps_full_url_and_parses_cdata_date` — parses the
   fixture sitemap with `iqt_parse_sitemap_xml(page_source)` (new pure
   function) and asserts:
   - `entry['url'] == 'https://www.insidequantumtechnology.com/news-archive/...'`
     (scheme intact, no truncation);
   - `entry['date'] == '2026-09-14 11:00 +0000'` (CDATE stripped, no
     `[8:-3]` damage).
2. `test_iqt_sitemap_skips_entries_with_unparseable_dates` — an entry with
   `lastmod` missing → entry dropped, others kept.
3. `test_iqt_metadata_from_aioseo_graph` — `extract_article_metadata(soup,
   script_class='aioseo-schema')` on the fixture yields a non-empty
   `title` and `datePublished` (today it yields `''` because index 0 is a
   `BreadcrumbList`).
4. `test_iqt_content_container_found_when_entry_content_absent` —
   `iqt_find_content_container(soup)` (new pure function) returns the live
   container and its cleaned paragraph text is non-empty.
5. `test_iqt_keywords_missing_tags_section_does_not_raise` — fixture without
   `tags-section` → `metadata['keywords'] == []`, no `AttributeError`.
6. `test_iqt_metadata_falls_back_to_meta_tags` — fixture stripped of all
   `ld+json` scripts still produces a title and `datePublished`.

Expected: tests 1/3/4 fail with `AttributeError` (functions missing) or with
the assertion that the URL is truncated.

**Step 3 — implement** in `scrapers/insidequantumtechnology.py`:

- `iqt_parse_sitemap_xml(page_source)`: BeautifulSoup `xml` parser, returns
  `{'url': loc.text, 'date': 'YYYY-MM-DD HH:MM ZZ'}` entries; no slicing;
  defensive `.strip()` of any literal `<![CDATA[` / `]]>`; entries with
  unparseable `lastmod` are logged and skipped; `iqt_scrape_sitemap` calls it
  per sitemap and keeps the existing dedupe/sort.
- `iqt_find_content_container(soup)`: returns the first non-empty match
  among `div.entry-content`, `div[class*=entry-content]`,
  `div[class*=post-content]`, `div[class*=mk-post-content]`, falling back to
  the `article.single_post_article` element itself.
- `iqt_extract_metadata(soup, post_content)`:
  `extract_article_metadata(soup, script_class='aioseo-schema')` + tags from
  `post_content.find('div', class_='tags-section')` guarded with `if tags:`;
  returns `None` when the extractor returns `None`.
- `iqt_generate_article_html`: use the three functions above; template call
  becomes `categories=', '.join(article_data['category'])`; when
  `iqt_find_content_container` finds nothing, keep today's warning-and-skip
  path.

**Step 4 — GREEN.** `.venv\Scripts\python.exe -m pytest tests/test_scrapers_parse.py -q`

**Step 5 — full suite.** `.venv\Scripts\python.exe -m pytest tests -q` → 185 passed.

**Step 6 — commit.** `git commit -am "fix: repair Inside Quantum Technology sitemap and article parsing"`

---

## Task 5: The Quantum Insider — locate the article node, normalize keywords

### Consumes
Task 1 helpers.

### Steps

**Step 1 — capture a fixture** from the cached TQI article HTML
(`cache/article_<sha256>.html` for a `thequantuminsider.com` URL) into
`tests/fixtures/tqi_article.html`, preserving its `application/ld+json`
scripts.

**Step 2 — write the failing tests:**

1. `test_tqi_metadata_works_without_yoast_script` — fixture with only plain
   `ld+json` scripts (no `yoast-schema-graph`) → `tqi_extract_metadata(soup)`
   returns the `NewsArticle`'s `title`, `datePublished`, `category`, and the
   `author` name.
2. `test_tqi_metadata_works_with_yoast_script` — fixture variant that has
   `class="yoast-schema-graph"` → same result (regression guard for the old
   path).
3. `test_tqi_metadata_ignores_ld_json_scripts_before_the_article` — an
   `Organization` script is emitted first; the article is still found.
4. `test_tqi_keywords_string_is_not_split_into_characters` —
   `keywords: "alpha, beta"` produces `['alpha', 'beta']`, so the HTML
   template's `', '.join(...)` renders correctly.

Expected: `AttributeError: ... no attribute 'tqi_extract_metadata'`.

**Step 3 — implement** in `scrapers/thequantuminsider.py`:
- `tqi_extract_metadata(soup, post_content)` →
  `extract_article_metadata(soup, script_class='yoast-schema-graph')`;
- `tqi_generate_article_html` replaces lines 166-192 with that call;
- keywords come back normalized as a list (no `str` reaching `', '.join`).

**Step 4 — GREEN.** `.venv\Scripts\python.exe -m pytest tests/test_scrapers_parse.py -q`

**Step 5 — full suite.** `.venv\Scripts\python.exe -m pytest tests -q` → 189 passed.

**Step 6 — commit.** `git commit -am "fix: resolve The Quantum Insider article node by type"`

---

## Task 6: Quanta Magazine — hardening only, filter untouched

### Consumes
Task 1 helpers.

### Steps

**Step 1 — capture a fixture** from a cached Quanta article HTML into
`tests/fixtures/qm_article.html` (must include the `@graph` script and the
`ga4Array` script).

**Step 2 — write the failing tests:**

1. `test_qm_metadata_no_graph_script_returns_none` — fixture with only the
   `ga4Array` script → `qm_extract_metadata(soup)` returns `None` instead of
   raising `NameError`/`UnboundLocalError`.
2. `test_qm_metadata_no_ga4_script_returns_none` — fixture with only the
   `@graph` script → `None` (today: `UnboundLocalError`).
3. `test_qm_metadata_reads_webpage_node` — full fixture → non-empty `title`
   (site suffix stripped), `author`, `datePublished`, `category`.
4. `test_qm_relevance_filter_still_rejects_non_quantum_kicker` —
   `kicker == 'biology'` → `qm_is_relevant(...) is False`;
   `kicker == 'quantum physics'` → `True`. **The rule itself must not
   change.**
5. `test_qm_missing_sidebar_tags_does_not_raise` — fixture without
   `sidebar__tag-wrap` → `keywords == []`.

Expected: tests 1 and 2 fail with `UnboundLocalError`, not with an
`AttributeError`.

**Step 3 — implement** in `scrapers/quantamagazine.py`:
- initialize `metadata = None` and `metadata_2 = None` before the script
  loop, and wrap each `json.loads` in the `json.loads` → `repair_json`
  fallback;
- `qm_extract_metadata(soup)` → node lookup with
  `find_ld_node(collect_ld_nodes(soup), 'NewsArticle', 'Article', 'WebPage')`
  for the graph side, plus the parsed `ga4Array` payload; returns `None`
  when either side is missing; `name` keeps the `[0:-18]` suffix strip,
  guarded by `len(name) > 18`;
- `qm_is_relevant(ga4)` keeps today's exact check
  (`kicker is None` or `'quantum' not in kicker.split(' ')`);
- guard the `sidebar__tag-wrap` lookup;
- `qm_generate_article_html` uses these three functions; no other behavior
  changes.

**Step 4 — GREEN.** `.venv\Scripts\python.exe -m pytest tests/test_scrapers_parse.py -q`

**Step 5 — full suite.** `.venv\Scripts\python.exe -m pytest tests -q` → 194 passed.

**Step 6 — commit.** `git commit -am "fix: harden Quanta Magazine metadata extraction without touching its filter"`

---

## Task 7: End-to-end verification and cleanup

### Steps

1. Re-run the whole suite and read the output:
   `.venv\Scripts\python.exe -m pytest tests -q` → 194 passed.
2. Static check that no scraper still indexes a JSON-LD graph position:
   search `scrapers\*.py` for `@graph'\]\[` — expect zero matches.
3. Static check that no scraper slices sitemap text: search for `[8:-3]` in
   `scrapers\*.py` — expect zero matches.
4. `git status` clean, `git log --oneline -8` shows the task commits.
5. Commit anything left over; ledger the result.

---

## Review Focus

Inputs and failure modes the tests deliberately do **not** exercise:

- Real network behaviour: cloudscraper vs. Selenium on Cloudflare, live
  sitemap contents, ChromeDriver availability on this machine.
- Cache interaction with pre-existing `cache/` and `quantum_articles.json`
  rows collected by the old (broken) parsers.
- The end-to-end pipeline (`task_runner` → scraper → `generate_content_json`
  → `merge_json_files`): the tests stop at metadata extraction.
- Volume: a full Quantum Zeitgeist run now passes relevance for many more
  URLs than before, which changes how long a run takes and how many parse
  jobs the LLM queue sees.
