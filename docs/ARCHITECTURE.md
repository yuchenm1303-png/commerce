# Architecture

## Product goal

Commerce is an AI-assisted **product opportunity intelligence system**. It is not a generic scraper and it is not the downstream listing executor. Its job is to discover, measure, explain, validate, and rank opportunities before they are handed to an execution system such as `ecommerce-agent`.

## Non-negotiable design rules

1. **Facts before semantics.** Source adapters collect measurable facts. Unsupported metrics stay `null`; proxies are never relabeled as real sales.
2. **Math is deterministic.** Delta, velocity, acceleration, baselines, margin and other arithmetic belong in code, not an LLM prompt.
3. **AI must be auditable.** Semantic evaluation returns claims, evidence, risks, missing information and confidence rather than an unexplained score.
4. **Discovery and analysis are decoupled.** Crawling must not block on AI analysis.
5. **Platform-specific acquisition stays behind adapters.** Prefer official/stable APIs, then HTTP/network JSON, then deterministic browser automation, with an AI browser agent only as a fallback.
6. **Snapshots are append-only.** Time-series history is a first-class asset and later sales outcomes must be able to calibrate the selection strategy.
7. **Risk gates are separate from ranking.** A high trend score cannot override hard compliance, IP, logistics or certification failures.

## Layers

```text
Source Adapters
  -> ProductSnapshot memory
  -> Trend Engine
  -> Candidate filtering
  -> Semantic / evidence evaluator
  -> Supply & economics
  -> Market-transfer validation
  -> Risk gates
  -> Opportunity ranking
  -> downstream Product Center / listing execution
  -> sales feedback
```

## Acquisition strategy

The adapter boundary deliberately supports multiple acquisition styles:

- stable official APIs;
- reusable HTTP or internal network JSON endpoints;
- AnyCrawl-style web data infrastructure;
- Playwright network-response capture for highly dynamic platforms;
- browser-use-style agent interaction only when deterministic methods are insufficient.

A future Goofish adapter should learn from the proven pattern of using Playwright to establish a real session and trigger page behavior while consuming the platform's own network JSON responses for search/detail/profile facts, instead of making DOM selectors the primary data contract.

## v0.1 scope

The first foundation intentionally includes only:

- source adapter protocol;
- append-only product snapshots;
- SQLite repository behind a replaceable interface;
- deterministic trend signals;
- structured evidence-chain contracts;
- a minimal FastAPI surface;
- tests and CI.

It intentionally does **not** invent an Opportunity Score, hard-code a marketplace strategy, or call an LLM before we have real source data to evaluate.

## Near-term milestones

1. Goofish source adapter and live discovery spike.
2. Snapshot `wants/views/price` time series and velocity detection.
3. Candidate queue so only meaningful anomalies reach AI.
4. Product-selection skill/evidence evaluator.
5. AnyCrawl adapter for generic sites.
6. Supply/economics and target-market transfer checks.
7. Hand-off contract to `ecommerce-agent`.
8. 7/14/30-day sales feedback loop.
