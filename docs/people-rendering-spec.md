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
- party (`party`) as a small text label, colour-matched to the bar
- one line: "Councillor since <first_elected, formatted to its precision>"
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
not — for Norwich it is the most important line in the section. Of the 39
registers, 22 are published as scanned pictures with no text in the file, so
nothing from them can be shown. Of the 17 that are readable, 13 carry entries
that could not be attributed with certainty, because the form puts a councillor's
own interests beside their partner's and the published file does not keep the
columns apart. The note says which case a councillor is in. Never render an empty
declarations box as though the councillor declared nothing.

Above the list, always, this sentence:

> This is what the councillor declared about themselves, in their own words. Every
> councillor has to fill in this form by law. It is not a list of accusations, and
> nothing on it means anything has gone wrong.

Then the register's date and a link to the register itself. If `interests` is
empty, do not show an empty box: show the `interests.note` instead, which says
what the council does and does not publish.

**Turning up.** `attendance` as one sentence and one small bar: "Went to
<attended> of <expected> meetings they were expected at, in <period>." Then the
`note`, always, because the period is a rolling window and the reader will
otherwise assume it is a year of their own choosing. If `attendance` is null,
print `attendance.note`'s equivalent from `gaps` — never a zero, never a dash.

**What they are paid.** `allowances` as one sentence: "Basic allowance
£<basic> for <year>, plus £<special_responsibility> for <the role>." Follow it
with one line of context the reader needs: an allowance is not a salary, and the
amounts are set by the council on the advice of an independent panel. If
`allowances` is null, say the council does not publish a per-councillor figure,
and link the scheme if there is one.

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

## The honesty note

This goes at the top of the page, under the title, before the composition bar. Not
in a footer, not behind a link. The wording below is the wording to use.

> **About this page**
>
> Everything here comes from Norwich City Council's own records, or from what
> councillors have declared about themselves. We have not gone looking anywhere
> else. No social media, no news reports, no company databases, nothing pieced
> together from someone's name.
>
> Councillors are required by law to declare things that might affect the
> decisions they take: a job, a directorship, land, help with election costs. They
> fill that form in themselves and the council publishes it. We reproduce it, we
> do not interpret it. A declaration is the system working, not evidence of
> anything.
>
> We do not score anyone. There is no league table here, no "best" or "worst"
> councillor, and no opinion about how anyone has voted. If a number looks bad, it
> is the council's number, and the caveat next to it is the council's caveat.
>
> Where we could not find something, we say so instead of guessing.
>
> **Something wrong?** If you are a councillor or an officer and something on this
> page is out of date, incomplete, or attributed to the wrong person, tell us and
> we will fix it. [Ask for a correction](<corrections_url>) — it takes a minute
> and you do not need a GitHub account to email us. We aim to correct factual
> errors within five working days, and we keep a note of what changed.
>
> **Want something taken down?** Any councillor or officer named here can ask us
> to remove or restrict what we show about them, and we will act on it while we
> look into it rather than after. Write to <REMOVALS_EMAIL> saying what you want
> removed. We will take the item down within five working days and reply telling
> you what we did. If we think the material should stay because the council itself
> still publishes it, we will say so and explain why, and you can take it further
> with the Information Commissioner's Office. Nothing here is a public-interest
> judgement we make on our own: if the council stops publishing something, we stop
> publishing it too.

Two things about that last paragraph. It is a real commitment, so the address has
to work and somebody has to read it. And the promise to remove first and argue
afterwards is deliberate: the cost of a page being briefly incomplete is far
smaller than the cost of being wrong about a named person.

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

Two things are not the designer's to decide, and both have to be settled first.

**A removal address that works.** `<REMOVALS_EMAIL>` in the honesty note is a
placeholder. The page names living people, so it cannot go up without a monitored
inbox and somebody who will act on what arrives in it. A GitHub issue is fine for
"you have my ward wrong"; it is not fine for "please take my name down", which
should not require a public post.

**A first pass by a person.** Every item in `people.json` is `needs_review`. The
rest of the site already tells readers when nothing human has checked a page, and
on a page of named people that warning is doing more work than anywhere else.

## What Norwich publishes, and what it does not

Useful context for anyone designing the page, and the reason several blocks have
to degrade gracefully.

| | Norwich |
|---|---|
| Councillor directory | Yes — 39 councillors, in the committee system |
| First elected, every term served | Yes, per councillor |
| Committee places, with joining dates | Yes |
| Outside body appointments | Yes, but only the first five are reachable |
| Attendance | Yes — meetings expected and attended, rolling twelve months |
| Register of interests | Yes, but 22 of 39 as scans; no index page; each one behind a form button |
| Allowances actually paid | Yes, per councillor, to 2024-25, by surname and initial |
| Election results | Yes, per ward, per year, with votes; turnout only in 2023 |
| Seats by party | Yes |
| Next election date | No |
| Chief executive and directors, by name | Yes |
| Monitoring officer, by name | No — the post and its pay band only |
| Section 151 officer | No — the role is named, the post-holder is not |
| Councillors' own websites or social accounts | No — none published |
