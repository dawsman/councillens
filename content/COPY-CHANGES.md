# Proposed copy changes

Every string on this list is one a reader sees. I have left the pipeline vocabulary alone, and I
have not touched anything inside `data/` or `src/` beyond noting where the string lives.

Three rules I applied:

- **Cut the abstract noun.** "Accountability", "authority", "provenance" and "build" all have
  concrete everyday equivalents, and the concrete word is always shorter.
- **One idea per sentence.** Where a sentence carried two, I split it. This is what moves the
  reading age more than vocabulary does.
- **Say the date, not the jargon.** "Drawn as at" and "as of" are formal register with no meaning a
  13-year-old can recover.

Nothing here changes what the site claims. If a proposed string does change a claim, I have said so
in the reason column and flagged it for the lead.

## The five that matter most

If only five get applied, apply these. They are the strings that appear on every page, or that carry
the site's central promise.

| # | File | Current | Proposed | Reason |
|---|---|---|---|---|
| 1 | `_parts.html` provenance macro + `build.py` `provenance()` | Written by claude-opus-5 (agent session) on 2026-09-07, confidence medium, **checked against the source documents by a second, independent AI review; not yet by a person**. | Written by AI on 7 September 2026. A second AI has checked it line by line against the council's documents. No person has checked it yet. | Appears under every card on the site, so it is the most-read sentence we have. It currently runs to 27 words with a semicolon, an internal model name and a raw ISO date. Split into three short sentences it reads at about age 11. |
| 2 | `base.html` footer | CouncilLens is for transparency and public discussion. It does not make legal findings or accuse anyone of wrongdoing. | CouncilLens exists so anyone can see the record and argue about it. We do not accuse anyone of breaking the law. | On every page. "Transparency", "legal findings" and "wrongdoing" are three abstract terms in twenty words. The replacement says the same thing and is harder to misread. |
| 3 | `home.html` honesty section intro | The hard part of accountability is knowing whether feedback actually changed a decision. Usually nobody writes that down. Rather than guess, we label every connection, and you can see the evidence behind the label. | The hard part is knowing whether what people said actually changed the decision. Usually nobody writes that down. So rather than guess, we label every link with how much evidence stands behind it, and show you that evidence. | This paragraph is the site's whole premise. "Accountability" and "feedback" are both replaceable with words a reader already owns. |
| 4 | `_viz.html` tracker | Drawn as at 8 September 2026, the day this page was last built. | This shows the record as it stood on 8 September 2026, the day we last built the page. | "Drawn as at" is formal register that carries no meaning for the target reader, and the sentence has no verb they can see. |
| 5 | `base.html` masthead nav | How we work · Corrections | How we work · Learn · Words explained · Corrections | The glossary and the Learn section are useless if nothing links to them. Two new nav items, both plain nouns. Needs the designer to add the routes. |

## Home page (`home.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `home.html` `<h1>` | See how your council listens | See how your council listens | No change. Six words, active verb, and it says what the site is for. |
| `home.html` lede | Your council publishes a lot: meeting notes, consultations, reports. It is all public, and almost none of it is written for you. | Your council publishes a lot. Meeting notes, consultations, reports. All of it is public and almost none of it is written for you. | Splitting the colon sentence drops the average sentence length without losing the rhythm. |
| `home.html` lede | CouncilLens gathers it, puts it in plain English, and lines it up so you can see one thing clearly — what people asked for, what the council decided, and what actually happened. | We gather it, put it in plain English, and line it up so you can see one thing clearly: what people asked for, what the council decided, and what actually happened. | First person is warmer and shorter. The dash becomes a colon; the site uses a lot of dashes and they read as pauses a struggling reader cannot hear. |
| `home.html` councils heading | Councils we cover | Councils we cover | No change. |
| `home.html` honesty heading | What we will and won't claim | What we will and won't say | "Claim" is a slightly legal word in this context. "Say" carries it. |
| `home.html` closing | We would rather tell you we don't know than mislead you. Everything on this site links to the original public document, so you never have to take our word for anything. | We would rather tell you we don't know than mislead you. Every page links to the council's own document, so you never have to take our word for anything. | "Original public document" is three words doing one word's work. |
| `home.html` empty state | No councils are published yet. This is an early build — the first council and topic are on the way. | No councils are published yet. This is an early version, and the first council and topic are on the way. | "Build" is developer vocabulary. Also removes a dash. |

## Council page (`council.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `council.html` lede | What this council was asked for, what it decided, and what happened afterwards — put together from its own published documents. | What this council was asked for, what it decided, and what happened next. All of it comes from its own published documents. | Two sentences instead of one dash-joined sentence of 22 words. |
| `council.html` remit heading | What this council is actually in charge of | What this council is actually in charge of | No change. This is the best heading on the site. |
| `council.html` remit note | This matters: if a problem sits with a different authority, this council cannot fix it however many people ask. | This matters. If a problem belongs to a different council, this one cannot fix it, however many people ask. | "Authority" means council here, so say council. |
| `council.html` topics heading | Topics we have looked at | Topics we have looked at | No change. |
| `council.html` correction prompt | We would rather be corrected than be wrong in public. | We would rather be corrected than be wrong in public. | No change. Eleven words and it earns them. |

## Topic page (`topic.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `topic.html` record intro | Every card below links to the council document it came from. Where feedback and a decision are joined, we say how sure we are — and show the words the council used. | Every card below links to the council document it came from. Where we think a decision answers something people asked for, we say how sure we are, and show the words the council used. | "Feedback and a decision are joined" is passive and abstract. Also removes a dash. |
| `topic.html` gaps heading | What we looked for and couldn't find | What we looked for and couldn't find | No change. |
| `topic.html` gaps intro | Missing information matters as much as the rest. These are the things we went looking for in the public record and did not find. | What is missing matters as much as what is here. These are the things we went looking for and did not find. | "Missing information" and "the public record" are both replaceable. Fourteen words saved. |
| `topic.html` sources intro | 18 public documents. Nothing on this page comes from anywhere else. | 18 public documents. Nothing on this page comes from anywhere else. | No change. |
| `topic.html` on-page nav label | Further down this page | Further down this page | No change. |
| `topic.html` correction prompt | If we have got something wrong, missed a document, or named you and you would rather we didn't, tell us and we will look at it. | If we have got something wrong, missed a document, or named you when you would rather we hadn't, tell us. We will look at it. | Split into two. The list of three clauses before the main verb is the hard part, not the words. |
| `topic.html` empty stage | We have not found anything at this stage yet. | We have not found anything at this stage yet. | No change. |

## The at-a-glance layer (`_viz.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `_viz.html` tracker heading | Where this stands | Where this stands | No change. |
| `_viz.html` tracker, no next date | Nothing further is in the diary that we can find. | We cannot find anything else in the council's diary. | Active, and drops "further" and "in the diary that". |
| `_viz.html` figures heading | The numbers so far | The numbers so far | No change. |
| `_viz.html` figure source link | Where this comes from | Where this number comes from | One extra word, and it stops the link text being ambiguous when read alone by a screen reader. |
| `_viz.html` ribbon heading | How it has unfolded | How it happened, in order | "Unfolded" is a writerly verb. The replacement says what the picture shows. |
| `_viz.html` ribbon intro | Each marker is a document we found, in the order things happened. The time between them is written underneath. Anything to the right of today has not happened yet. | Each dot is a document we found, in the order things happened. The gap between them is written underneath. Anything to the right of today has not happened yet. | "Marker" is design vocabulary; the reader sees a dot. "Gap" beats "time between them". |
| `_viz.html` changes intro (not adopted) | Taken word for word from the council's own committee papers. None of it is settled: the draft has not been adopted, so the older policy below is still the one that counts. | Taken word for word from the council's own committee papers. None of it is settled. The draft has not been adopted, so the older policy below is still the one in force. | Splits a 26-word sentence. "In force" is worth teaching and is glossed. |
| `_viz.html` linkage summary intro | We checked 3 possible connections between feedback and a decision. Here is how far the council's own record backs each one up. | We checked 3 places where something people said might have changed a decision. Here is how far the council's own record backs each one up. | "Possible connections between feedback and a decision" is the pipeline's vocabulary, not a reader's. |
| `_viz.html` documents strip intro | Each square is one public document, numbered to match the list below. Follow a square to what we made of it, or the list below to the document itself. | Each square is one public document, numbered to match the list below. Click a square to see what we made of it. Use the list below to reach the document itself. | Three short sentences. The current second sentence asks the reader to hold two routes in mind at once. |
| `build.py` `STEP_STATE['done']` | On record | On record | No change. |
| `build.py` `STEP_STATE['superseded']` | Nothing new yet | Nothing new yet | No change. This one took several attempts to get right and it is right. |
| `build.py` `STATUS['unknown'].note` | The public record does not tell us where this stands. | The published documents do not tell us where this stands. | "The public record" appears six times across the site. Varying it to "the published documents" in at least half of them helps, because the phrase is doing a lot of unexplained work. |

## Link labels (`build.py` `TIER`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `build.py` `TIER['confirmed'].blurb` | The council's own record says this feedback shaped the decision. | The council's own document says this is what changed the decision. | "Feedback shaped the decision" is two abstractions in four words. |
| `build.py` `TIER['possible'].blurb` | The feedback came first, but nothing on record proves it caused the decision. | People said this before the decision was taken. Nothing written down proves it made any difference. | Two short sentences, and it states the causation problem in words a 13-year-old will follow. |
| `build.py` `TIER['none'].blurb` | We found nothing connecting this feedback to the decision. | We found nothing connecting what people said to what was decided. | Removes the last use of "feedback" as a noun on the public pages. |
| `build.py` `TIER` labels | Confirmed link / Possible link / No link found | Confirmed link / Possible link / No link found | No change. Tested wording, and the plural rule behind it is already fixed. |

## How we work (`methodology.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `methodology.html` lede | This page is generated straight from the methodology document in our code repository, so what you read here and what the project actually follows can't drift apart. | This page is built straight from the working document our team follows. What you read here and what we actually do cannot say different things. | "Generated", "methodology document", "code repository" and "drift apart" is four pieces of jargon in one sentence, on the page most likely to be read by someone checking whether to trust us. |
| `methodology.html` link note | See this document in the repository, including every change ever made to it. | See this document on GitHub, including every change ever made to it. | "Repository" means nothing outside software. GitHub at least names a place. |
| `methodology.html` correction prompt | Our method is open to argument as much as our facts are. | You can argue with how we work, not only with what we say. | Active, concrete, and it invites the thing we want. |

## Corrections (`corrections.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `corrections.html` lede | We'd rather be corrected than be wrong in public. If something on this site is wrong, out of date, missing, or about you and shouldn't be here, tell us. | We'd rather be corrected than be wrong in public. Tell us if something here is wrong, out of date, missing, or about you and should not be here. | Putting the verb first turns a 24-word conditional into an instruction. |
| `corrections.html` GitHub note | Open a correction request on GitHub. It's a short form, it's free, and you'll need a GitHub account to use it. | Open a correction request on GitHub. It is a short form and it is free. You will need a GitHub account. | Three facts, three sentences. The current version buries the account requirement at the end of a list. |
| `corrections.html` timing | We aim to respond within 10 working days. | We aim to reply within 10 working days. | "Respond" for "reply" with no gain. |
| `corrections.html` naming section | We only ever use documents the council has already published. But "already public" isn't the same as "fine to repeat", and we treat those as different questions. | We only ever use documents the council has already published. But "already public" is not the same as "fine to repeat", and we treat those as two different questions. | Small. The added "two" makes the sentence parse on first reading. |

## Sitewide notice (`base.html`)

| File | Current | Proposed | Reason |
|---|---|---|---|
| `base.html` fixture notice | **Example data.** This build was made from a sample file so the pages could be designed and tested. Anything here that looks like a council record is illustrative, not real. | **Example data.** These pages were made from a sample file, so the design could be tested. Anything here that looks like a council record is made up. | "Build" and "illustrative" both go. "Made up" is unambiguous and slightly alarming, which is correct for this banner. |
| `base.html` build line | Built 8 September 2026 from public documents. Open source, MIT licensed. | Built 8 September 2026 from public documents. The code and the data are free for anyone to use. | "Open source, MIT licensed" means nothing to the audience. Keep the licence in the footer link, say what it means here. |

## New strings needed

These do not exist yet. The designer will need them if the glossary and Learn section go live.

| Where | Proposed string | Note |
|---|---|---|
| Glossary page title | Words explained | Not "Glossary". Two syllables saved and no one has to know the word. |
| Glossary page lede | Council documents are full of words that mean something specific. Here is what each one means, with a Norwich example wherever we have one. | |
| Inline term marker | (dotted underline, no label) | The popover carries the `short` field from `content/glossary.yaml`. No "click here". |
| Popover footer link | Read more about this word | Links to the full entry on the glossary page. |
| Learn section title | Learn | |
| Learn lede | A short course in how your council works, built around real documents you can open yourself. | |
| Scorecard status words | Met · Close · Missed · Can't tell | Already specified in the wave 4 brief. Repeated here so the strings live in one place. |
| Scorecard rule link | How this status was worked out | Never "methodology" and never "see rule". |
