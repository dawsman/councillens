# Rendering "Who decides" — a spec for the designer

This is the brief for turning `data/analysed/<council-slug>/people.json` into a
page. It covers what the page is for, what goes on it, the wording that is not
negotiable, and the things it must never do.

The model it renders is defined in `data/schemas/people.schema.json` and built by
`src/analyse/build_people.py`. Nothing on the page may be computed from anywhere
else.

## What the page is for

Every other page on this site ends at the same question. The council decided
something — who are *they*?

So: one page per council, at `/councils/<council-slug>/who-decides/`, answering
five things a resident actually asks.

1. Who is on the council, and which party runs it?
2. How long has my councillor been there?
3. What jobs do they hold — cabinet, chair of something, leader?
4. What have they told the council about themselves, and about the money and
   organisations they are connected to?
5. Who are the paid people in charge, and what are they paid?

A reader arriving from a topic page wants the fourth and fifth of those, fast.
A reader arriving from the home page wants the first.

## The five blocks, in order

### 1. Composition bar

One horizontal stacked bar, full width, one segment per party, sized by seats.
Above it: the plain sentence from `composition.summary`. Below it: a legend
giving party, seat count and share, and the `as_of` date in words ("as the
council's own directory listed it on 8 September 2026").

The bar is the only chart on the page. Give each party a colour, but never rely
on colour alone: every segment carries its seat count as text, and the legend
repeats it. Colours should be recognisable without being campaign material —
muted, one weight, no gradients.

If `composition.next_election` is set, a short line under the bar: "The next
election is on <date>." If it is null, say nothing. Do not calculate it.

### 2. Councillor cards

A responsive grid. Each card, collapsed, shows only what a resident scanning for
their own councillor needs:

- name (`name`, as published)
- ward (`ward`) — the biggest thing on the card after the name
- party (`party`) as a small text label, colour-matched to the bar. Match on the
  exact string: `composition.seats_by_party[].party` and `councillors[].party` use
  the same labels, and "The Green Party" is not "Green Party"
- one line: "Councillor since <first_elected, formatted to its precision>"
- where `party_history` is not empty, the current party label carries a small
  marker, and the expanded card gives the dated history. Three of Norwich's 39
  changed party while in office, and a card that pairs "Independent" with
  "councillor since 2016" invites a reading the council's own record contradicts
- any `roles`, as small pills: "Leader of the council", "Chair, Licensing
  committee"

Sort by ward, then surname, and let the reader re-sort by party. Provide a filter
by ward and a search box that matches name and ward. No ranking, ever: no "most
active", no "longest serving" leaderboard. Sorting is for finding a person, not
for comparing them.

Expanding a card reveals four sections, in this order:

**Their council jobs.** `roles` and `committees` as a plain list, each with the
date they joined where the record gives one. Committee names link to the
committee block further down the page.

**What they have declared.** `interests`, grouped under the headings the register
itself uses: employment, directorships, memberships, sponsorship, land. Each item
verbatim from the register.

Expect most of these to be thin, and show `interests.note` whether they are or
not. For Norwich it is the most important line in the section. Of the 39
registers, 22 are published as scanned pictures with no text in the file, so
nothing from them can be shown at all. The 17 readable ones sit on two different
versions of the council's form. Six are on the February 2016 form, which has a
single column for the councillor's own interests, and everything on those is
shown. Eleven are on the April 2026 form, which puts a councillor's answers
beside their partner's in the pecuniary table; where such a row lists more than
one answer, it is left out rather than risk printing a partner's job under a
councillor's name. On both forms the "other registrable interests" box is a
single list with no partner column, so it is always shown in full. Each note says
which form that councillor is on and what, if anything, is missing from their
entry. Never render an empty declarations box as though the councillor declared
nothing.

Above the list, always, this sentence:

> This is what the councillor declared about themselves, in their own words. Every
> councillor has to fill in this form by law. It is not a list of accusations, and
> nothing on it means anything has gone wrong.

Then the register's date and a link to the register itself. If `interests` is
empty, do not show an empty box: show the `interests.note` instead, which says
what the council does and does not publish.

**Turning up.** `attendance` as one sentence and one small bar: "Went to
<attended> of the <expected> meetings they were expected at, in <period>. Of the
<expected − attended> they missed, <apologies> were with apologies." Both halves,
always, wherever `apologies` is not null. The council publishes an absence figure
and an apologies figure, and showing only the first makes a councillor who
apologised for every absence look like one who could not be bothered. Four of
Norwich's 39 are in exactly that position. Then the `note`, always, because the
period is a rolling window and the reader will otherwise assume it is a year of
their own choosing. If `attendance` is null, print the matching line from `gaps`.
Never a zero, never a dash.

**What they are paid.** `allowances` as one sentence: "Basic allowance £<basic>
in <year>. Total paid, £<total>." Show `special_responsibility` only when it is
not null, and for Norwich it never is: the published schedule has four money
columns and prints figures in three of them, so the middle figure cannot be told
apart from expenses. Do not label it, do not infer it from whether the councillor
holds a role, and do not quietly present the total as though it were all basic
allowance. Follow with one line of context: an allowance is not a salary, and the
amounts are set by the council on the advice of an independent panel. Always show
`allowances.note`. If `allowances` is null, say the council publishes no figure
for that councillor and give the reason from `gaps` — usually that they were not
in office in the year the schedule covers.

Under all four, `source_urls` as "Where this comes from", and the standard AI
provenance chip the rest of the site already uses.

### 3. Senior officers

Not cards. A simple table or definition list, because there are few of them and
the reader is scanning for a role, not a face:

| Role | Name | Statutory duty | Pay band |

`statutory_role` is rendered in words, with the explanation inline on first use —
"Section 151 officer (the person legally responsible for the council's finances)".
Where `name` is null, print "the council does not publish who holds this post"
rather than leaving the cell blank. Where `pay_band` is null, the same.

Officers are employees, not politicians. The page carries no photographs of them,
no biography, and no history. Role, name if published, duty, band. That is all.

### 4. Committee blocks

One block per entry in `bodies`, anchored so a topic page can deep-link it
(`#committee-licensing-committee`). Each block:

- name and `purpose` in one sentence
- chair, then vice chair, then members, each linking back up to their card
- a link to the committee's own page on the council's site

**These blocks are the reusable part.** A topic page should be able to embed one:
"The Licensing committee decided this. It is these ten councillors." Build them as
a partial the topic template can include by slug, not as page-only markup.

### 5. What we could not find

`gaps`, rendered exactly as the rest of the site renders gaps, grouped by `area`.
This block is not an apology. It is the most honest thing on the page, and it goes
above the footer, not hidden behind a toggle.

## The privacy notice

This goes at the top of the page, under the title, before the composition bar.
Not in a footer, not behind a link. A page that names thirty-nine living people
has to say up front where it got them and what a person can do about it.

Use the wording below. Two blocks, both open on the page. The first is the one
everybody reads. The second is longer and duller, and it is the one that answers
a complaint.

> **About this page**
>
> Everything here comes from Norwich City Council's own records, or from what
> councillors have declared about themselves. We haven't gone looking anywhere
> else. No social media. No news reports, no company databases, nothing pieced
> together from someone's name.
>
> Councillors have to declare, by law, things that might affect the decisions
> they take: a job, a directorship, land, help with election costs. They fill
> that form in themselves and the council publishes it. We reproduce it. We
> don't interpret it, and a declaration is the system working rather than
> evidence of anything.
>
> We don't score anyone. There's no league table here, no "best" or "worst"
> councillor, no opinion about how anyone has voted. If a number looks bad, it's
> the council's number, and the caveat beside it is the council's caveat.
>
> Where we couldn't find something, we say so instead of guessing.

> **About the personal information on this page**
>
> **Who we are.** CouncilLens is an independent project. It isn't part of any
> council and nobody pays for it. Write to the correction form on GitHub (a private address will follow after alpha) and a person will
> read it.
>
> **What we publish, and where each part comes from.** All of it is already
> published by the council about the people who run it:
>
> - names, wards, parties, and every term served, from the council's own
>   councillor directory;
> - votes and majorities, from the council's published election results;
> - committee places, roles and meeting attendance, from the council's committee
>   system;
> - registers of interests, which councillors write out themselves and the
>   council publishes because the Localism Act 2011 makes it publish them;
> - allowances paid, published every year under the Local Authorities (Members'
>   Allowances) (England) Regulations 2003;
> - senior officers' posts and published pay bands, under the Local Government
>   Transparency Code.
>
> None of it came from the people named here. It came from their council. When
> information about someone is collected from somewhere other than that person,
> data protection law says they should be told what has happened to it, and this
> block is us telling them. (That rule is Article 14 of the UK GDPR.)
>
> **Why we think we may publish it.** Our lawful basis is legitimate interests,
> Article 6(1)(f). The interest is plain enough: you should be able to find out
> who decides things where you live, what they have declared about themselves,
> and whether they turn up. Weighed against that is what it costs the people
> named, and we think it is small. They hold public office and stood for it.
> Every line here is about the office, not the person. We carry no home
> addresses, no personal phone numbers, nothing about family or health, and
> nothing about anyone's partner; where a register names a street, the street
> does not reach this page. Officers didn't stand for anything, so we publish
> less about them: the post, the published pay band, the duty the law gives it.
> Nothing here is a comment on how anyone has done their job.
>
> We're aware that gathering scattered records into one searchable profile is
> not quite the same as the council publishing them separately, and that is
> exactly the thing a reader might object to. It is also the only reason the
> page is any use. So the answer we've settled on is to publish only what the
> council publishes, to link every line back to it, and to take something down
> while we look into it rather than afterwards.
>
> **Parties and unions.** Which party a councillor belongs to is on every card,
> and a few registers name a trade union. Both count as special category data,
> the kind the law protects most tightly. We publish them because the councillor
> published them: each one wrote the entry on a public register, under their own
> name, knowing the council would put it online. That is the condition in
> Article 9(2)(e), information made public by the person it is about. We rely on
> nothing else, and we never infer either from anything.
>
> **Keeping it right.** Records go stale, and a stale record about a person is a
> wrong one. We refresh this page from the council's records and check it again
> every year, after the May elections. The date it was last checked is at the
> foot of the page.
>
> **How long we keep it.** When someone stops being a councillor, their card
> comes off this page within 30 days. What stays is the project's working
> history, in the public code repository, because that is what lets anyone check
> what the page said on a given day. Nothing about a former councillor stays on
> the live page.
>
> **Getting something changed, or taken down.** If you are a councillor or an
> officer and something here is out of date, incomplete, or attributed to the
> wrong person, tell us. [Ask for a correction](<corrections_url>) if you're
> happy to do it in the open, or email the correction form on GitHub (a private address will follow after alpha) if you'd rather not. We
> aim to fix factual errors within five working days and we keep a note of what
> changed.
>
> You can also ask us to remove or restrict what we show about you, or object to
> it being here at all. Say what you want removed and we will take it down
> within five working days, then reply telling you what we did. If we think it
> should go back up because the council itself still publishes it, we'll say so
> and explain why. If the council stops publishing something, we stop too.
>
> **If we get it wrong.** You can complain to the Information Commissioner's
> Office at ico.org.uk, and you don't have to come to us first.

Three notes for whoever owns this page, and none of them are the designer's to
settle.

**This is a draft, not legal advice.** It was written by an AI agent working
from what the two review passes found, and every bit of it needs confirming by
someone qualified before the page goes live. The parts most worth a second
opinion are the legitimate interests balance, the Article 9(2)(e) reasoning for
party and union membership, and whether a short data protection impact
assessment ought to sit behind it. A structured record about thirty-nine named
people is the shape of thing a regulator asks about first, and two pages of
working would be the best possible answer.

**The removal address has to work.** `the correction form on GitHub (a private address will follow after alpha)` is a placeholder. The
page names living people, so it cannot go up without an inbox somebody reads and
acts on. A public GitHub issue is fine for "you've got my ward wrong". It is not
fine for "please take my name down", which shouldn't require posting in public.

**Decide about search engines on purpose.** Whether these pages are indexed is a
real choice with real consequences for the people on them, and it should be made
deliberately and written down, not left to whatever the static site does by
default.

## Rules that are not style preferences

- **Never fetch a `declared_links` URL.** If a councillor's own website is listed,
  print it as the council prints it, and mark it clearly as their own site, not
  ours. Do not preview it, do not screenshot it, do not summarise it. For Norwich
  the array is empty for all 39: the council publishes no personal websites or
  social accounts, so nothing renders.
- **No photographs of councillors** in the first version. The council publishes
  them, but a face on a card changes what the page feels like, and a page about
  power should read like a record, not a lineup.
- **No home addresses, no personal phone numbers, no family, no health.** The
  model does not carry them; the template must not reintroduce them from any
  other source.
- **Land interests stay at ward level.** If a register names a street, that street
  does not reach the page.
- **No derived judgements.** Do not compute an attendance rank, a "declarations
  count", or a longest-serving list. Counting is a kind of opinion once it is put
  in an order.
- **Every AI-written line keeps its provenance chip**, and anything still
  `needs_review` is labelled as such in the same words the topic pages use.

## Reading level

Same target as the rest of the site: a confident thirteen-year-old should get
through it without stopping. Short sentences. "Councillor" not "elected member".
"Job" not "employment interest". Explain a term the first time it appears, in
brackets, in six words or fewer.

## Where the page sits

- Linked from the council page, prominently.
- Linked from every topic page, from the committee that made the decision.
- Linked from the home page as one of the council's standing pages.
- URL: `/councils/<council-slug>/who-decides/`, relative links throughout, because
  the site is served from `/councillens/`.


## Before this page goes live

**A first pass by a person.** Two independent AI review passes have now checked
every entry against the source documents, and the model records that as
`ai_reviewed` with who checked it and when. Two entries stayed `needs_review`
because the council's own record cannot settle them: Richard Lawes's 2025
majority of one vote, on a results table that prints no count for one candidate,
and the chair of the treasury management committee, which the committee system
shows two councillors holding. A person still has to read this page before it
goes up. `ai_reviewed` means checked twice against the documents, not signed off.

The removal address and the search-engine decision are covered under the privacy
notice above, and both have to be settled first.

## What Norwich publishes, and what it does not

Useful context for anyone designing the page, and the reason several blocks have
to degrade gracefully.

| | Norwich |
|---|---|
| Councillor directory | Yes — 39 councillors, in the committee system |
| First elected, every term served | Yes, per councillor |
| Committee places, with joining dates | Yes, in full, once the committee system's paging is followed |
| Outside body appointments | Yes, in full, once the committee system's paging is followed |
| Attendance | Yes: expected, attended, absent and apologies received, rolling twelve months |
| Register of interests | Yes, but 22 of 39 as scans; two form versions; no index page; each one behind a form button |
| Allowances actually paid | Yes, per councillor, to 2024-25, by surname and initial |
| Election results | Yes, per ward, per year, with votes; turnout only in 2023 |
| Seats by party | Yes |
| Party changes while in office | Yes, dated, per councillor |
| Next election date | No |
| Chief executive and directors, by name | Yes |
| Monitoring officer, by name | No — the post and its pay band only |
| Section 151 officer | No — the role is named, the post-holder is not |
| Councillors' own websites or social accounts | No — none published |
