# Methodology

How CouncilLens works, in the open. This is a living document: it grows as councils and topics are added, and the rules below are the ones the first council was actually built under.

## Sources
We use public information only: council agendas and minutes, consultation pages, open data / transparency pages, and published performance or spending data. Every published claim links to its source.

### Norwich City Council, licensing policy

Eighteen documents, every one fetched and read on 7 September 2026. The council's committee system is CMIS, its website runs on LocalGov Drupal, and its consultations run on EngagementHQ, branded Get Talking Norwich.

**What people were asked**

- [The consultation itself](https://gettalking.norwich.gov.uk/licensing) — open 18 May to 9 August 2026
- [Summary of changes to the licensing policy](https://gettalking.norwich.gov.uk/49713/widgets/150659/documents/105900/download) — the plain-English version residents were pointed at
- [The full draft policy](https://gettalking.norwich.gov.uk/49713/widgets/150659/documents/105901/download)

**What the council decided**

- [Licensing committee, 5 March 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1534/Committee/6/Default.aspx) — the agenda, plus the officer's report, three appendices (the draft policy, a table of changes, the equality impact assessment) and the minutes of both that meeting and the previous one
- [Licensing committee, 17 September 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1727/Committee/6/Default.aspx) — scheduled, no papers published yet
- [The committee's index of meetings](https://cmis.norwich.gov.uk/live/Committees/tabid/62/ctl/ViewCMIS_CommitteeDetails/mid/381/id/6/Default.aspx)

**What is actually in force**

- [The licensing policy approved in December 2021](https://www.norwich.gov.uk/downloads/file/2258/licensing_policy)
- [The premises licence page](https://www.norwich.gov.uk/licensing/premises-and-alcohol/premises-licence), the only place on the council's site that links it

**What it costs**

- [The General Fund budget and financial strategy for 2026-27](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1518/Committee/1/Default.aspx), taken to Cabinet on 11 February 2026 — section 2 only, because that is the part with the service-by-service table
- [The council's fees and charges book for 2026-27](https://www.norwich.gov.uk/sites/default/files/2026-06/Norwich-City-Council-Fees-and-Charges-2026-2027.pdf), which lists every licensing fee the council collects
- [Payments to suppliers over £500](https://www.norwich.gov.uk/your-council-explained/transparency-and-accountability/find-open-data/payments-over-500), the transparency-code dataset, with January 2026 banked as a worked example

Three pages were checked and deliberately left out, each with the reason recorded in `config/sources/norwich-city-council/licensing-policy.yaml`: the consultations hub, which had dropped the closed licensing consultation by September; the e-petitions page, which carries no licensing petition; and the policies and strategies list, whose entry labelled "Licensing Policy" actually links a different policy about houses in multiple occupation. Banking that one would have caused exactly the confusion this project exists to prevent.

### Norwich City Council, housing allocations

Eleven documents, every one fetched and read on 7 September 2026. Norwich owns and manages its own council housing, and the law requires it to publish a scheme saying who qualifies for a home and in what order. That scheme is called Home Options, and this topic follows one round of its review from consultation to adoption. The decision went to Cabinet, with the Scrutiny committee looking at it first.

**What people were asked**

- [The consultation itself](https://gettalking.norwich.gov.uk/homelessnessandallocations) — open from 10 November 2025, covering the homelessness strategy at the same time, and now carrying the council's "you said, we did" update
- [The briefing note](https://gettalking.norwich.gov.uk/42605/widgets/135103/documents/94937/download) — the plain-English version residents were pointed at
- [The full draft scheme](https://gettalking.norwich.gov.uk/42605/widgets/135103/documents/94939/download) and [the equality impact assessment](https://gettalking.norwich.gov.uk/42605/widgets/135103/documents/94938/download)

**What the council decided**

- [Scrutiny committee, 15 January 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1561/Committee/4/Default.aspx) — the agenda and the minutes, which record the questions members put and the only change they pressed for
- [Cabinet, 11 February 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1518/Committee/1/Default.aspx) — the agenda and the officer's report, whose appendices carry the proposed scheme, the equality impact assessment and the consultation figures
- The minutes of that Cabinet meeting, which the 11 February page carries and which CMIS also lists under [the next meeting, on 11 March 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1530/Committee/1/Default.aspx), where they were confirmed. We fetched them from the March page

**What is actually in force**

- [The Home Options Allocation Scheme 2026](https://www.norwich.gov.uk/your-council-explained/policies-plans-and-strategies/home-options-allocation-scheme-2026), published the day after Cabinet agreed it
- [The page you apply through](https://www.norwich.gov.uk/housing-and-community-safety/housing-advice-and-homelessness/applying-housing-norwich), which states the new two-year residence rule, so the new rules are the ones an applicant meets today — though the page carries no date, so we cannot say when it changed

Two pages were checked and left out, with the reason recorded in `config/sources/norwich-city-council/housing-allocations.yaml`: the index of adopted policies, which is a signpost rather than evidence about allocations, and the older allocation-scheme address the Cabinet report itself links to, which returns "Access denied" to the public. The second is left in the config rather than deleted, because a council report pointing residents at a page they cannot open is worth recording.

## Linkage tiers
The hardest question in accountability is whether feedback actually changed a decision. We never imply a connection we cannot evidence. Every feedback ↔ decision comparison is labelled:

- 🟢 **Confirmed** — the council's own record cites the feedback.
- 🟡 **Possible** — the feedback preceded the decision on the same topic, but causation is **not** confirmed.
- ⚪ **No link found** — no documented relationship.

Default to 🟡 or ⚪ unless the records establish 🟢.

## Summarising documents
AI assists with bounded tasks only: summarising minutes, tagging topics, comparing feedback / decisions / outcomes, and flagging missing or conflicting evidence. It never decides what a council should have done, and it is never asked an open question about a council.

These are the rules the summaries follow.

**One document at a time.** A summary describes the document it is written from and nothing else. It says what the document is, then what it says. Two to four sentences.

**Plain English.** Write for a resident, not a committee clerk. "Hot food sold after 11pm", not "late night refreshment". Where a council's own term has to appear — a statutory phrase, a committee name — it is explained the first time.

**No adjectives about performance.** We do not call a council slow, thorough, transparent or evasive. Dates and documents carry the story. Nothing on the site scores or attacks a politician, and nothing takes a side on whether a policy is a good idea.

**Stages, not tags.** Every document is filed at one of three stages (feedback, decision, outcome), and that comes from the source config, where a human set it, not from the model's reading. An entry on the timeline gets the stage of the thing that happened.

**Causation is never inferred.** A summary may say a committee resolved something, because the minutes say so. It may not say a consultation caused a change. That judgement only ever appears as a linkage tier, with the evidence quoted.

**Dates are as precise as the record, and no more.** A minuted meeting gets a day. A policy whose front page says "December 2021" gets a month, and the timeline says so. Something with no date gets none. Where a council's own documents disagree, we use what happened and note the difference rather than quietly picking one. Norwich's officer report proposed consulting from 11 May to 7 August 2026; the consultation actually ran 18 May to 9 August.

**Numbers come from the document.** 67 responses, 677 premises licences, 79 pages. If a figure is not in a source, it is not on the site.

**What we could not find is published too.** Every gap says what was looked for, where, and what was there instead. An empty meeting page is evidence, and we link it.

### Confidence

Each AI output carries `high`, `medium` or `low`. It describes how well the cited sources support the reading, nothing else:

- **high** — the document states it outright.
- **medium** — assembled from several places, or read in part because the document runs to 140,000 characters.
- **low** — the sources are thin, or the output has been flagged because a document it was written from has changed since.

Confidence is not a prediction. A note that a council intends to do something in November can be `high`, because the intention is documented, while the thing itself stays in the "still waiting" column.

### Every AI output stores
- Source document IDs
- Prompt version
- Model name / version
- Confidence or review flag
- Timestamp

### Review status
Every item on the site carries one of three labels, and the label says exactly who has checked it:

- **needs_review** — written by the model and not yet checked by anything else.
- **ai_reviewed** — checked against the source documents by a second, independent AI review, not by a person.
- **reviewed** — checked by a person, who is named.

In this early build, every published item has been through two independent AI reviews against the source
documents, and the two reviews have been reconciled item by item, going back to the documents wherever the
reviewers disagreed. That is what `ai_reviewed` means, and it is not the same as human review. Human review is
still to come. Until it happens, the label on each item tells you which of the three states it is in — we would
rather say "no person has read this yet" than let you assume one has.

## Figures
The numbers shown at a glance on a topic page all come from documents in the archive. Each carries the document it came from, the period it covers and a plain sentence saying what it does and does not mean, and every one links straight to its source. Three rules govern them.

**We never estimate.** A number is on the site because a public document states it. Nothing is calculated, averaged, projected, or scaled up from something smaller. If a figure would only exist after doing arithmetic across two documents, it does not go on the site, and the gap records what we were looking for.

**Money is quoted as the council published it.** District councils budget by service group rather than by team, and Norwich is no exception: its 2026-27 General Fund budget puts licensing inside planning and regulatory services. So the money on the licensing page is that group's money, £5.44m of spending against £2.45m of income, and the note says as much rather than implying a licensing-only figure that nobody has published. We went looking for one in the budget book and again in the payments-over-£500 data. Neither has it. Both absences are written up as gaps.

**Licence fees are set by Parliament, not by Norwich.** The amounts in the fees and charges book, £100 to apply for the smallest premises licence and £70 to £1,050 a year to keep it, come from regulations made under the Licensing Act 2003 and are the same in every licensing authority in England and Wales. Norwich publishes them and collects them. It cannot move them. Anyone who wants them changed needs to take that up with the government.

Figures carry the same provenance block as every other AI output and start life flagged for human review. Where a draft document gives a number in square brackets, which is how Norwich marks a figure it has yet to settle, we leave it out rather than dress up a placeholder as a decision.

### Norwich City Council, council finances

Eighteen documents, fetched and read on 8 September 2026. This is the money topic, and it follows one annual cycle: the budget consultation each December, Cabinet and Budget Council each February, and the outturn in the accounts the following summer.

**What people were asked**

- [The budget consultation for 2026-27](https://gettalking.norwich.gov.uk/budget2026-27) — open 4 December 2025 to 18 January 2026, promoted by text alert to 120,000 residents, 899 replies

**What the council decided**

- [Cabinet, 11 February 2026](https://cmis.norwich.gov.uk/live/Meetingscalendar/tabid/70/ctl/ViewMeetingPublic/mid/397/Meeting/1518/Committee/1/Default.aspx) — section 2 of the budget report: the General Fund budget and financial strategy for 2026-27, with the consultation result printed in full as Appendix 2(F)
- Cabinet, 5 February 2025 — the same report for 2025-26, which is where the £5.5m minimum reserve and the £3.2m savings figure come from
- Budget Council, 24 February 2026 — the statutory council tax resolution setting Band D at £315.26, and the amendments the political groups tabled
- [The council's own guide to its budget](https://www.norwich.gov.uk/your-council-explained/transparency-and-accountability/norwich-city-council-budget-2026-27-what-you)

**What actually happened**

- [The Statements of Accounts](https://www.norwich.gov.uk/your-council-explained/transparency-and-accountability/statement-accounts) for 2021-22 to 2025-26, plus the audit certificate for 2024-25. The narrative report at the front of each one carries the variance against budget and the capital outturn, and those are the numbers every money measure uses.
- [The treasury management strategy for 2026-27](https://www.norwich.gov.uk/sites/default/files/2026-03/Treasury-Management-Strategy-2026-2027.pdf) — the borrowing limits full Council sets, and the council's own commercial income indicator
- [The corporate performance report for quarter 1 of 2025-26](https://www.norwich.gov.uk/downloads/file/11006/corporate_performance_report_for_quarter_1_2025-26), and [the index of every performance report](https://www.norwich.gov.uk/your-council-explained/transparency-and-accountability/performance-reports)

Two decisions worth recording. The provisional outturn reports to Cabinet each June are small and would have been the obvious thing to bank, but their figures are provisional and do not match the accounts — for 2025-26 the June report gives a General Fund underspend of £543,000 where the accounts give £710,000 — so the accounts are cited throughout and the difference is written up as a gap. And the accounts before 2021-22 are published by the council but are not banked here, to keep the repository a sensible size; that too is a gap rather than a silence.

## How a red, amber or green status is worked out

Every status on this site is produced by a rule, applied by code, comparing the council's own numbers against each other. The rules are written out in full in [scoring.md](scoring.md), which is generated from the docstrings in `src/analyse/rules.py` on every build — so the wording published on the site is the wording of the function that produced the colour, and the two cannot drift apart.

Norwich publishes its own traffic-light framework: a target and an intervention level for every corporate indicator, reported to Cabinet each quarter. Where it does, the `council-threshold-v1` rule uses both, so the colour here is the colour on the council's own dashboard rather than one of our devising. Where a council publishes a target but no intervention level, `target-met-v1` applies a 10% band. Where the council publishes neither, the measure is grey and says so.

Grey is a first-class answer. Eight of the forty-three measures currently on the site are grey, and most of them are about the same thing: Norwich publishes the savings it has identified when it sets a budget, and never publishes how much of that was actually delivered. That is the most obvious accountability question about a council's money and it cannot be answered from Norwich's published papers.

One honest caveat about the target measures. The council's quarterly report carries the numbers in an appendix of dashboard screenshots rather than as text, so they cannot be checked by machine. They were read off the images by eye and every one is flagged for human review.

## Reproducibility
AI outputs are cached and versioned. The published site can be regenerated byte-for-byte from those cached outputs plus the raw inputs, even though the model itself is not deterministic.

## Corrections
Anyone can request a correction or removal by opening an issue or contacting the maintainers. Response-time target: we aim to acknowledge within 2 working days and resolve or explain within 10 working days.

## Data protection
Some public documents contain personal data. We process only what is necessary, redact where appropriate, and provide a removal route.

Everything CouncilLens holds was already published by the council on a public web page. We do not scrape anything behind a login, we do not buy data, and we do not combine council records with anything else to build a picture of a person.

Officers and councillors are named where the council names them, in the role they hold. The minutes of a public meeting record who presented a report and what the committee resolved, and that is the accountability record. We keep those names as published. We do not comment on individuals, and we do not collect anything about their private lives.

Residents are treated differently. Consultation responses are the clearest case: we will say how many people replied and what the council was asking, but we do not reproduce individual responses, names, addresses, email addresses or anything else that could identify someone who took part. Where a council publishes a response in full, we link to the council's page rather than copying it here. The same goes for anyone named in a licensing objection or a complaint. If a document we have saved turns out to contain personal data the council did not intend to publish, we remove it from the archive and tell the council.

Removal works the same way as a correction. Open an issue on the repository, or contact the maintainers, saying which page or document is involved and what the problem is. The response times below apply. If the material is on the council's own site as well, we will say so. Taking it off CouncilLens does not take it off the council's website; that request has to go to the council, and we will point you to the right place.
