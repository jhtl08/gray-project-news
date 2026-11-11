import threading

# Persistent model cache: set HF_HOME (e.g. a Docker volume) to a stable
# directory so downloaded weights survive across runs/processes. Defaults to
# ~/.cache/huggingface when unset.
# HF_HOME documentation note: export HF_HOME=/path/to/persistent/cache

_router = None
_router_lock = threading.Lock()


def _get_router_class():
    """Resolve the laya Router class lazily so importing this module has no
    model-loading or download side effects."""
    router_cls = globals().get("Router")
    if router_cls is None:
        from laya import Router as router_cls

        globals()["Router"] = router_cls
    return router_cls


def get_router():
    """Thread-safe singleton accessor for the laya Router.

    Creates ``Router(default="multilingual", max_loaded=1)`` and preloads the
    ``multilingual`` model on first call only.
    """
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                Router = _get_router_class()
                router = Router(default="multilingual", max_loaded=1)
                router.preload(["multilingual"])
                _router = router
    return _router


questions = {
    "disruptiveness": {
        "type": "score",
        "instructions": ("""
            # Task: Evaluate Prediction-Market News Disruptiveness

Evaluate news headlines for their potential usefulness to prediction-market traders. Return respective scores from 0 to 100, where higher scores indicate greater expected usefulness and potential market impact.

## Prediction-market context

Relevant markets may concern:

- Politics, elections, government, and public policy
- Geopolitics, diplomacy, war, military conflict, and ceasefires
- Finance, macroeconomics, interest rates, inflation, and central-bank decisions
- Stocks, companies, earnings, IPOs, bankruptcy, and commodities
- Cryptocurrency, token prices, and blockchain developments
- Technology, artificial intelligence, and major product releases
- Sports and esports, including match outcomes, tournaments, and player performance
- Culture and entertainment, including box office, awards, and celebrity-related outcomes
- Weather, temperature, natural disasters, and other measurable events

Examples of market questions include:

- Will a ceasefire between specified countries hold through a given date?
- What price will a cryptocurrency reach by a specified date?
- Which team will win a match or tournament?
- Will one country invade another before a specified year?
- What price will crude oil reach in a given month?
- What will a company's IPO closing market capitalization be?
- Will a company announce bankruptcy by a specified date?
- Which party will win an election or control a legislative chamber?
- Which company will have the leading AI model at a specified time?
- What will the Federal Reserve decide at its next meeting?
- What will the highest temperature in a city be on a given date?

## Scoring criteria

Evaluate two dimensions:

1. MARKET RELEVANCE (40%): How likely is the headline to be useful for an existing unresolved prediction market, or for a plausible market that could reasonably exist? Consider whether it relates to a specific, measurable future outcome. Penalize generic news with no clear connection to a likely market.

2. POTENTIAL MARKET IMPACT (60%): Assuming a relevant market exists, how much could the information change its implied probability, price, or expectations before the market resolves? Consider the magnitude, novelty, credibility, specificity, and timing of the information.

## Essential rules

- Evaluate the information conveyed by the headline, not merely how dramatic its wording sounds.
- Distinguish a reported event from a forecast, rumor, opinion, or speculation.
- Do not assume that a market exists or that a news report is true.
- News about an already completed outcome receives little or no relevance for markets on that same outcome once they have resolved. However, it may still matter for other unresolved markets.
- Routine, expected, repetitive, or incremental developments generally have lower impact than unexpected developments.
- Major policy announcements, military escalations, credible ceasefire developments, unexpected economic data, corporate distress, and significant election developments can have high impact when relevant markets remain unresolved.
- A headline can be highly relevant but have low impact if it confirms what was already expected.
- A headline can be impactful for one market but irrelevant to most others.
- Judge only what can reasonably be inferred from the headline. Do not invent missing details, market prices, market existence, or facts.
- When uncertainty is high, avoid assigning an extreme score without supporting evidence.

## Output

Produce one numeric disruptiveness score from 0 to 100 for each headline. The score should reflect both market relevance and potential impact, with relevance weighted 40% and potential impact weighted 60%.

Use 0 for effectively irrelevant news and 100 for exceptional potential disruption to unresolved prediction-market expectations."""),
        "criteria": [str(i) for i in range(101)],
    }
}


def score_headlines(headlines: list[str]) -> list[int]:
    router = get_router()

    requests = [
        {
            "state": {"headline": headline},
            "questions": questions,
            "model": "multilingual",
        }
        for headline in headlines
    ]

    results = router.predict_batch(requests, batch_size=16)

    return [
        round(result["answers"]["disruptiveness"]["score"])
        for result in results
    ]


bet_questions = {
    "emotionality": {
        "type": "score",
        "instructions": (
            "Measure the emotional hype or wave-riding of a prediction market. "
            "Score 0..100 where higher means more emotionally charged, viral, or "
            "driven by hype rather than fundamentals."
        ),
        "criteria": [str(i) for i in range(101)],
    },
    "status_quo_deviation": {
        "type": "score",
        "instructions": (
            "Does this market deviate from the status quo? Return 1 if it "
            "deviates from the status quo, 0 otherwise."
        ),
        "criteria": ["0", "1"],
    },
}


def score_bet_emotionality_and_status_quo(markets: list[str]) -> list[tuple[int, int]]:
    """Score a list of markets for emotionality and status-quo deviation.

    Returns a list of ``(emotionality, status_quo_deviation)`` tuples. If Laya
    is unavailable (import error), returns a list of ``(None, None)`` tuples.
    """
    try:
        router = get_router()
    except Exception:  # Laya unavailable (import or load error)
        return [(None, None) for _ in markets]

    requests = [
        {
            "state": {"market": market},
            "questions": bet_questions,
            "model": "multilingual",
        }
        for market in markets
    ]

    try:
        results = router.predict_batch(requests, batch_size=16)
    except Exception:
        return [(None, None) for _ in markets]

    parsed: list[tuple[int, int]] = []
    for result in results:
        answers = result.get("answers", {}) if isinstance(result, dict) else {}
        emo_raw = answers.get("emotionality", {}).get("score")
        sq_raw = answers.get("status_quo_deviation", {}).get("score")
        emo = None if emo_raw is None else round(emo_raw)
        sq = None if sq_raw is None else round(sq_raw)
        parsed.append((emo, sq))
    return parsed


if __name__ == "__main__":
    headlines = [
        "Grocery prices across Europe : Where is food most expensive and why ?",
        "El tiempo en Coyhaique este sábado 24 de octubre de 2026",
        "ایران : دیگر اجازه نخواهیم داد شناورهای نظامی امریکا وارد خلیج فارس بشوند",
        "Consumer sentiment nears historic low , University of Michigan study finds",
        "Democrats for Mike Roger ad attacks El - Sayed on agenda , plan for Black Michiganders",
        "US has for years asked Musk to alter Starlink service in Ukraine , Middle East : Report",
        "Watch : Iran mocks Trump on busy Tehran street , shows US president taking nap behind bars",
        "Trump revives threat of US intervention in Cuba at Florida rally"
    ]

    scores = score_headlines(headlines)

    for headline, score in zip(headlines, scores):
        print(f"{score:3d}/100 | {headline}")
