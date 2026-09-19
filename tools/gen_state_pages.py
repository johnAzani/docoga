#!/usr/bin/env python3
"""Generate DocOga state SEO pages: 4 tenancy tools x 6 states = 24 pages.
Facts verified 19 Sep 2026: Lagos Tenancy Law 2011 s.13(1)/s.4/s.13(2)-(3);
Recovery of Premises Act s.8 (FCT). Other states: honest general framing."""
import io, os

STATES = {
 'lagos': dict(name='Lagos', place='Lagos', full='Lagos State',
   law='Lagos Tenancy Law 2011', law_note='The 2011 law covers most of Lagos State — Ikeja GRA, Ikoyi and Victoria Island are exempted areas.',
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
<table>
<tr><th>Type of tenancy</th><th>Minimum notice to quit</th></tr>
<tr><td>Tenant at will</td><td>1 week</td></tr>
<tr><td>Monthly</td><td>1 month</td></tr>
<tr><td>Quarterly</td><td>3 months</td></tr>
<tr><td>Half-yearly</td><td>3 months</td></tr>
<tr><td>Yearly</td><td>6 months</td></tr>
</table>
<p class="law">{advance}</p>
{arrears_block}
<p class="law"><b>The law:</b> {law} {law_note} Disputes go to {courts}. This page is general information, not legal advice \u2014 confirm the current position for your case with a Nigerian lawyer.</p>
</div>

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
    assert '</urlset>' in s and sitemap_add[0] not in s
    entries = ''.join(f'  <url>\n    <loc>https://docoga.com.ng/{f}</loc>\n    <priority>0.7</priority>\n  </url>\n' for f in sitemap_add)
    s = s.replace('</urlset>', entries + '</urlset>')
    io.open('site/sitemap.xml', 'w', encoding='utf-8').write(s)
    print(f"sitemap: +{len(sitemap_add)} URLs")

    s = io.open('site/index.html', encoding='utf-8').read()
    anchor = '''    <p>DocOga puts a standard, fill-in-the-blanks document generator in every pocket — from Lagos to Kano to Port Harcourt. Answer simple questions, and your document is ready to print, save as PDF, or share on WhatsApp. The free version carries a small DocOga banner; the <b>Oga Pass (₦2,000)</b> removes it and unlocks unlimited clean copies for 30 days.</p>
  </div>'''
    assert s.count(anchor) == 1, "index anchor fail"
    if 'State guides' not in s:
        links = ' · '.join(f'<a href="tenancy-agreement-{k}.html">{st["name"]}</a>' for k, st in STATES.items())
        block = anchor + f'''

  <div class="seo-block">
    <h2>State guides — tenancy rules where you rent</h2>
    <p>Notice-to-quit minimums and tenancy practice differ by state. Plain-English guides, current for 2026:</p>
    <p style="line-height:2">{links}</p>
  </div>'''
        s = s.replace(anchor, block)
        io.open('site/index.html', 'w', encoding='utf-8').write(s)
        print("index: state guides block added")
    else:
        print("index: state guides block already present")

if __name__ == '__main__':
    main()
