# PREPROCESSING.md — Modernized text preparation

Locked 2026-04-27. Phase 3 deliverable.

This file documents every preprocessing decision in `src/preprocess.py` and explicitly notes where the modernized Python pipeline diverges from the original R `stab4_wNgrams-nBossYjob (new timeframe).R` script. Each divergence is justified.

## Original R pipeline (recap)

The 2023 SIOP paper used quanteda + topicmodels in R:

1. `tokens()` with `remove_numbers`, `remove_punct`, `remove_symbols`, `remove_hyphens`
2. `tokens_tolower()`
3. `tokens_select(stopwords())` — quanteda's English stopword list
4. **`tokens_wordstem(language = "english")`** — Porter stemmer (produces "manag", "schedul", "christma")
5. `tokens_select(c("*£","£*","*£","£*","£"), selection = "remove")` — remove encoding-corruption tokens
6. `tokens_select(bossPhrases, selection = "remove")` — remove 21 hardcoded compound phrases like `"assist manag"`, `"middle boss"`, `"store supervisor"`, etc.
7. `tokens_select(c("boss", "manag", "supervisor"), selection = "remove")` — remove the search-term stems
8. `tokens_select(phrase("team lead"), selection = "remove")`
9. `tokens_select(c("job", "work"), selection = "remove")`
10. `tokens_ngrams(n = 2)` — bigram features
11. `dfm_trim(min_docfreq = 5)` — minimum document frequency cutoff
12. LDA via Gibbs, `k = 6`, `alpha = 0.1`, `seed = 29`

## Modernized Python pipeline (this project)

`src/preprocess.py`, using spaCy `en_core_web_sm` 3.8.0 with `parser` and `ner` disabled (lemma path only).

| Step | Action | spaCy mechanism |
|---|---|---|
| 1 | Tokenize (whitespace-aware) | `nlp.pipe()` |
| 2 | Drop punct, whitespace, numbers | `tok.is_punct \| tok.is_space \| tok.like_num` |
| 3 | Drop English stopwords | `tok.is_stop` |
| 4 | **Lemmatize** (NOT stem) | `tok.lemma_` |
| 5 | Drop non-alphabetic lemmas | `lemma.isalpha()` check |
| 6 | Drop search-term lemmas + work/job | `BLOCKED_LEMMAS` set |
| 7 | Drop "team lead" / "team leader" 2-token phrases | post-tokenization scan over `BLOCKED_PHRASES` |

`BLOCKED_LEMMAS` = `{boss, manager, manage, supervisor, supervise, job, work}`

Output: `data/processed/posts_preprocessed.parquet` with columns
`id, created_utc, rolling_window, calendar_window, calendar_window_complete, title, body, tokens_title, tokens_body, text_lemmatized_title, text_lemmatized_body`.

The `tokens_*` columns feed the LDA replication; the `text_lemmatized_*` columns feed BERTopic. The original `title` and `body` columns are retained for sentiment analysis (Phase 5) and TopicGPT input (Phase 4c).

## Divergences from the original — and why

### 1. Lemmatization, not stemming. **The most consequential change.**

- **Original:** Porter stemmer turned "manage", "manager", "managing", "managed" all into the stem `"manag"`. Same for "schedule" -> `"schedul"`, "Christmas" -> `"christma"`.
- **Modern:** spaCy lemmatizer maps to dictionary forms — `"manage"`, `"manager"` (different lemmas), `"schedule"`, `"christmas"`.
- **Why:** Stems are not real words; reviewers (and the model itself) lose interpretability. Topic-word lists with `"manag schedul christma"` are harder to read and harder to defend than `"manager schedule christmas"`. Lemmatization is the standard since ~2020 in IO psych and computational social science.
- **Consequence:** The `BLOCKED_LEMMAS` set must include both `"manage"` AND `"manager"` (different lemmas, same intent). Likewise `"supervise"` AND `"supervisor"`.

### 2. `bossPhrases` removal is dropped.

- **Original:** Removed 21 compound phrases like `"assist manag"`, `"store boss"`, `"middle supervisor"`, `"work manag"`, `"job manag"`. Documented as "remove types of bosses."
- **Modern:** Not implemented.
- **Why:** The original list was a workaround for stemmed text — "store manag" was the stemmed bigram for "store manager" / "store managers" / "store managing". After lemmatization these become clean compound noun phrases that BERTopic's embedding model handles natively (the embedding for "store manager" is distinct from "manager" and informative). For LDA, dropping bossPhrases means a slightly different topic structure than the original; we accept this and document it. The locked decision in PROJECT.md is that LDA is the *replication* model, not the primary, and we use coherence-justified `k` rather than the original's hard-coded `k=6` — so we are not aiming for bit-exact replication anyway.
- **Future option:** If LDA replication topics look weird because bigrams like `"store manager"` dominate, we can add an opt-in `--strict-bossphrases` flag to mirror the original. Not implemented unless needed.

### 3. Stopword list source.

- **Original:** quanteda's English stopword list (~175 words).
- **Modern:** spaCy's English stopword list (`tok.is_stop`, ~327 words — broader).
- **Why:** Both are well-curated, both are standard. spaCy's is more aggressive (includes more pronouns, modal-verb forms, contraction fragments). The 152-word delta is unlikely to materially change topic structure on a 97k-post corpus, but it does mean output token counts will be lower than the original. Documented for reproducibility.

### 4. Encoding-corruption token removal is dropped.

- **Original:** Manual list of corruption-byte tokens (`*£`, etc.) to remove after stemming.
- **Modern:** Handled upstream — Arctic Shift returns clean UTF-8, and spaCy's `tok.is_alpha` check at step 5 drops anything non-alphabetic.
- **Why:** Modernized scrape eliminates the source.

### 5. Bigram detection.

- **Original:** `tokens_ngrams(n = 2)` produced bigram-augmented features, fed into a separate LDA run.
- **Modern (Phase 3):** Bigram detection is *not* applied during preprocessing. We emit unigram tokens only.
- **Modern (Phase 4):** Bigrams will be detected at modeling time using `gensim.models.Phrases` (statistical bigram detection over the cleaned token stream) — this is more powerful than blind `n=2` because it requires statistical evidence (PMI-style scoring) before treating two tokens as a phrase. The original's `n=2` produced many spurious bigrams; gensim Phrases avoids this.
- **Status:** deferred to Phase 4 implementation. Documented here so the choice is intentional.

### 6. Document-frequency trimming.

- **Original:** `dfm_trim(min_docfreq = 5)` — words appearing in fewer than 5 docs were dropped.
- **Modern:** Not done in `src/preprocess.py`. We retain all token counts and let the modeling step (Phase 4) decide trimming.
- **Why:** Different models want different cutoffs (LDA likes a min_df, BERTopic doesn't care because it works on embeddings). Centralizing trimming at modeling time is cleaner.

### 7. Title vs body handling.

- **Original:** Titles only.
- **Modern:** Titles AND bodies, with separate `tokens_title` / `tokens_body` columns so any downstream analysis can use either or both.
- **Why:** Per the locked decision in PROJECT.md, modernized analysis uses titles+bodies (the original collected bodies but didn't use them). Phase 4a (LDA replication) can use `tokens_title` to match the original; Phase 4b (BERTopic primary) joins both.

## Performance notes

- spaCy with `disable=["parser", "ner"]` runs at ~30k–60k tokens/sec on CPU.
- Two passes (one for titles, one for bodies) over 97,254 posts. Total wall time ≈ 10–15 minutes on a reasonable laptop.
- Memory: ~1–2 GB peak (corpus + spaCy pipeline). Output parquet is ~200–400 MB.

## Reproducibility

- spaCy version: `3.8.14` (per `pyproject.toml`)
- Model: `en_core_web_sm` `3.8.0`
- Python version: `3.12.10`
- Random seed: spaCy is deterministic for lemma extraction; no seed needed.

Pin these in `pyproject.toml` (already done) and re-record exact versions in the Phase 6 reproducibility appendix.
