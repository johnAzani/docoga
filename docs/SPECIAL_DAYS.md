# Special days — what the machine posts on Christmas, Independence Day, Eid and the rest

Owner, 23 Oct 2026: *"Is there a possibility of integrating special events post to the contents
eg Christmas, Independence Day, Children's Day, Democracy Day, Eid etc."* Yes — and it is built
so that an event post is never a bare greeting card. On every special day DocOga still teaches
one rule a tenant can use, because the day is usually when the trouble arrives: the
"pack out before Christmas" message, the flat left locked over Sallah, the January renewal letter.

## How it works (no tap needed from you)

1. **The brain knows the date and the angle.** `tools/events_calendar.py` holds the days, their
   dates (fixed ones, Easter by calculation, the Islamic feasts as the Federal Government declared
   or the press projects them — with a moon-sighting caveat where the date is not yet official)
   and one tenancy angle each. From a few days before the day, the brain's night-time plan
   carries that angle; on the day it is allowed exactly **one greeting line** — opening or
   closing — and the post must still cite a fact from the law shelf like any other day.
2. **The card wears the day.** On the national days (Independence Day, Democracy Day) the
   brand card gets a thin **green-white-green ribbon** above the masthead — the only place
   flag green is allowed (`docs/BRAND_STYLE.md`). On every greeting day the masthead reads
   `DOCOGA · HAPPY INDEPENDENCE DAY`, `DOCOGA · MERRY CHRISTMAS`, `DOCOGA · EID MUBARAK`.
   Everything else — navy, the yellow slab, Inter — stays exactly as it is.
3. **The dashboard shows what is coming.** Admin → Social → under the plan: *Special days
   ahead* with the date and whether the flag frame applies.
4. **Islamic dates move.** 2026 is confirmed (Eid el-Fitr 20 Mar, Eid el-Kabir 27 May,
   Eid el-Maulud 25 Aug); 2027 is pinned from projections and marked so; any other year falls
   back to the tabular calendar (within a day or two). On a projected date the brain writes
   "this Sallah", never the date. When the Ministry of Interior declares a year, the dates go
   into `PINNED` and the year into `CONFIRMED_YEARS` — one line each.

## The calendar from today

| Day | Date | On the card | The angle the brain is given |
|---|---|---|---|
| Christmas Day | Fri 25 Dec 2026 | Greeting in the masthead | 'Pack out before Christmas' is not a notice: a quit notice must be written, must give the statutory months, and December does not shorten it. Travel: photograph, lock, keep the papers on your phone. |
| Boxing Day | Sat 26 Dec 2026 | Greeting in the masthead | Between Christmas and New Year the renewal letters arrive: a renewal is not a new tenancy, and the increase must be agreed, not announced. |
| New Year's Day | Fri 1 Jan 2027 | Greeting in the masthead | January is renewal month: a renewal is not a new tenancy, advance rent has legal limits in several states, and the year's first payment deserves the year's first receipt. |
| Eid el-Fitr | Wed 10 Mar 2027 *(moon-sighting projection)* | Greeting in the masthead | Sallah travel: the flat stays yours while you are away; photograph it, lock it, keep the receipt and agreement on your phone. A landlord cannot re-let a room because you travelled. |
| Good Friday | Fri 26 Mar 2027 | Greeting in the masthead | Easter travel: photograph the flat before you lock it, keep the agreement on your phone, and no landlord may enter or change the locks while you are away. |
| Easter Monday | Mon 29 Mar 2027 | Greeting in the masthead | Back from Easter: check the flat against your photos; damage you did not cause is not yours to pay for, and the caution fee covers damage, not holidays. |
| Workers' Day | Sat 1 May 2027 | Greeting in the masthead | The salary pays the rent; the receipt is the worker's proof. Rent paid in cash with no paper is rent paid twice when there is a dispute. |
| Eid el-Kabir | Sun 16 May 2027 *(moon-sighting projection)* | Greeting in the masthead | Sallah spending meets rent: pay the rent first and get the receipt; a landlord who says 'pay after Sallah' still owes you a receipt dated the day the money moved. |
| Children's Day | Thu 27 May 2027 | Greeting in the masthead | A family's home: the agreement names who lives there, children included, and a landlord may not lock a family out — eviction is a court order, never a padlock. |
| Democracy Day | Sat 12 Jun 2027 | Flag ribbon + greeting | The law is the tenant's vote: a receipt is a right, notice has a statutory length, and the court — not the landlord — ends a tenancy. |
| Eid el-Maulud | Sat 14 Aug 2027 *(moon-sighting projection)* | Greeting in the masthead | A public holiday is not a grace period: rent due on a holiday is due the next working day, and a receipt is due the day it is paid. |
| Independence Day | Fri 1 Oct 2027 | Flag ribbon + greeting | Independence at home: a tenant who holds a receipt, an agreement and a dated notice cannot be bullied. 1 October is the day to say what the law already gives you. |
| World Habitat Day / International Tenants' Day | Mon 4 Oct 2027 | No greeting — the day is the angle | The UN's housing day and the tenants' day fall together: one post on what adequate housing means in Nigerian law — a written agreement, a receipt, notice before eviction. |
| Christmas Day | Sat 25 Dec 2027 | Greeting in the masthead | 'Pack out before Christmas' is not a notice: a quit notice must be written, must give the statutory months, and December does not shorten it. Travel: photograph, lock, keep the papers on your phone. |
| Boxing Day | Sun 26 Dec 2027 | Greeting in the masthead | Between Christmas and New Year the renewal letters arrive: a renewal is not a new tenancy, and the increase must be agreed, not announced. |

## What it deliberately does not do

- No greeting-only posts ("Happy Eid from DocOga" and nothing else). Each post teaches a rule.
- No flag colours on Christmas, Eid or Easter — the flag is for the national days.
- No claims about a state's law that the law shelf cannot back: the calendar gives the *angle*,
  the fact ids still come from `tools/law_index.py` and the gates still refuse an unsupported
  claim.
- No posting *on behalf of* a faith: greetings are the ordinary Nigerian ones (Eid Mubarak /
  Barka da Sallah, Merry Christmas, Happy Easter) and nothing more.

Tests: `tools/tests/test_events_calendar.py`.
