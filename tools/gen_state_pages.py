#!/usr/bin/env python3
"""Generate DocOga state SEO pages: 4 tenancy tools x 6 states = 24 pages.
Facts verified 19 Sep 2026: Lagos Tenancy Law 2011 s.13(1)/s.4/s.13(2)-(3);
Recovery of Premises Act s.8 (FCT). Other states: honest general framing."""
import io, os

STATES = {
 'lagos': dict(name='Lagos', place='Lagos', full='Lagos State',
   law='Lagos Tenancy Law 2011', law_note='The 2011 law covers most of Lagos State — s.1(3) excludes four areas: Apapa, Ikeja GRA, Ikoyi and Victoria Island.',
   courts='the Magistrates\u2019 Courts of Lagos State',
   notice_intro='<b>Section 13(1) of the Lagos Tenancy Law 2011</b> sets the minimum notice where the agreement is silent:',
   advance='Section 4 also makes it unlawful for a landlord to demand or receive more than <b>one year\u2019s rent in advance</b> from a yearly tenant (six months for a monthly tenant).',
   arrears='<b>Arrears rule (Lagos):</b> a monthly tenant who is six months in arrears loses entitlement to a quit notice (s.13(2)); a quarterly or half-yearly tenant who is one year in arrears does too (s.13(3)).',
   verified=True),
 'abuja': dict(name='Abuja (FCT)', place='Abuja', full='the Federal Capital Territory',
   law='Recovery of Premises Act', law_note='The Recovery of Premises Act is the federal law that governs recovery of premises in the FCT, Abuja.',
   courts='the Magistrates\u2019 Courts and the High Court of the FCT, Abuja',
   notice_intro='<b>Section 8 of the Recovery of Premises Act</b> (which applies in the FCT) sets the graduated notice framework where the agreement is silent:',
   advance='The FCT has no equivalent of Lagos\u2019s advance-rent cap \u2014 whatever advance you agree should be recorded clearly in the tenancy agreement before money moves.',
   arrears='', verified=True),
 'rivers': dict(name='Rivers', place='Rivers State (Port Harcourt)', full='Rivers State',
   law='recovery-of-premises legislation', law_note='Rivers State, like most Nigerian states, applies the traditional graduated notice framework through its recovery-of-premises legislation.',
   courts='the Magistrates\u2019 Courts in Rivers State',
   notice_intro='Where the agreement is silent, courts in most states \u2014 including Rivers \u2014 apply the traditional graduated framework:',
   advance='There is no Lagos-style advance-rent cap in Rivers State \u2014 agree the advance in writing in the tenancy agreement.',
   arrears='', verified=False),
 'oyo': dict(name='Oyo', place='Oyo State (Ibadan)', full='Oyo State',
   law='recovery-of-premises legislation', law_note='Oyo State follows the traditional graduated notice framework in its recovery-of-premises legislation.',
   courts='the Magistrates\u2019 Courts in Oyo State',
   notice_intro='Where the agreement is silent, courts in most states \u2014 including Oyo \u2014 apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'kano': dict(name='Kano', place='Kano State', full='Kano State',
   law='recovery-of-premises legislation', law_note='Kano State follows the traditional graduated notice framework in its recovery-of-premises legislation.',
   courts='the courts of Kano State',
   notice_intro='Where the agreement is silent, courts in most states \u2014 including Kano \u2014 apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'enugu': dict(name='Enugu', place='Enugu State', full='Enugu State',
   law='recovery-of-premises legislation', law_note='Enugu State follows the traditional graduated notice framework in its recovery-of-premises legislation.',
   courts='the Magistrates\u2019 Courts in Enugu State',
   notice_intro='Where the agreement is silent, courts in most states \u2014 including Enugu \u2014 apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'delta': dict(name='Delta', place='Delta State (Asaba / Warri)', full='Delta State',
   law='recovery-of-premises legislation', law_note='Delta State follows the traditional graduated notice framework. Warri and Asaba are the main rental markets.',
   courts='the Magistrates\u2019 Courts in Delta State',
   notice_intro='Where the agreement is silent, courts in Delta State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves. In Warri and Asaba, yearly advance is common.',
   arrears='', verified=False),
 'kaduna': dict(name='Kaduna', place='Kaduna State', full='Kaduna State',
   law='recovery-of-premises legislation', law_note='Kaduna State follows the traditional graduated notice framework in its recovery-of-premises legislation.',
   courts='the courts of Kaduna State',
   notice_intro='Where the agreement is silent, courts in Kaduna State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'ogun': dict(name='Ogun', place='Ogun State (Abeokuta)', full='Ogun State',
   law='recovery-of-premises legislation', law_note='Ogun State follows the traditional graduated notice framework. With Lagos overflow, towns like Ota, Mowe and Ibafo see fast-growing rental markets.',
   courts='the Magistrates\u2019 Courts in Ogun State',
   notice_intro='Where the agreement is silent, courts in Ogun State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'anambra': dict(name='Anambra', place='Anambra State (Onitsha / Awka)', full='Anambra State',
   law='recovery-of-premises legislation', law_note='Anambra State follows the traditional graduated notice framework. Onitsha and Awka are the main rental hubs.',
   courts='the Magistrates\u2019 Courts in Anambra State',
   notice_intro='Where the agreement is silent, courts in Anambra State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'edo': dict(name='Edo', place='Edo State (Benin City)', full='Edo State',
   law='recovery-of-premises legislation', law_note='Edo State follows the traditional graduated notice framework in its recovery-of-premises legislation.',
   courts='the Magistrates\u2019 Courts in Edo State',
   notice_intro='Where the agreement is silent, courts in Edo State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
 'plateau': dict(name='Plateau', place='Plateau State (Jos)', full='Plateau State',
   law='recovery-of-premises legislation', law_note='Plateau State follows the traditional graduated notice framework. Jos remains a popular and affordable rental market in the North-Central region.',
   courts='the Magistrates\u2019 Courts in Plateau State',
   notice_intro='Where the agreement is silent, courts in Plateau State apply the traditional graduated framework:',
   advance='Agree the advance in writing in the tenancy agreement before any money moves.',
   arrears='', verified=False),
}

TOOLS = {
 'tenancy-agreement': dict(tool='Tenancy Agreement', hash='#agreement', verb='agreement',
   title='Tenancy Agreement in {place} — Free Nigerian Generator (2026)',
   desc='Create a complete tenancy agreement for {place} in 2 minutes. Free, on your phone — rent, caution fee, notice periods, covenants. Print or save as PDF.',
   lead='Renting in {place}? A written tenancy agreement is the one document that protects both landlord and tenant \u2014 the rent, the duration, the caution fee, and the notice each side must give before the tenancy ends. DocOga builds a complete, standard Nigerian agreement in about two minutes \u2014 free, no signup, straight from your phone.',
   body_title='What your {place} agreement should lock down',
   bullets=[
     '<b>The notice period you actually want.</b> Courts uphold what the agreement says \u2014 the statutory defaults apply only \u201cwhere there is no stipulation\u201d. If you want three months, write three months.',
     '<b>The rent and the advance</b> \u2014 exact amount in figures and words, and how much is payable in advance.',
     '<b>The caution fee</b> \u2014 amount, purpose, and the refund terms. This is the most disputed money in Nigerian tenancies.',
     '<b>The parties and the property</b> \u2014 full names, addresses, and a clear description of the premises.',
     '<b>Covenants</b> \u2014 repairs, utilities, subletting, use of the premises, and renewal terms.'],
   faq=[
     ('Is a written tenancy agreement compulsory in {place}?', 'A tenancy can exist without one \u2014 but without it you have no agreed rent record, no caution-fee terms, and the statutory notice defaults govern. A two-minute written agreement is cheaper than any dispute.'),
     ('Does the agreement override the notice periods in the law?', 'Generally yes \u2014 the statutory periods apply where the agreement is silent. Write the notice you want into the agreement.'),
     ('How much is a lawyer-drafted agreement?', 'Commonly \u20a620,000\u2013\u20a650,000 in Nigerian cities. The DocOga generator produces a standard agreement free (small watermark), or clean copies for \u20a62,000/30 days.')]),
 'notice-to-quit': dict(tool='Notice to Quit', hash='#notice', verb='notice',
   title='Notice to Quit in {place} — Free Generator (2026)',
   desc='The lawful notice to quit for {place}: correct minimum periods, valid service, and a free generator that produces the letter in 2 minutes.',
   lead='Ending a tenancy in {place}? A notice to quit that fails on period or service will be thrown out by the court \u2014 months wasted. Here are the rules that matter, and a generator that produces a properly-formatted notice in about two minutes.',
   body_title='When a notice to quit is valid in {place}',
   bullets=[
     '<b>Correct minimum period</b> \u2014 see the table above; a yearly tenant needs six months where the agreement is silent.',
     '<b>Proper service</b> \u2014 it must reach the tenant in a way you can prove. Service can be on any day and at any hour, but proof is everything.',
     '<b>Signed by the right person</b> \u2014 the landlord, or an agent/solicitor with written authority dated before the notice is issued.',
     '<b>After it expires:</b> a further <b>7 days\u2019 notice of the owner\u2019s intention to apply to court</b> to recover possession \u2014 then the case goes to {courts}.',
     '<b>Fixed term already expired?</b> No quit notice is needed at all \u2014 only the 7-day court notice.'],
   faq=[
     ('Can my landlord give me less than six months\u2019 notice?', 'If your written agreement specifies a shorter (or longer) notice, that clause generally governs. Where it is silent, the statutory minimums apply.'),
     ('What if I\u2019m in arrears?', '{arrears_placeholder}'),
     ('How do I count the notice period?', 'Traditionally it had to expire at the end of a complete period of the tenancy \u2014 the modern Lagos rule allows expiry on or after the current term ends. When in doubt, give more than the minimum.')]),
 'rent-receipt': dict(tool='Rent Receipt', hash='#receipt', verb='receipt',
   title='Rent Receipt in {place} — Free Generator (2026)',
   desc='Issue a proper rent receipt in {place}: date, amount in words and figures, period covered, signatures. Free generator, 2 minutes, print or PDF.',
   lead='Rent in Nigeria is paid in advance \u2014 commonly a full year at once. Every payment deserves a proper receipt: it is the tenant\u2019s proof of payment in any dispute, and the landlord\u2019s clean record. DocOga produces a proper Nigerian rent receipt in about two minutes \u2014 free.',
   body_title='What a valid rent receipt carries',
   bullets=[
     '<b>Date of payment</b> and receipt number for your records.',
     '<b>The amount in figures and in words</b> \u2014 the words prevent alteration disputes.',
     '<b>The period the rent covers</b> (e.g. one year from 1 October 2026).',
     '<b>The property</b> the payment relates to.',
     '<b>Names of payer and issuer</b>, with the landlord\u2019s (or agent\u2019s) signature.'],
   faq=[
     ('Is my landlord obliged to give me a receipt?', 'Where tenancy laws require acknowledgment of rent paid (as in Lagos), yes \u2014 and even where not explicitly stated, refusing to receipt a payment is a red flag no tenant should accept.'),
     ('Can a receipt be handwritten?', 'Yes \u2014 what matters is content and signature. A clean printed receipt simply removes the arguments.'),
     ('I paid an agent, not the landlord. Receipt from whom?', 'Whoever collects must receipt \u2014 and the agreement should identify who is authorised to collect rent.')]),
 'caution-fee': dict(tool='Caution Fee Receipt', hash='#caution', verb='caution-fee receipt',
   title='Caution Fee Receipt in {place} — Free Generator (2026)',
   desc='Secure your caution fee / security deposit in {place} with a proper receipt and written refund terms. Free generator, 2 minutes.',
   lead='The caution fee (security deposit) is refundable money \u2014 in practice, the most disputed money in Nigerian tenancies. Your protection is written refund terms recorded at the moment of payment. DocOga produces a caution-fee receipt with proper refund terms in about two minutes \u2014 free.',
   body_title='Protecting your caution fee in {place}',
   bullets=[
     '<b>Receipt the deposit separately from rent</b> \u2014 never lump it into the rent figure.',
     '<b>Refund terms in writing:</b> refundable at tenancy\u2019s end, fair wear and tear excepted.',
     '<b>Itemised deductions only</b> \u2014 any deduction must be listed in writing with evidence.',
     '<b>Record the property\u2019s condition at move-in</b> (photos, a short checklist) \u2014 it settles most arguments before they start.',
     '<b>Timeline:</b> state when the refund is due after the tenancy ends.'],
   faq=[
     ('Is a caution fee the same as rent?', 'No \u2014 it is a refundable security deposit held against damage or unpaid charges. It is not the landlord\u2019s income.'),
     ('How much can a caution fee be?', 'Commonly a fraction of the rent, but it is negotiable \u2014 record whatever you agree in the tenancy agreement and receipt it.'),
     ('What if the landlord refuses to refund?', 'Your receipt with written refund terms, plus your move-in condition record, is exactly what {courts} will want to see.')]),
}

TPL = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://docoga.com.ng/{fname}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#141F33;background:#F5F7FB;line-height:1.6}}
.wrap{{max-width:760px;margin:0 auto;padding:20px 18px 60px}}
.brand{{display:inline-block;font-weight:900;font-size:20px;color:#0040E0;text-decoration:none;padding:10px 0}}
h1{{font-size:26px;line-height:1.25;margin:10px 0 14px}}
.lead{{font-size:16px;color:#37455E}}
.box{{background:#fff;border:1px solid #DCE4F0;border-radius:14px;padding:18px 20px;margin:20px 0}}
h2{{font-size:19px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:14.5px;margin:8px 0}}
th,td{{padding:8px 10px;border:1px solid #DCE4F0;text-align:left}}
th{{background:#F0F4FA}}
ul{{padding-left:20px}}
li{{margin:8px 0;font-size:15px}}
.law{{font-size:13px;color:#5B6B85}}
.cta{{display:inline-block;background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:10px;padding:14px 24px;font-size:16px;margin:14px 0}}
details{{background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:14px 18px;margin:10px 0}}
summary{{font-weight:700;cursor:pointer}}
p{{margin:8px 0}}
.links{{font-size:14px}}
.links a{{color:#0040E0;text-decoration:none;font-weight:600;margin-right:12px;white-space:nowrap;display:inline-block}}
footer{{margin-top:34px;border-top:1px solid #DCE4F0;padding-top:16px;font-size:12.5px;color:#5B6B85}}
</style>
</head>
<body>
<div class="wrap">
<a class="brand" href="https://docoga.com.ng/">DocOga</a>
<h1>{title}</h1>
<p class="lead">{lead}</p>

<div class="box">
<h2>Notice-to-quit minimums in {place}</h2>
<p class="law">{notice_intro}</p>
{notice_table}
<p class="law">{advance}</p>
{arrears_block}
<p class="law"><b>The law:</b> {law} {law_note} Disputes go to {courts}. This page is general information, not legal advice \u2014 confirm the current position for your case with a Nigerian lawyer.</p>
</div>

{law_block}

<div class="box">
<h2>{body_title}</h2>
<ul>
{bullets}
</ul>
</div>

<div class="box">
<h2>Make it in 2 minutes \u2014 free</h2>
<p>DocOga\u2019s {tool} generator works on your phone: answer simple questions, get a clean, standard Nigerian document. Free version carries a small banner; the Oga Pass (\u20a62,000/30 days) unlocks unlimited clean copies \u2014 all 9 tools.</p>
<a class="cta" href="https://docoga.com.ng/{hash}">Create your {verb} free \u2192</a>
</div>

<div class="box">
<h2>Questions people ask</h2>
{faq}
</div>

{sources_block}

<div class="box links">
<h2>More for {name}</h2>
{same_state_links}
<h2 style="margin-top:14px">Same tool, other states</h2>
{other_states_links}
</div>

<footer>
<b>DocOga</b> \u2014 free Nigerian document tools: tenancy agreement, notice to quit, rent receipt, invoice, employment contract, caution fee receipt, letter of demand, payslip, warning letter.
<br><br>This page is general information about Nigerian tenancy practice, current as at September 2026 \u2014 it is not legal advice.
</footer>
</div>
</body>
</html>
'''

# ---------------------------------------------------------------------------
# State-specific legal content.
#
# Verified statute-level law lives in tools/state_law_data.py, compiled under
# Rule Zero: primary sources, section citations, and open questions recorded
# rather than guessed at. A state appears there only if it reaches tier A-D.
# States that are not there get the general Nigerian position AND a plain
# statement that we have not verified their own statute.
# ---------------------------------------------------------------------------
try:
    from state_law_data import STATE_LAW, NEEDS_CONFIRMATION, TIER_E_PUBLISHED
except ImportError:  # only when run from outside tools/
    from tools.state_law_data import STATE_LAW, NEEDS_CONFIRMATION, TIER_E_PUBLISHED

# The general ladder, WITHOUT a half-yearly tier. Lagos is the only
# jurisdiction we have verified that legislates for a half-yearly tenant
# (s.13(1)(d), three months). The FCT Act, Cross River s.15 and Kwara s.17
# all run week / month / quarter / half-year with no half-yearly row.
DEFAULT_NOTICE = [
    ("Tenant at will", "1 week"),
    ("Monthly", "1 month"),
    ("Quarterly", "3 months (a quarter)"),
    ("Yearly", "6 months (half a year)"),
]

LAGOS_NOTICE = [
    ("Tenant at will", "1 week"),
    ("Monthly", "1 month"),
    ("Quarterly", "3 months"),
    ("Half-yearly", "3 months"),
    ("Yearly", "6 months"),
]


def overlay(st, slug):
    """Drive the legacy per-state strings from the verified data layer.

    The STATES dict still carries hand-written sentences from before the
    research. Where a state now has verified law, those strings are wrong --
    the most serious being Edo, described as "the Magistrates' Courts in Edo
    State" when s.4 of the Edict establishes Rent Tribunals and s.41(2)
    repealed the Recovery of Premises Law for residential accommodation.
    Overlaying here means the old strings cannot silently contradict the
    cited law block underneath them.
    """
    law = STATE_LAW.get(slug)
    if law:
        forum = law.get('forum') or {}
        st['courts'] = forum.get('name') or (
            'the courts of %s (not yet confirmed from the primary text)' % law['name'])
        # Kano deliberately has no `statutes` entry: we could not cite one, and
        # inventing a title would be worse than naming nothing.
        _s0 = (law.get('statutes') or [None])[0]
        st['law'] = _s0['title'] if _s0 else (
            'a law we could not verify for %s' % law['name'])
        st['law_note'] = (' (%s)' % _s0.get('citation', '')) if _s0 else (
            ' We looked and could not cite one — see the note below.')
        st['notice_intro'] = (
            'Verified against <i>%s</i> \u2014 %s. Where the agreement is '
            'silent, the minimum notice is:' % (_s0['title'], _s0.get('citation', ''))
            if _s0 else
            'We could not verify this state\u2019s own statute, so the table below is '
            'the general Nigerian position rather than a citation:')
        ar = law.get('advance_rent') or {}
        st['advance'] = ar.get('text', '') or (
            'This state\u2019s statute sets no cap we have been able to verify \u2014 '
            'agree the advance in writing before any money moves.')
        if law.get('notice_extras'):
            st['arrears'] = law['notice_extras'][1] if len(law['notice_extras']) > 1 else ''
    else:
        st['notice_intro'] = (
            'We have <b>not</b> verified this state\u2019s own statute, so the '
            'table below is the general Nigerian position rather than a citation. '
            'Confirm it locally before relying on it:')
        # Do not assert a forum or a statute we cannot cite. These strings were
        # hand-written before the research and stated specific courts and laws
        # for states whose legislation had never been checked.
        st['courts'] = 'the courts of %s (not yet verified for this state)' % st['name']
        st['law'] = 'a recovery-of-premises or landlord-and-tenant law we have not been able to verify'
        st['law_note'] = ('We have not located this state\u2019s own statute, so we do not '
                          'name one. See the note below.')
        st['advance'] = (
            'We have found no advance-rent cap in force for this state. Whatever '
            'you agree, record it in the tenancy agreement before money moves.')


def notice_rows(slug):
    """Per-state notice table. Lagos is the only state with a half-yearly tier."""
    if slug == 'lagos':
        return LAGOS_NOTICE
    law = STATE_LAW.get(slug)
    ladder = (law or {}).get('notice_ladder') or []
    # Only replace the national ladder where we actually verified most of it.
    # Rivers publishes the yearly tier alone; one row would read as if the
    # other tiers did not exist, so the general ladder is shown with a note.
    if len(ladder) >= 3:
        return [(a, b) for a, b, _cite in ladder]
    return DEFAULT_NOTICE


def notice_table(slug, place):
    rows = '\n'.join(
        f'<tr><td>{a}</td><td>{b}</td></tr>' for a, b in notice_rows(slug)
    )
    law = STATE_LAW.get(slug)
    if law and law.get('statutes'):
        cite = ' &middot; '.join(
            '<b>s.%s</b>' % r[2].replace('s.', '') if r[2].startswith('s.') else r[2]
            for r in law.get('notice_ladder', [])[:1]
        )
        note = '<p class="law">Source: %s, %s.</p>' % (
            law['statutes'][0]['title'], law['statutes'][0].get('citation', ''))
    else:
        note = ('<p class="law">This is the general Nigerian position. '
                '<b>We have not yet verified %s&rsquo;s own tenancy statute</b> '
                '&mdash; see the note below.</p>' % place)
    return (
        '<table>\n<tr><th>Type of tenancy</th><th>Minimum notice to quit</th></tr>\n'
        + rows + '\n</table>\n' + note
    )


def law_block(slug, tslug):
    """The state-specific legal section. This is what makes the page unique."""
    law = STATE_LAW.get(slug)
    if not law:
        return unverified_block(slug)

    parts = ['<div class="box">',
             '<h2>What the law actually says in %s</h2>' % law['name']]

    # --- the statute itself, with citation -------------------------------
    # Only where we can cite one. Kano has none, and the honest absence is
    # carried by its verified_negative and inheritance blocks instead.
    st0 = (law.get('statutes') or [None])[0]
    if st0:
        parts.append('<p class="law"><b>The statute:</b> <i>%s</i> &mdash; %s. Commenced %s.</p>' % (
            st0['title'], st0.get('citation', ''), st0.get('commenced', 'date not stated')))
        if st0.get('note'):
            parts.append('<p class="law">%s</p>' % st0['note'])
    else:
        parts.append('<p class="law"><b>No citable statute found.</b> We could not locate a '
                     'tenancy or rent-control statute for %s from any source we trust. '
                     'Rather than name one we cannot cite, the sections below set out what '
                     'we did find.</p>' % law['name'])

    # --- forum -----------------------------------------------------------
    if law.get('forum'):
        parts.append('<h3 style="font-size:15px;margin:14px 0 6px">Where a dispute goes</h3>')
        parts.append('<p class="law">%s</p>' % law['forum']['text'])
        for key in ('important', 'adr', 'valuers', 'procedure', 'rules_committee', 'zones', 'terms'):
            if law['forum'].get(key):
                parts.append('<p class="law">%s</p>' % law['forum'][key])

    # --- tool-specific substance ----------------------------------------
    parts.extend(tool_block(law, tslug))

    # --- the things worth knowing regardless of tool --------------------
    for key, heading in (('correction', 'A correction to our own research'),
                         ('verified_negative', 'What we found when we looked'),
                         ('inheritance', 'What probably governs recovery instead'),
                         ('alternative_accommodation', 'Alternative accommodation'),
                         ('repairs', 'Who repairs what'),
                         ('security_of_tenancy', 'Protection from retaliatory notices'),
                         ('first_six_months', 'A new tenant&rsquo;s first six months'),
                         ('suitable_alternative_accommodation', 'Alternative accommodation'),
                         ('distress', 'Seizing a tenant&rsquo;s property'),
                         ('excluded_areas', 'Where this law does <i>not</i> apply'),
                         ('application', 'What the law covers'),
                         ('related', 'A related jurisdiction')):
        if law.get(key):
            blk = law[key] or {}
            head = blk.get('title') or heading
            parts.append('<h3 style="font-size:15px;margin:14px 0 6px">%s</h3>' % head)
            if blk.get('text'):
                parts.append('<p class="law">%s</p>' % blk['text'])
            if blk.get('summary'):
                parts.append('<p class="law">%s</p>' % blk['summary'])
            for sub in ('why', 'why_it_matters', 'plain', 'detail', 'definitions', 'definition',
                        'protection', 'supersedes', 'exception', 'contrast', 'penalty',
                        'must_state', 'also_excluded', 'arrears', 'secondary_conflict',
                        'stale_warning', 'how_to_read', 'grandfather', 'caution',
                        'statute', 'enugu', 'important'):
                if law[key].get(sub):
                    v = law[key][sub]
                    if isinstance(v, list):
                        parts.append('<ul>' + ''.join('<li>%s</li>' % i for i in v) + '</ul>')
                    else:
                        parts.append('<p class="law">%s</p>' % v)
            if law[key].get('rows'):
                parts.append('<table>\n<tr><th>Who</th><th>Rule</th></tr>' +
                             '\n'.join('<tr><td>%s</td><td>%s</td></tr>' % (a, b)
                                       for a, b, *_ in law[key]['rows']) + '\n</table>')

    # --- protections -----------------------------------------------------
    if law.get('protections'):
        parts.append('<h3 style="font-size:15px;margin:14px 0 6px">Other protections worth knowing</h3>')
        parts.append('<ul>' + ''.join('<li>%s</li>' % p for p in law['protections']) + '</ul>')

    # --- the honest part -------------------------------------------------
    gaps = []
    for key in ('lagos_dispute', 'kwara_conflict', 'notice_ladder_gap', 'schedules_omitted'):
        if law.get(key):
            v = law[key]
            if isinstance(v, str):
                gaps.append(v)
            else:
                gaps.append(v.get('summary') or v.get('detail') or v.get('note') or v.get('text', ''))
    if law.get('standard_rent', {}).get('anomaly'):
        gaps.append(law['standard_rent']['anomaly']['summary'])
    if law.get('rent_book', {}).get('gap'):
        gaps.append(law['rent_book']['gap'])
    gaps.extend(law.get('open_questions', []))
    if gaps:
        parts.append('<h3 style="font-size:15px;margin:14px 0 6px">What we could not confirm</h3>')
        parts.append('<p class="law">We publish the gaps rather than fill them in:</p>')
        parts.append('<ul>' + ''.join('<li>%s</li>' % g for g in gaps) + '</ul>')

    parts.append('</div>')
    return '\n'.join(parts)


def tool_block(law, tslug):
    """Content specific to this tool, drawn from the state's own statute."""
    out = []
    if tslug == 'tenancy-agreement':
        ar = law.get('advance_rent')
        if ar:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Advance rent</h3>')
            out.append('<p class="law">%s</p>' % ar['text'])
            if ar.get('rows'):
                out.append('<table>\n<tr><th>Who</th><th>Cap</th><th>Section</th></tr>' +
                           '\n'.join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % r
                                     for r in ar['rows']) + '\n</table>')
            for k in ('penalty', 'how_to_read', 'contrast', 'grandfather'):
                if ar.get(k):
                    out.append('<p class="law">%s</p>' % ar[k])
        if law.get('tenant_at_will'):
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Tenants at will</h3>')
            out.append('<p class="law">%s</p>' % law['tenant_at_will']['text'])
            for k in ('contrast', 'arrears'):
                if law['tenant_at_will'].get(k):
                    out.append('<p class="law">%s</p>' % law['tenant_at_will'][k])
        if law.get('contracting_out'):
            out.append('<p class="law">%s</p>' % law['contracting_out']['text'])
        if law.get('rent_control'):
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Rent control</h3>')
            out.append('<p class="law">%s</p>' % law['rent_control']['text'])
            for k in ('supersedes', 'recovery_of_excess'):
                if law['rent_control'].get(k):
                    out.append('<p class="law">%s</p>' % law['rent_control'][k])

    elif tslug == 'notice-to-quit':
        extras = law.get('notice_extras') or []
        if extras:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">How notice works here</h3>')
            out.append('<ul>' + ''.join('<li>%s</li>' % e for e in extras) + '</ul>')
        if law.get('notice_ladder_gap'):
            out.append('<p class="law">%s</p>' % law['notice_ladder_gap'])
        if law.get('notice_ladder_note'):
            out.append('<p class="law">%s</p>' % law['notice_ladder_note'])
        for key in ('anniversary_rule', 'rent_in_arrears'):
            if law.get(key):
                heading = ('When the notice must expire' if key == 'anniversary_rule'
                           else 'When rent is due')
                out.append('<h3 style="font-size:15px;margin:14px 0 6px">%s</h3>' % heading)
                out.append('<p class="law">%s</p>' % law[key]['text'])
                for sub in ('contrast', 'worked'):
                    if law[key].get(sub):
                        out.append('<p class="law">%s</p>' % law[key][sub])
        if law.get('service'):
            out.append('<p class="law"><b>Service:</b> %s</p>' % law['service']['text'])
        g = law.get('grounds_for_possession')
        if g:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Grounds a landlord can rely on</h3>')
            out.append('<ul>' + ''.join(
                '<li>%s%s</li>' % (a, (' &mdash; <i>%s</i>' % b) if b else '') for a, b in g
            ) + '</ul>')
            if law.get('grounds_note'):
                out.append('<p class="law">%s</p>' % law['grounds_note'])
        if law.get('forms'):
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Prescribed forms</h3>')
            out.append('<ul>' + ''.join('<li>%s</li>' % f for f in law['forms']) + '</ul>')
            if law.get('subtenant_warning'):
                out.append('<p class="law">%s</p>' % law['subtenant_warning'])

    elif tslug == 'rent-receipt':
        r = law.get('receipts')
        if r:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Receipts</h3>')
            out.append('<p class="law">%s</p>' % r['text'])
            if r.get('must_state'):
                out.append('<p class="law">The receipt must state:</p>')
                out.append('<ul>' + ''.join('<li>%s</li>' % i for i in r['must_state']) + '</ul>')
            for k in ('penalty', 'extra'):
                if r.get(k):
                    out.append('<p class="law">%s</p>' % r[k])
        rb = law.get('rent_book')
        if rb:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Rent books</h3>')
            out.append('<p class="law">%s</p>' % rb['text'])
            if rb.get('penalty'):
                out.append('<p class="law">%s</p>' % rb['penalty'])
            if rb.get('note'):
                out.append('<p class="law">%s</p>' % rb['note'])
            if rb.get('gap'):
                out.append('<p class="law">%s</p>' % rb['gap'])

    elif tslug == 'caution-fee':
        p = law.get('premium')
        if p:
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Premiums, loans and caution money</h3>')
            out.append('<p class="law">%s</p>' % p['text'])
            for k in ('plain', 'penalty', 'exception'):
                if p.get(k):
                    out.append('<p class="law">%s</p>' % p[k])
        c = law.get('caution_fee')
        if c:
            out.append('<p class="law">%s</p>' % c['text'])
            if c.get('warning'):
                out.append('<p class="law">%s</p>' % c['warning'])
        if law.get('improvements'):
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Improvements you make</h3>')
            out.append('<p class="law">%s</p>' % law['improvements']['text'])
        gf = law.get('grounds_and_forms')
        if gf and gf.get('improvements'):
            out.append('<p class="law">%s</p>' % gf['improvements'])
        if law.get('penalties') and law['penalties'].get('rows'):
            out.append('<h3 style="font-size:15px;margin:14px 0 6px">Penalties</h3>')
            out.append('<table>\n<tr><th>Conduct</th><th>Penalty</th></tr>' +
                       '\n'.join('<tr><td>%s</td><td>%s</td></tr>' % (a, b)
                                 for a, b, *_ in law['penalties']['rows']) + '\n</table>')

    return out


def unverified_block(slug):
    """Honest framing for a state whose own statute we have not verified."""
    note = NEEDS_CONFIRMATION.get(slug)
    parts = ['<div class="box">', '<h2>What we can and cannot tell you about this state</h2>']
    if note:
        parts.append('<p class="law"><b>Status of our research:</b> %s</p>' % note)
    else:
        parts.append(
            '<p class="law"><b>Status of our research:</b> we have not been able to verify a '
            'tenancy or rent-control statute for this state from a primary source. Rather than '
            'describe a law we cannot cite, we say so. Everything below is the general Nigerian '
            'position, which is the starting point most states share.</p>')
    parts.append(
        '<p class="law">Almost every Nigerian state has <i>some</i> recovery-of-premises or '
        'rent-control legislation, and almost all of them descend from the same colonial-era '
        'model &mdash; which is why the notice ladder below looks familiar. But the details that '
        'decide real cases &mdash; the forum, the advance-rent cap, whether a tribunal exists, '
        'whether alternative accommodation must be found &mdash; are set state by state, and '
        'they genuinely differ.</p>')
    parts.append(
        '<p class="law">Before you rely on any figure here for this state, confirm it against the '
        'state&rsquo;s own laws or a lawyer practising there. We will update this page the moment '
        'we can cite the statute.</p>')
    parts.append('</div>')
    return '\n'.join(parts)


def sources_block(slug):
    """Sources and confidence tier, on the page rather than hidden in a comment."""
    law = STATE_LAW.get(slug)
    parts = ['<div class="box">', '<h2>Sources and confidence</h2>']
    if law:
        parts.append('<p class="law"><b>Confidence: tier %s.</b> %s</p>' % (
            law['tier'], law.get('tier_note', '')))
        srcs = law.get('sources', [])
        if srcs:
            parts.append('<ul>' + ''.join('<li>%s</li>' % s for s in srcs) + '</ul>')
    else:
        parts.append(
            '<p class="law"><b>Confidence: tier E for the state&rsquo;s own statute.</b> '
            'The general Nigerian position on this page rests on the Recovery of Premises Act '
            '(Cap. 544 LFN, Abuja) and the Lagos Tenancy Law 2011 as the two texts we have read '
            'in full. We have not verified a statute for this state, and we do not cite one.</p>')
    parts.append(
        '<p class="law">This page is general information, not legal advice. Tenancy law in Nigeria '
        'is made state by state, and a lawyer practising in your state will know the current '
        'position in a way a national page cannot.</p>')
    parts.append('</div>')
    return '\n'.join(parts)


def faq_html(t, st):
    out = []
    for q, a in t['faq']:
        if '{courts}' in a: a = a.replace('{courts}', st['courts'])
        if '{arrears_placeholder}' in a:
            a = st['arrears'] if st['arrears'] else 'Serious arrears can cost a tenant the protection of a quit notice \u2014 courts can order possession on proof of the arrears. Never let arrears run; and landlords: follow the lawful process, never self-help.'
        if '{place}' in a: a = a.replace('{place}', st['place'])
        out.append('<details><summary>' + q.replace('{place}', st['place']) + '</summary><p>' + a + '</p></details>')
    return '\n'.join(out)

def main():
    made = 0
    sitemap_add = []
    for slug, st in STATES.items():
        for tslug, t in TOOLS.items():
            fname = f"{tslug}-{slug}.html"
            st = dict(STATES[slug])
            overlay(st, slug)
            d = dict(st)
            d.update(t)
            d['title'] = t['title'].format(place=st['place'])
            d['desc'] = t['desc'].format(place=st['place'])
            d['lead'] = t['lead'].format(place=st['place'])
            d['body_title'] = t['body_title'].format(place=st['place'])
            d['bullets'] = '\n'.join('<li>' + b.format(place=st['place'], courts=st['courts']) + '</li>' for b in t['bullets'])
            d['faq'] = faq_html(t, st)
            d['fname'] = fname
            d['arrears_block'] = ('<p class="law">' + st['arrears'] + '</p>' if st['arrears'] else '')
            d['notice_table'] = notice_table(slug, st['place'])
            d['law_block'] = law_block(slug, tslug)
            d['sources_block'] = sources_block(slug)
            d['same_state_links'] = '\n'.join(f'<a href="https://docoga.com.ng/{ts2}-{slug}.html">{t2["tool"]} \u2014 {st["name"]}</a>' for ts2, t2 in TOOLS.items() if ts2 != tslug)
            d['other_states_links'] = '\n'.join(f'<a href="https://docoga.com.ng/{tslug}-{s2}.html">{st2["name"]}</a>' for s2, st2 in STATES.items() if s2 != slug)
            html = TPL.format(**d)
            io.open('site/' + fname, 'w', encoding='utf-8').write(html)
            sitemap_add.append(fname)
            made += 1
    print(f"generated {made} state pages")
    sizes = [os.path.getsize('site/' + f) for f in sitemap_add]
    print(f"avg size: {sum(sizes)//len(sizes)}B, total: {sum(sizes)//1024}KB")

    s = io.open('site/sitemap.xml', encoding='utf-8').read()
    assert '</urlset>' in s
    # Remove existing state page entries (idempotent regeneration)
    import re
    for f in sitemap_add:
        pattern = rf'\s*<url>\s*<loc>https://docoga\.com\.ng/{re.escape(f)}</loc>\s*<priority>0\.7</priority>\s*</url>'
        s = re.sub(pattern, '', s)
    entries = ''.join(f'  <url>\n    <loc>https://docoga.com.ng/{f}</loc>\n    <priority>0.7</priority>\n  </url>\n' for f in sitemap_add)
    s = s.replace('</urlset>', entries + '</urlset>')
    io.open('site/sitemap.xml', 'w', encoding='utf-8').write(s)
    print(f"sitemap: {len(sitemap_add)} URLs (regenerated)")

    s = io.open('site/index.html', encoding='utf-8').read()
    anchor = '''    <p>DocOga puts a standard, fill-in-the-blanks document generator in every pocket — from Lagos to Kano to Port Harcourt. Answer simple questions, and your document is ready to print, save as PDF, or share on WhatsApp. The free version carries a small DocOga banner; the <b>Oga Pass (₦2,000)</b> removes it and unlocks unlimited clean copies for 30 days.</p>
  </div>'''
    links = ' · '.join(f'<a href="tenancy-agreement-{k}.html">{st["name"]}</a>' for k, st in STATES.items())
    if 'State guides' not in s:
        if s.count(anchor) == 1:
            block = anchor + '''

  <div class="seo-block">
    <h2>State guides — tenancy rules where you rent</h2>
    <p>Notice-to-quit minimums and tenancy practice differ by state. Plain-English guides, current for 2026:</p>
    <p style="line-height:2">{links}</p>
  </div>'''
            s = s.replace(anchor, block)
            io.open('site/index.html', 'w', encoding='utf-8').write(s)
            print("index: state guides block added")
        else:
            print("index: anchor not found, state guides block skipped")
    else:
        # Update existing state guides block with current state list
        import re as _re
        old_links = _re.search(r'(<p style="line-height:2">).*?(</p>)', s, _re.DOTALL)
        if old_links:
            replacement = f'<p style="line-height:2">{links}</p>'
            s = s[:old_links.start()] + replacement + s[old_links.end():]
            io.open('site/index.html', 'w', encoding='utf-8').write(s)
            print("index: state guides block updated")
        else:
            print("index: state guides block already present")

if __name__ == '__main__':
    main()
