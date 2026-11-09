
from laya import Router

# Load the multilingual model once and keep it available.
router = Router(default="multilingual")
router.preload(["multilingual"])

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

Use 0 for effectively irrelevant news and 100 for exceptional potential disruption to unresolved prediction-market expectations."""
        ),
        "criteria": [str(i) for i in range(101)],
    }
}


def score_headlines(headlines: list[str]) -> list[int]:
    requests = [
        {
            "state": {"headline": headline},
            "questions": questions,
            "model": "multilingual",
        }
        for headline in headlines
    ]

    results = router.predict_batch(requests, batch_size=64)

    return [
        round(result["answers"]["disruptiveness"]["score"])
        for result in results
    ]


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
