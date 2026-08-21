"""Industry-aware homepage prose, replacing site_engine.py's single
universal contractor-flavored paragraph template.

2026-08-21: _index_main() (site_engine.py) used to hardcode ONE paragraph
template ("Every project... written estimate... materials and options
are explained... chase anyone down after the visit") applied verbatim to
every subtype -- a dental practice, a restaurant, a law firm all got
literally the same contractor-flavored sentences with only the business
name substituted in. Confirmed via a real headless-browser screenshot
during this session's investigation (not just an audit-score check) that
the rendered prose read as generic/boilerplate regardless of which of
the 9 templates it landed on -- growing template count further would not
have fixed this, since every template just renders whatever this
function hands it.

Reuses palettes.industry_family_for() -- the same shared classifier
palette_for()/template_for() already call -- so a business's prose,
palette, and template all key off one identical industry classification,
never disagreeing about which vertical a business belongs to.

Structural contract preserved from the original single-template version,
verified against audit_engine.py's real DOM-parsing checks
(_cat2_semantic_html), not Python-side word-count locals in site_engine.py
that turned out to be computed and never actually consumed:
  - each of the 3 prose "chunks" (p1, p2, about) is one <p> and should
    land in the 150-300 word range audit_engine._content_chunks measures
    (mean chunk length target)
  - each chunk keeps exactly one meaningfully-sized emphasized clause so
    the aggregate emphasis-density check (0.05-0.10 of total words)
    stays satisfied
  - p1 keeps the same answer-first opening shape ("{business} is a
    {human} in {loc}") since that's the literal check in
    _cat2_semantic_html's answer-first rule, and it's also just good,
    real, non-generic content -- the problem was never this line, it was
    everything after it.

Two authored variants per named family (not just business-name
substitution) selected by a decorrelated seed, same SHA-256
domain-separated re-hash pattern as typography._typography_seed() /
engine._template_seed(), so two same-industry businesses don't read
identically either.
"""
import hashlib
import re


def _prose_seed(seed: int) -> int:
    return int(hashlib.sha256(f"prose:{seed}".encode()).hexdigest()[:16], 16)


def _variant_index(seed: int, n: int) -> int:
    return _prose_seed(seed) % n


# Each entry below is a function (business_name, human, loc, areas, svc_phrase, creds) -> 10-tuple:
#   (open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b)
#
# 2026-08-21, Opus review round 3: p1_rest used to embed the "read more
# about {business_name}..." link as a single string carrying a sentinel
# marker (\x01ABOUT_LINK_OPEN\x01 / \x01ABOUT_LINK_CLOSE\x01) in place of
# the literal <a> tag, with site_engine.py substituting the real tag back
# in after escaping. That scheme was itself forgeable: business_name is
# free text with no charset restriction, is interpolated into the SAME
# string the sentinel lives in, and html.escape() doesn't touch \x01 (the
# exact property the scheme relied on to protect its own marker) -- so a
# business_name containing the literal sentinel bytes could inject its own
# fake anchor tag, and any stray \x01 reaching assets/logo.svg's
# aria-label (built from business_name via a separate path) produced
# invalid XML. Fixed at the root: the "read more" link's visible text
# (about_link_text) and the text after it (p1_trailing) are now genuinely
# separate return values, never concatenated into one string with a
# marker. site_engine.py builds the real <a href="about.html"> tag
# structurally from these pieces -- there is no in-band signal in any
# string for attacker-controlled text to forge.
# matching site_engine.py's original paragraph shape exactly.

def _dental_medical_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving patients throughout {areas}. The practice offers {svc_phrase}, "
        f"and every visit starts with a clear explanation of what is being "
        f"recommended and why, in plain language, before any treatment begins. "
        f"Patients choose {business_name} because appointments run on schedule, "
        f"costs are discussed up front, and the same clinical team follows a "
        f"case from the first visit through recovery. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and every new patient is seen by a licensed provider directly. "
    p1_rest += (
        f"Insurance and paperwork are handled by the office, so patients are not "
        f"left to sort out billing after the fact. New patients are welcomed "
        f"with the same care and attention as returning ones, and same-day "
        f"appointments are available for urgent needs. Records and history "
        f"carry forward from visit to visit, so nothing has to be re-explained "
        f"from scratch each time you come in. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach to care'
    p1_trailing = f" before your visit."
    p2_a = (
        f"Every treatment plan at {business_name} starts with a full clinical "
        f"evaluation, not a guess, so patients understand exactly what is "
        f"recommended and what the options are before agreeing to anything. "
    )
    em_clause = "Getting the diagnosis right the first time is what everything else depends on"
    p2_b = (
        f", because catching a problem early is almost always simpler and less "
        f"costly to treat than waiting. The team serves {areas} and keeps "
        f"scheduling flexible, so urgent concerns can usually be seen the same "
        f"week rather than weeks out. Patients who have had rushed appointments "
        f"elsewhere consistently mention how much time {business_name} takes to "
        f"explain findings and answer questions before moving forward. The same "
        f"standard of care applies to routine checkups and complex cases alike: "
        f"the provider who examines you is the one who treats you, every option "
        f"is explained before it is used, and nothing is added to a treatment "
        f"plan without discussing it with you first. Follow-up after treatment "
        f"is part of the plan, not an afterthought, so recovery is actually "
        f"tracked rather than assumed."
    )
    about_a = (
        f"{business_name} has cared for patients across {areas} for years, and "
        f"many families have seen the same provider for that entire time. That "
        f"continuity means your history is already known walking into every "
        f"visit, not reconstructed from a chart. If you are comparing care "
        f"options in {loc}, the "
    )
    about_em = "combination of real appointment availability and a provider who actually explains things is what patients mention most"
    about_b = (
        f", along with a team that answers the phone and follows up after "
        f"treatment rather than moving on to the next patient. New patients "
        f"receive the same unhurried first visit as long-standing ones, and "
        f"every record is kept up to date so nothing has to be re-explained "
        f"next time. Scheduling is straightforward, and you will always know "
        f"what was found, what is recommended, and what it costs before you "
        f"agree to treatment. If a question comes up after your visit, the "
        f"office is easy to reach and will get you a real answer, not a "
        f"callback three days later."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _dental_medical_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" providing care to patients across {areas}. Services include "
        f"{svc_phrase}, delivered with modern equipment and a clinical team "
        f"that keeps up with current standards of care rather than treating "
        f"the way things were done a decade ago. "
    )
    if creds:
        p1_rest += f"The practice is {creds}, and credentials are something patients are welcome to ask about directly. "
    p1_rest += (
        f"Every patient receives an individualized plan rather than a standard "
        f"protocol applied to everyone, and the reasoning behind each "
        f"recommendation is explained before treatment starts. New patients are "
        f"seen promptly, and the office coordinates directly with insurance so "
        f"billing surprises are rare. Appointment times are built around real "
        f"conversation, not a fixed slot that ends the moment the clock runs "
        f"out. Records and imaging from a prior provider are reviewed before "
        f"your first visit whenever they're available, so the team already has "
        f"context instead of starting from nothing. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and how the practice is run'
    p1_trailing = f" before scheduling."
    p2_a = (
        f"{business_name} reviews each case individually before recommending "
        f"anything, weighing the real options against a patient's actual "
        f"situation rather than defaulting to the same plan for everyone. "
    )
    em_clause = "A treatment plan that is explained clearly is one a patient can actually agree to with confidence"
    p2_b = (
        f", and that clarity is treated as part of the care itself, not an "
        f"afterthought. The team serves {areas} and structures appointments so "
        f"there is real time to ask questions, not a rushed five minutes at the "
        f"end. Costs are discussed before treatment, not after, and patients "
        f"are never pressured into add-ons they did not ask about. The same "
        f"thoroughness applies whether the visit is routine or urgent: findings "
        f"are documented, options are laid out honestly, and the final decision "
        f"is always the patient's to make. If a plan needs to change partway "
        f"through, that change is discussed before it happens, not discovered "
        f"on the bill afterward. Second opinions are welcomed rather than "
        f"treated as a challenge to the recommendation, because a patient who "
        f"actually understands why a treatment is recommended is more likely to "
        f"follow through with it."
    )
    about_a = (
        f"{business_name} has built a practice around patients in {areas} who "
        f"want a provider they can actually reach and a plan they actually "
        f"understand. Records carry forward from visit to visit, so care stays "
        f"consistent even years apart, and nothing gets lost between "
        f"appointments. For anyone weighing options in {loc}, the "
    )
    about_em = "combination of modern clinical standards and a team that explains everything up front is what keeps patients coming back"
    about_b = (
        f", not just proximity or a slightly lower price. Every patient is "
        f"treated with the same attention regardless of how long they have been "
        f"coming in, and questions are answered before treatment, not after the "
        f"invoice. Booking a first visit is simple, and you will know exactly "
        f"what to expect before you walk in, including what it will actually "
        f"cost once insurance is factored in. Follow-up calls after a "
        f"procedure are routine here, not reserved for the cases that go "
        f"wrong, and a real person answers when you call with a question "
        f"instead of routing you to a general voicemail box."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _home_services_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. The company provides {svc_phrase}, and every job "
        f"starts with a clear written estimate so you know what is recommended, "
        f"why it matters, and what it will cost before any work begins. "
        f"Customers choose {business_name} because technicians show up on time, "
        f"the work is explained in plain language, and pricing is given up "
        f"front with no surprise charges afterward. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and the same technicians handle a job from the first call through completion. "
    p1_rest += (
        f"New customers are treated the same as long-standing ones, with time "
        f"taken to answer questions before anything is scheduled. "
        f"Whether the job is routine maintenance or an emergency, the fastest "
        f"way to get help is to call and describe the problem, and dispatch "
        f"will find the earliest available technician. Trucks are stocked for "
        f"the most common repairs, so a second trip just to grab a part is "
        f"rare. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and how we work'
    p1_trailing = f" before you call."
    p2_a = (
        f"Every job at {business_name} starts with a real inspection and a "
        f"written estimate, so you understand the recommendation and the price "
        f"before agreeing to anything. "
    )
    em_clause = "Doing the job right the first time is the foundation of everything here"
    p2_b = (
        f", because catching a small problem early is far cheaper than "
        f"repairing it after it fails. The team serves {areas} and keeps the "
        f"schedule tight, so most jobs are completed in a single visit without a "
        f"second trip or a referral elsewhere. For customers who have been let "
        f"down before, {business_name} stands behind the work and the "
        f"warranty that comes with it, so you are not left to chase anyone down "
        f"after the job is done. The same standard applies to small repairs and "
        f"full installations alike: the technician who quotes the work is the "
        f"one who does it, and nothing is added to the bill without discussing "
        f"it with you first. Cleanup is part of the job, not an afterthought "
        f"left for the customer."
    )
    about_a = (
        f"{business_name} has served {areas} for years, and many customers "
        f"call back the same crew every time rather than starting over with a "
        f"stranger. That continuity means less time re-explaining the same "
        f"problem and more time actually fixing it, and it means the crew "
        f"already knows the layout of your home or building. If you are "
        f"comparing options in {loc}, the "
    )
    about_em = "combination of upfront pricing and a crew that actually shows up on time is what customers mention most"
    about_b = (
        f", along with a dispatcher who answers the phone and technicians who "
        f"follow through on the schedule they give you. New customers get the "
        f"same treatment as long-standing ones, and every job is documented so "
        f"the next visit picks up exactly where the last one left off. Booking "
        f"is straightforward, and you will always know who is coming and what "
        f"it will cost before anyone shows up, with no last-minute changes to "
        f"the quote."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _home_services_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. Services include {svc_phrase}, and calls are "
        f"answered by a real person, not a queue, whether the job is a routine "
        f"repair or something that cannot wait until tomorrow. "
    )
    if creds:
        p1_rest += f"The company is {creds}, so every job is backed by real coverage, not just a promise. "
    p1_rest += (
        f"Every job comes with a workmanship guarantee, and if something is not "
        f"right after the crew leaves, {business_name} comes back and fixes it "
        f"at no extra charge. New customers get the same response time as "
        f"long-standing ones, and same-day service is available for genuine "
        f"emergencies. The office confirms the appointment window in advance, "
        f"so you are not stuck waiting around all day for a truck that might "
        f"show up. Technicians call ahead when they are on the way, so you can "
        f"plan around the visit instead of sitting by the door. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and what we guarantee'
    p1_trailing = f" before you call."
    p2_a = (
        f"When something breaks, {business_name} treats speed and quality as "
        f"the same goal, not a trade-off — a rushed repair that fails again in "
        f"a month costs everyone more than doing it right the first time. "
    )
    em_clause = "A fast response only matters if the fix actually holds"
    p2_b = (
        f", which is why every technician is trained to diagnose the real "
        f"problem before starting work, not just treat the symptom that got the "
        f"call placed. The team covers {areas} and keeps trucks stocked so most "
        f"repairs are finished in one visit. If a job turns out to be bigger "
        f"than expected, you hear about it before the work continues, never "
        f"after. The warranty on labor and materials is explained up front, in "
        f"writing, so there is nothing to dispute later, and it applies "
        f"whether the fix was simple or took the whole crew a full day. Old "
        f"parts and materials are hauled away when the job is done, not left "
        f"for the customer to deal with, and the work area is left as clean as "
        f"it was found."
    )
    about_a = (
        f"{business_name} has worked in {areas} long enough that a lot of the "
        f"calls now come from repeat customers or their referrals, not cold "
        f"searches. That track record is the actual reason to trust a workmanship "
        f"guarantee — it only means something if the company is still around to "
        f"honor it years later. If you are comparing options in {loc}, the "
    )
    about_em = "guarantee behind the work, not just the estimate in front of it, is what actually protects you"
    about_b = (
        f", along with technicians who explain what they are doing rather than "
        f"working behind closed doors. Every customer gets a written summary of "
        f"what was done and what is covered, and the office keeps that record "
        f"on file for next time. Scheduling a call is quick, and you will know "
        f"the price and the coverage before anyone starts work, not after the "
        f"invoice arrives. Repeat visits to the same address are common here, "
        f"and the crew keeps notes on what was done last time, so a follow-up "
        f"job never starts from a blank slate."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _legal_finance_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" representing clients throughout {areas}. The firm handles "
        f"{svc_phrase}, and every matter begins with a direct conversation "
        f"about what is actually at stake, what the realistic options are, and "
        f"what it will cost before any work is billed. "
        f"Clients choose {business_name} because they speak directly with the "
        f"person handling their case, not a rotating cast of assistants, and "
        f"fee arrangements are explained in writing up front. "
    )
    if creds:
        p1_rest += f"The firm is {creds}, and every client is briefed on where their matter actually stands, not just told it is being handled. "
    p1_rest += (
        f"New clients receive the same attention as long-standing ones, with "
        f"time set aside for a real consultation before anything is filed. "
        f"Documents and deadlines are tracked closely, so nothing slips through "
        f"the cracks between meetings. The firm returns calls the same day "
        f"whenever possible, and a client should never have to guess who to "
        f"call for an update. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and how matters are handled'
    p1_trailing = f" before you reach out."
    p2_a = (
        f"Every matter at {business_name} starts with a full review of the "
        f"facts and a candid assessment of the realistic outcomes, not a sales "
        f"pitch about guaranteed results no one can actually promise. "
    )
    em_clause = "An honest assessment early is worth more than false confidence later"
    p2_b = (
        f", because clients who understand the real risks make better decisions "
        f"about how to proceed. The firm serves {areas} and returns calls "
        f"promptly, so clients are not left wondering what is happening with "
        f"their own case. For clients who have felt unheard elsewhere, "
        f"{business_name} explains each step before it happens and answers "
        f"questions directly rather than deferring them. The same standard "
        f"applies to routine matters and complex ones alike: fees are agreed to "
        f"in writing before work begins, and nothing is billed that was not "
        f"discussed first. Filings and deadlines are handled proactively, not "
        f"at the last possible moment. If a matter turns out to be more "
        f"involved than the initial estimate suggested, that gets flagged "
        f"before more work is done, not buried in the next invoice."
    )
    about_a = (
        f"{business_name} has represented clients across {areas} for years, "
        f"and many come back for future matters or refer family members "
        f"directly. That kind of trust is not built on advertising — it comes "
        f"from clients actually understanding where their case stands at every "
        f"step, not just being told to wait. If you are comparing counsel in "
        f"{loc}, the "
    )
    about_em = "combination of direct access to the attorney handling your case and fee clarity in writing is what clients mention most"
    about_b = (
        f", not just reputation or a firm's size. Every client gets a real "
        f"consultation, not a rushed intake call, and every matter is "
        f"documented so nothing has to be re-explained at the next meeting. "
        f"Scheduling a consultation is straightforward, and you will know the "
        f"realistic path forward and the cost before you commit to anything, "
        f"with no pressure to decide on the spot. Questions between meetings "
        f"are welcomed rather than saved up for the next billed hour, since a "
        f"client who understands what is happening makes better decisions "
        f"along the way."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _legal_finance_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving clients across {areas}. Practice areas include "
        f"{svc_phrase}, and every engagement follows the same process: a real "
        f"review of the situation, a written explanation of the options, and "
        f"an agreed fee structure before any work begins. Clients get a real "
        f"person on the phone when they call, not an automated queue that "
        f"never reaches anyone. "
    )
    if creds:
        p1_rest += f"{business_name} is {creds}, and that experience is applied to your specific situation, not a generic template. "
    p1_rest += (
        f"Clients are updated as their matter progresses rather than left to "
        f"wonder, and calls are returned within a reasonable window, not weeks "
        f"later. New clients receive the same responsiveness as clients who "
        f"have worked with the firm for years, from the very first call. "
        f"Every document the firm sends is written in plain language first, "
        f"with the legal terminology explained rather than left to guess at. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach'
    p1_trailing = f" before scheduling a consultation."
    p2_a = (
        f"{business_name} treats a clear fee structure as part of good "
        f"representation, not a separate conversation to have later — clients "
        f"should never be surprised by a bill for work they did not know was "
        f"happening. "
    )
    em_clause = "Clients who understand the plan and the cost make better decisions than clients who are just told to trust the process"
    p2_b = (
        f", which is why every matter starts with both laid out in writing. "
        f"The firm serves {areas} and structures communication so clients "
        f"always know the current status of their case without having to ask. "
        f"Complex matters get the same transparency as simple ones: what is "
        f"being done, why it is being done, and what it costs, explained before "
        f"it happens rather than justified after the invoice arrives. Any "
        f"change in strategy is discussed with the client first, not decided "
        f"unilaterally, and the reasoning behind that change is always laid "
        f"out plainly rather than assumed to be self-explanatory."
    )
    about_a = (
        f"{business_name} has worked with clients throughout {areas} long "
        f"enough to see the same situations come up again and again, which "
        f"means less time explaining the basics and more time on what is "
        f"actually specific to your matter, from day one. For anyone comparing "
        f"representation in {loc}, the "
    )
    about_em = "responsiveness and the fee clarity are what clients bring up first when they refer someone else"
    about_b = (
        f", more than any single case result. Every client gets direct access "
        f"to the person handling their matter, and every conversation is "
        f"documented so there is a clear record of what was discussed and "
        f"agreed. Scheduling an initial consultation is simple, and you will "
        f"leave it understanding your real options, not just a sales pitch, "
        f"and with a straight answer about what happens next. Every question "
        f"gets a real answer during that first conversation, not a promise to "
        f"follow up once someone has had a chance to look into it. Billing "
        f"statements are itemized in plain language too, so a client can "
        f"actually see what each charge covers."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _beauty_salon_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" welcoming clients from {areas}. The studio offers {svc_phrase}, and "
        f"every appointment starts with a real consultation, not a rushed "
        f"guess, so you leave with something you actually asked for. "
        f"Clients choose {business_name} because the same stylist sees you "
        f"appointment after appointment, product recommendations are honest "
        f"rather than upsold, and pricing is clear before anything begins. "
        f"Rebooking your next visit before you leave is offered, never "
        f"required. "
    )
    if creds:
        p1_rest += f"The team is {creds}, trained on current techniques rather than whatever was standard years ago. "
    p1_rest += (
        f"New clients get the same unhurried consultation as regulars, with "
        f"time to talk through what you actually want before any work starts, "
        f"including a real conversation about what your hair or skin can "
        f"actually support. Tools and stations are sanitized between every "
        f"single client, not just at the start of the day. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach'
    p1_trailing = f" before you book."
    p2_a = (
        f"Every appointment at {business_name} starts with a real "
        f"conversation about what you want, not an assumption based on what is "
        f"trending, so the result actually matches what you asked for. "
    )
    em_clause = "A service that starts with real listening is the difference between a client who comes back and one who does not"
    p2_b = (
        f", and that consultation is treated as part of the service, not a "
        f"formality before the real work begins. The studio serves {areas} and "
        f"books realistic appointment lengths, so no one is rushed through a "
        f"service that deserves more time. For clients who have felt talked "
        f"into something before, {business_name} explains the options and the "
        f"trade-offs honestly, including when a simpler service is the better "
        f"call. The same care applies to a quick trim and a full color "
        f"correction alike: technique is explained, products are chosen for "
        f"your actual hair or skin, and nothing is added to the service without "
        f"asking first. Aftercare guidance is part of the appointment too, so "
        f"the result actually holds up once you get home, not just when you "
        f"walk out the door."
    )
    about_a = (
        f"{business_name} has built a client base across {areas} largely "
        f"through referrals, which only happens when people are genuinely happy "
        f"with the result, not just polite about it. That kind of trust takes "
        f"time to earn, and it shows in how many appointments are booked months "
        f"in advance by the same regulars. If you are comparing studios in "
        f"{loc}, the "
    )
    about_em = "consistency of seeing the same stylist and getting an honest consultation every time is what clients mention most"
    about_b = (
        f", more than any single service on a menu. New clients get the same "
        f"attention as long-standing regulars, and stylist notes are kept on "
        f"file so your preferences carry over from visit to visit. Booking is "
        f"simple, and you will always know the service, the price, and roughly "
        f"how long it will take before you sit down, with no guessing once you "
        f"arrive, and no pressure to add a service you did not come in for."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _beauty_salon_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. Services include {svc_phrase}, in a space built "
        f"for the appointment to actually feel relaxing, not rushed between "
        f"back-to-back bookings. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and product lines are chosen for quality, not just what is cheapest to stock. "
    p1_rest += (
        f"Appointments are booked with real time built in, so a service never "
        f"has to be cut short to stay on schedule. New clients get a full "
        f"consultation before any service begins, the same as returning "
        f"clients, so nothing is guessed at once you are in the chair. The "
        f"space itself is kept quiet and unhurried on purpose, not just "
        f"decorated to look that way in photos. Playlists and lighting are "
        f"kept low-key rather than loud, on purpose, so the appointment "
        f"actually feels like a break. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and the experience'
    p1_trailing = f" before you book."
    p2_a = (
        f"{business_name} treats the actual experience of an appointment as "
        f"part of the service, not just the technical result — how relaxed you "
        f"feel matters as much as how it looks when you leave. "
    )
    em_clause = "A great result delivered in a rushed, stressful appointment is not actually a great experience"
    p2_b = (
        f", which is why appointments are never double-booked and stylists are "
        f"never working two clients at once. The studio serves {areas} and "
        f"keeps the space genuinely comfortable, not just photogenic. Product "
        f"recommendations are based on what your hair or skin actually needs, "
        f"not what is being pushed that month, and you will never be talked "
        f"into a service you did not ask about. Every stylist is given real "
        f"time between appointments, so the next client never feels like an "
        f"interruption to the last one, and no one is watching the clock while "
        f"you are still in the chair. If a service is going to run long because "
        f"of something the stylist notices once they actually get started, you "
        f"are told before it happens, not left wondering why the appointment is "
        f"taking longer than expected."
    )
    about_a = (
        f"{business_name} has served clients across {areas} long enough that "
        f"many appointments now come from referrals rather than searches, which "
        f"is the real measure of whether an experience holds up beyond the "
        f"first visit and a nice photo. Word of mouth is the only advertising "
        f"that actually matters in this business, and it only happens when the "
        f"appointment itself was worth talking about. If you are comparing "
        f"options in {loc}, the "
    )
    about_em = "combination of unrushed appointments and an honest consultation every time is what keeps clients coming back"
    about_b = (
        f", more than any single treatment. New clients are given the same "
        f"time and attention as long-standing regulars, and preferences are "
        f"noted so you do not have to re-explain them at every visit. Booking "
        f"is simple, and you will know the service and the price before you "
        f"arrive, with real time built into the appointment itself and no "
        f"pressure to add anything once you are already in the chair. Gift "
        f"cards and rebooking are handled at the front desk in a couple of "
        f"minutes, not treated as an inconvenience on your way out."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _food_restaurant_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. The menu includes {svc_phrase}, made from "
        f"ingredients chosen for quality rather than whatever is cheapest to "
        f"source that week. "
        f"Guests choose {business_name} because dishes are made to order, "
        f"not reheated from a batch, and the kitchen is genuinely willing to "
        f"accommodate real dietary needs rather than just saying yes and "
        f"hoping. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and that standard shows in how consistently the food comes out. "
    p1_rest += (
        f"Whether you are stopping in for a quick meal or planning a larger "
        f"gathering, the staff will help you find something that actually works "
        f"for the occasion, not just point you at whatever is easiest to fire. "
        f"Portions and pricing are consistent from visit to visit, not "
        f"adjusted quietly depending on how busy the kitchen is. Takeout "
        f"orders are packed to actually survive the drive home, not thrown "
        f"together at the last second. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our kitchen'
    p1_trailing = f" before you visit."
    p2_a = (
        f"Every dish at {business_name} starts with ingredients chosen the "
        f"same day, not a freezer pulled from on a slow night, because the "
        f"difference is obvious the moment it hits the table. "
    )
    em_clause = "Consistency is what actually keeps people coming back, not one great meal followed by three forgettable ones"
    p2_b = (
        f", so the kitchen treats every plate with the same standard whether "
        f"it is a Tuesday lunch or a Saturday rush. The restaurant serves "
        f"{areas} and keeps the kitchen staffed to handle real volume without "
        f"cutting corners when it gets busy. For guests with dietary "
        f"restrictions, the kitchen will tell you honestly what can and cannot "
        f"be safely adjusted, rather than guessing. The same care applies to a "
        f"simple order and a full table alike: nothing goes out that the "
        f"kitchen would not be comfortable eating themselves, whether it is a "
        f"solo lunch order or a party of twelve, and nothing is quietly "
        f"substituted without telling you first. If an ingredient is not "
        f"available, that gets said up front, rather than swapped in silently "
        f"and hoping no one notices."
    )
    about_a = (
        f"{business_name} has served {areas} long enough that a lot of guests "
        f"now come in as regulars, not first-time visitors, which is the real "
        f"test of whether a kitchen actually holds up over time rather than "
        f"just impressing once. If you are deciding where to eat in {loc}, the "
    )
    about_em = "consistency of the food and a staff that actually knows the regulars is what people mention most"
    about_b = (
        f", more than any single dish. New guests are treated with the same "
        f"attention as regulars, and the kitchen keeps its standards the same "
        f"whether the room is half full or completely booked. Reservations are "
        f"simple to make, and walk-ins are genuinely welcome, not just "
        f"tolerated, even during a busy rush, and the wait is honestly quoted "
        f"rather than guessed at. Groups are accommodated with the same care "
        f"as a table for two, not treated as an inconvenience to squeeze in."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _food_restaurant_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" welcoming guests from {areas}. The menu features {svc_phrase}, "
        f"served in a space built for people to actually stay and enjoy the "
        f"meal, not just eat quickly and leave. "
    )
    if creds:
        p1_rest += f"The kitchen is {creds}, and that shows in how the food is put together, not just how it is plated. "
    p1_rest += (
        f"Tables are never rushed, and the staff genuinely wants to talk "
        f"through the menu with you if you want recommendations rather than "
        f"pointing at the specials board and moving on. Reservations are "
        f"accepted, and walk-ins are handled with the same welcome, even on a "
        f"busy night. The dining room is arranged so conversation is actually "
        f"possible, not competing with music turned up to fill a loud space. "
        f"Special occasions are noted ahead of time whenever a guest mentions "
        f"one, so the evening actually feels marked rather than routine. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and the space'
    p1_trailing = f" before you book a table."
    p2_a = (
        f"{business_name} treats the atmosphere of a meal as seriously as "
        f"what is on the plate — a great dish served in a rushed, loud, "
        f"stressful room is a different experience than the same dish enjoyed "
        f"slowly. "
    )
    em_clause = "The room and the pace of service matter as much as the food itself"
    p2_b = (
        f", which is why tables are not turned over faster than the meal "
        f"naturally moves. The restaurant serves {areas} and keeps the dining "
        f"room comfortable rather than packed past capacity to squeeze in more "
        f"covers. Staff know the menu well enough to answer real questions "
        f"about ingredients and preparation, not just recite the description "
        f"printed on the card, and they will say so honestly if they do not "
        f"know rather than guessing. Pacing between courses is handled "
        f"deliberately, not left to whoever happens to be free in the kitchen, "
        f"and a table is never rushed toward the check before anyone at it is "
        f"actually ready. Wine and pairing suggestions are offered without "
        f"being pushed, and a straightforward answer is always available for "
        f"anyone who would rather just order and skip the conversation."
    )
    about_a = (
        f"{business_name} has become a regular stop for guests across "
        f"{areas}, the kind of place people return to for a specific occasion "
        f"rather than just when nothing else is open. Word of mouth is what "
        f"actually fills tables here, not a rotating list of promotions. If "
        f"you are choosing where to eat in {loc}, the "
    )
    about_em = "combination of an unhurried atmosphere and a kitchen that actually cares about consistency is what guests mention most"
    about_b = (
        f", more than any single dish on the menu. New guests get the same "
        f"attention as regulars, and the kitchen holds the same standard "
        f"whether the room is quiet or completely full. Booking a table is "
        f"simple, and walk-ins are genuinely accommodated whenever there is "
        f"room, not just squeezed in as an afterthought, and the wait staff "
        f"will tell you honestly how long that might take rather than "
        f"promising a table that is not actually close to ready."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _general_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. The business provides {svc_phrase}, and every "
        f"engagement starts with a clear conversation about what is being "
        f"recommended, why it matters, and what it will cost before anything "
        f"begins. "
        f"Clients choose {business_name} because communication is direct, "
        f"pricing is explained up front, and the same team follows a request "
        f"from the first conversation through completion, rather than handing "
        f"it off partway through. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and that background is applied to your situation specifically, not a generic template. "
    p1_rest += (
        f"New clients get the same attention as long-standing ones, with real "
        f"time set aside to answer questions before anything is scheduled, and "
        f"nothing is assumed about what you need before it is actually "
        f"discussed. "
        f"Whether the request is routine or time-sensitive, the fastest way to "
        f"get a real answer is to reach out directly and describe the "
        f"situation, and a member of the team will follow up promptly. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and how we work'
    p1_trailing = f" before you reach out."
    p2_a = (
        f"Every request at {business_name} starts with a real assessment of "
        f"the situation and a clear explanation of the options, not a "
        f"one-size-fits-all answer applied to everyone who calls. "
    )
    em_clause = "Understanding the actual situation before recommending anything is what everything else depends on"
    p2_b = (
        f", because the right answer for one client is rarely the right answer "
        f"for the next, even when the requests sound similar on the surface. "
        f"{business_name} serves {areas} and keeps communication direct, so "
        f"clients are not left guessing about status or cost partway through. "
        f"For clients who have been left waiting elsewhere, {business_name} "
        f"sets clear expectations up front and follows through on them rather "
        f"than revising the plan quietly. The same standard applies to small "
        f"requests and larger ones alike: nothing is added or changed without "
        f"discussing it with you first, and the person who scoped the work is "
        f"the one who actually sees it through."
    )
    about_a = (
        f"{business_name} has worked with clients across {areas} for years, "
        f"and many come back for future needs or refer others directly rather "
        f"than searching for someone new each time. That kind of trust is "
        f"built through follow-through, not marketing, and it shows in how "
        f"often the same names come up again. If you are comparing options in "
        f"{loc}, the "
    )
    about_em = "directness and the follow-through are what clients mention most, more than any single project"
    about_b = (
        f". New clients are treated with the same care as long-standing ones, "
        f"and every request is documented so nothing has to be re-explained "
        f"next time you reach out. Getting in touch is simple, and you will "
        f"know what to expect, what it will cost, and roughly how long it will "
        f"take before you commit to anything. Follow-up questions after the "
        f"work is done are answered the same way the first ones were, not "
        f"treated as an afterthought once the invoice is paid."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _general_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving clients across {areas}. Services include {svc_phrase}, "
        f"and every new client gets a real conversation about their situation "
        f"before any work is scoped or scheduled, not a generic quote pulled "
        f"from a price sheet. "
    )
    if creds:
        p1_rest += f"{business_name} is {creds}, and that experience shapes how requests are actually handled, not just how they are advertised. "
    p1_rest += (
        f"Clients are kept informed as work progresses rather than left to "
        f"wonder, and questions are answered directly instead of deferred to a "
        f"callback that never comes. New clients receive the same "
        f"responsiveness as clients who have worked with {business_name} for "
        f"years, and no request is treated as too small to explain properly. "
        f"Whether the need is routine or time-sensitive, the fastest way to get "
        f"a straight answer is to reach out directly and describe the "
        f"situation, and someone will follow up with real next steps rather "
        f"than a form response. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach'
    p1_trailing = f" before reaching out."
    p2_a = (
        f"{business_name} treats clear communication as part of the work "
        f"itself, not a separate courtesy — clients should never be surprised "
        f"by cost, timeline, or scope partway through, and none of that should "
        f"have to be pried out of anyone. "
    )
    em_clause = "Clients who understand the plan make better decisions than clients who are just asked to trust the process"
    p2_b = (
        f", which is why expectations are set in writing before work begins, "
        f"not summarized verbally and forgotten. {business_name} serves "
        f"{areas} and structures updates so clients always know current status "
        f"without having to ask twice. Complex requests get the same "
        f"transparency as simple ones, explained as they happen rather than "
        f"justified afterward, and any change to scope is discussed before it "
        f"is acted on, not after it shows up on an invoice. That standard "
        f"applies whether the request is a one-time job or an ongoing "
        f"relationship, and it is the reason many clients come back the next "
        f"time they need the same kind of help."
    )
    about_a = (
        f"{business_name} has worked with clients throughout {areas} long "
        f"enough to recognize the same needs coming up again and again, which "
        f"means less time spent on the basics and more time on what is "
        f"actually specific to your situation. Repeat clients are common here, "
        f"and that only happens when the last job actually went the way it was "
        f"described up front. For anyone comparing options in {loc}, the "
    )
    about_em = "responsiveness and the follow-through are what clients bring up first when they refer someone else"
    about_b = (
        f", more than any single project. Every client gets direct "
        f"communication with the people actually doing the work, not a "
        f"go-between, and requests are documented so there is a clear record "
        f"of what was agreed at every stage. Getting started is simple, and "
        f"you will understand the real plan, the timeline, and the cost before "
        f"you commit to anything — no vague estimate that turns into a "
        f"different number once the work is already underway, and no surprise "
        f"add-ons once the work is finished."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _real_estate_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving buyers and sellers throughout {areas}. The agency provides "
        f"{svc_phrase}, and every relationship starts with a direct, honest "
        f"read on the market: what a property is actually worth, what it will "
        f"realistically take to sell or buy it, and what the timeline looks "
        f"like before anything is signed. Clients choose {business_name} "
        f"because they work directly with the agent handling their "
        f"transaction, not a rotating cast of assistants, and expectations are "
        f"set clearly from the first conversation. "
    )
    if creds:
        p1_rest += f"The agency is {creds}, and licensing details are something clients are welcome to ask about directly. "
    p1_rest += (
        f"New clients get the same attention as long-standing ones, with real "
        f"time set aside to walk through the process before anything is "
        f"listed or offered on. Paperwork and deadlines are tracked closely, "
        f"so nothing slips between showings, inspections, and closing. Every "
        f"disclosure and contingency is explained in plain language before a "
        f"client signs anything, not summarized in a rush at the closing "
        f"table. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and how transactions are handled'
    p1_trailing = f" before you reach out."
    p2_a = (
        f"Every listing at {business_name} starts with a real, current read "
        f"on comparable sales in the area, not a number pulled out of thin "
        f"air to win the listing. "
    )
    em_clause = "Pricing a property honestly from day one is what actually gets it sold, not a high number that just sits on the market"
    p2_b = (
        f", because an overpriced listing sits, buyers watch it go stale, and "
        f"the eventual sale price ends up lower than an honest one would have "
        f"been from the start. The agency serves {areas} and stays responsive "
        f"through every stage of a transaction, so clients are not left "
        f"wondering what happens next. For clients who have felt ignored "
        f"elsewhere, {business_name} explains each step before it happens and "
        f"answers questions directly rather than deferring them to voicemail. "
        f"The same standard applies to a straightforward sale and a "
        f"complicated one alike: offers and counteroffers are explained "
        f"clearly, financing contingencies are tracked closely, and nothing "
        f"moves forward without the client actually understanding it first. "
        f"Inspection findings and repair requests are handled proactively, "
        f"not left until the closing table."
    )
    about_a = (
        f"{business_name} has represented buyers and sellers across {areas} "
        f"for years, and many clients come back for their next move or refer "
        f"family members directly. That kind of trust is not built on a yard "
        f"sign — it comes from clients actually understanding where their "
        f"transaction stands at every step, not just being told to wait for "
        f"good news. If you are comparing agents in {loc}, the "
    )
    about_em = "combination of direct access to the agent handling your transaction and a straight read on pricing is what clients mention most"
    about_b = (
        f", not just a firm's name recognition. Every client gets a real "
        f"conversation about strategy, not a rushed pitch, and every "
        f"transaction is documented so nothing has to be re-explained at the "
        f"next step. Reaching out is simple, and you will know the realistic "
        f"timeline and the real numbers before you commit to anything, with "
        f"no pressure to sign on the spot. Questions after an offer is "
        f"accepted get the same attention as questions before it, all the "
        f"way through to closing day."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _real_estate_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" helping buyers and sellers move through {areas}. Services include "
        f"{svc_phrase}, and every client gets a straight answer about timing "
        f"and price, not the number that sounds best in a first meeting. "
        f"Weekend and evening showings are available, not limited to a "
        f"nine-to-five window that rarely fits a buyer's actual schedule. "
    )
    if creds:
        p1_rest += f"{business_name} is {creds}, and that experience is applied to your specific property and situation, not a generic script. "
    p1_rest += (
        f"Clients are kept informed at every stage of a transaction rather "
        f"than left checking a portal for updates, and calls are returned the "
        f"same day, not days later. New clients get the same responsiveness "
        f"as clients who have bought or sold with {business_name} before. "
        f"Showings are scheduled around a client's actual availability, not "
        f"whatever slot happens to be easiest to fill. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach'
    p1_trailing = f" before scheduling a showing."
    p2_a = (
        f"{business_name} treats a clear, current market read as part of "
        f"good representation, not a separate conversation to have after a "
        f"client has already fallen in love with a number. "
    )
    em_clause = "A price built on real comparables, not wishful thinking, is what actually protects a client's timeline and their money"
    p2_b = (
        f", which is why every listing starts with both laid out honestly, "
        f"in writing. The agency serves {areas} and structures communication "
        f"so clients always know the current status of their transaction "
        f"without having to chase an answer. Complex transactions — "
        f"financing contingencies, inspection negotiations, tight closing "
        f"timelines — get the same transparency as simple ones: what is "
        f"happening, why it matters, and what it means for the client, "
        f"explained before it happens rather than after an offer falls "
        f"through. Any change in strategy is discussed with the client "
        f"first, never decided unilaterally on their behalf. Comparable "
        f"listings are shared as they come up, not just at the start of a "
        f"search, so a client's sense of the market stays current all the "
        f"way through closing."
    )
    about_a = (
        f"{business_name} has worked with buyers and sellers throughout "
        f"{areas} long enough to have seen most situations a transaction can "
        f"throw at a client, which means less time explaining the basics and "
        f"more time on what is actually specific to your property, from the "
        f"very first walkthrough. For anyone comparing representation in "
        f"{loc}, the "
    )
    about_em = "responsiveness and the honesty about real market numbers are what clients bring up first when they refer someone else"
    about_b = (
        f", more than any single closing. Every client gets direct access to "
        f"the agent actually handling their transaction, and every "
        f"conversation is documented so there is a clear record of what was "
        f"discussed and agreed. Scheduling a first conversation is simple, "
        f"and you will leave it understanding your real options and the real "
        f"numbers, not just a pitch, with a straight answer about what "
        f"happens next. Questions that come up between showings get a real "
        f"answer the same day, not a promise to circle back once things slow "
        f"down."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _nail_spa_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" welcoming clients from {areas}. The studio offers {svc_phrase}, "
        f"and every appointment starts with a real conversation about what "
        f"you actually want, not a rushed guess. Clients choose "
        f"{business_name} because the same technician sees you appointment "
        f"after appointment, product recommendations are honest rather than "
        f"upsold, and pricing is clear before anything begins. Walk-ins are "
        f"accommodated when the schedule allows, but a booked appointment "
        f"always gets priority. "
    )
    if creds:
        p1_rest += f"The team is {creds}, trained on current techniques and sanitation standards rather than whatever was standard years ago. "
    p1_rest += (
        f"New clients get the same unhurried consultation as regulars, with "
        f"time to talk through what you want and what your skin or nails can "
        f"actually support before any service starts. Instruments are single "
        f"use or fully sterilized between clients, and that standard is "
        f"visible, not just claimed. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and our approach'
    p1_trailing = f" before you book."
    p2_a = (
        f"Every appointment at {business_name} starts with a real "
        f"conversation about what you want, not an assumption based on what "
        f"is trending, so the result actually matches what you asked for. "
    )
    em_clause = "Real hygiene standards and a technician who actually listens are what turn a one-time visit into a regular appointment"
    p2_b = (
        f", and that consultation is treated as part of the service, not a "
        f"formality before the real work begins. The studio serves {areas} "
        f"and books realistic appointment lengths, so no one is rushed "
        f"through a service that deserves more time. Tools and stations are "
        f"sanitized between every single client, not just at the start of "
        f"the day, and that standard is not something you have to ask about "
        f"— it is simply how the studio runs. For clients who have felt "
        f"rushed elsewhere, {business_name} explains the options and the "
        f"trade-offs honestly, including when a simpler service is the "
        f"better call for the occasion. Aftercare guidance is part of the "
        f"appointment too, so the result actually holds up once you get "
        f"home, not just when you leave the chair."
    )
    about_a = (
        f"{business_name} has built a client base across {areas} largely "
        f"through referrals, which only happens when people are genuinely "
        f"happy with the result, not just polite about it. That kind of "
        f"trust takes time to earn, and it shows in how many appointments "
        f"are booked weeks in advance by the same regulars. If you are "
        f"comparing studios in {loc}, the "
    )
    about_em = "consistency of seeing the same technician and a genuinely clean, unhurried space every time is what clients mention most"
    about_b = (
        f", more than any single service on a menu. New clients get the "
        f"same attention as long-standing regulars, and technician notes are "
        f"kept on file so your preferences carry over from visit to visit. "
        f"Booking is simple, and you will always know the service, the "
        f"price, and roughly how long it will take before you sit down, with "
        f"no guessing once you arrive, and no pressure to add anything you "
        f"did not come in for."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _nail_spa_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving {areas}. Services include {svc_phrase}, in a space built "
        f"for the appointment to actually feel relaxing, not rushed between "
        f"back-to-back bookings. "
    )
    if creds:
        p1_rest += f"The team is {creds}, and product lines are chosen for quality and safety, not just what is cheapest to stock. "
    p1_rest += (
        f"Appointments are booked with real time built in, so a service "
        f"never has to be cut short to stay on schedule. New clients get a "
        f"full consultation before any service begins, the same as returning "
        f"clients, so nothing is guessed at once you are seated. The space "
        f"itself is kept quiet, clean, and unhurried on purpose, not just "
        f"decorated to look that way in photos. Sanitation between clients "
        f"is visible and consistent, not something you have to take on "
        f"faith. "
        f'You can also read more '
    )
    about_link_text = f'about {business_name} and the experience'
    p1_trailing = f" before you book."
    p2_a = (
        f"{business_name} treats the actual experience of an appointment as "
        f"part of the service, not just the technical result — how relaxed "
        f"and cared for you feel matters as much as how it looks when you "
        f"leave. "
    )
    em_clause = "A great result delivered in a rushed, uncomfortable appointment is not actually a great experience"
    p2_b = (
        f", which is why appointments are never double-booked and "
        f"technicians are never working two clients at once. The studio "
        f"serves {areas} and keeps the space genuinely comfortable, not just "
        f"photogenic. Product and technique recommendations are based on "
        f"what your skin or nails actually need, not what is being pushed "
        f"that month, and you will never be talked into a service you did "
        f"not ask about. Every technician is given real time between "
        f"appointments, so the next client never feels like an interruption "
        f"to the last one, and no one is watching the clock while you are "
        f"still in the chair. If a service is going to run long because of "
        f"something the technician notices once they actually get started, "
        f"you are told before it happens, not left wondering why the "
        f"appointment is taking longer than expected."
    )
    about_a = (
        f"{business_name} has served clients across {areas} long enough "
        f"that many appointments now come from referrals rather than "
        f"searches, which is the real measure of whether an experience holds "
        f"up beyond the first visit and a nice photo. Word of mouth is the "
        f"only advertising that actually matters in this business, and it "
        f"only happens when the appointment itself was worth talking about. "
        f"If you are comparing options in {loc}, the "
    )
    about_em = "combination of unrushed appointments and real hygiene standards you can actually see is what keeps clients coming back"
    about_b = (
        f", more than any single treatment. New clients are given the same "
        f"time and attention as long-standing regulars, and preferences are "
        f"noted so you do not have to re-explain them at every visit. "
        f"Booking is simple, and you will know the service and the price "
        f"before you arrive, with real time built into the appointment "
        f"itself and no pressure to add anything once you are already "
        f"seated."
    )
    return open_clause, p1_rest, about_link_text, p1_trailing, p2_a, em_clause, p2_b, about_a, about_em, about_b


_FAMILIES = {
    "dental_medical": [_dental_medical_0, _dental_medical_1],
    "home_services": [_home_services_0, _home_services_1],
    "legal_finance": [_legal_finance_0, _legal_finance_1],
    "beauty_salon": [_beauty_salon_0, _beauty_salon_1],
    "food_restaurant": [_food_restaurant_0, _food_restaurant_1],
    "general": [_general_0, _general_1],
    "real_estate": [_real_estate_0, _real_estate_1],
    "nail_spa": [_nail_spa_0, _nail_spa_1],
}


def _prose_family_for(subtype):
    """Refines the shared industry_family_for() classifier specifically for
    prose selection.

    2026-08-21, Opus review: industry_family_for() is deliberately coarse --
    correct for palette/template choice, since color and layout don't make
    factual claims -- but prose asserts specific professional facts ("the
    attorney handling your case", "what your hair or skin can actually
    support") that are false when a coarse family lumps together professions
    that don't share those facts. A "Real Estate" business landing in the
    legal_finance family's prose literally told clients they get "direct
    access to the attorney handling your case" -- a false professional
    claim, not a tone miss. "Nail Salon"/"Med Spa" landing in beauty_salon's
    hair-specific prose said "what your hair or skin can actually support"
    and offered "a quick trim and a full color correction" -- neither
    subtype gets a haircut.

    Deliberately does NOT touch palettes.industry_family_for() itself --
    that classifier is correct as-is for palette/template selection, and is
    also the single shared source of truth template_for()/palette_for()
    both call; splitting it here would risk exactly the "two independently-
    maintained classifiers can drift" defect class already fixed once this
    session. This is an additive refinement layered on top, used only by
    prose selection.

    2026-08-21, Opus review round 2: this function's first draft used plain
    substring checks ("spa" in s), inheriting the exact "spa"-inside-
    "Spanish" collision already documented as accepted-for-palette/
    template-purposes in tests/test_site_design_variation.py's own
    "Deliberately adversarial subtypes" list -- coarse routes "Spanish
    Restaurant" to beauty_salon (its "spa"/"salon"/"beauty" branch is
    checked before "food"/"restaurant"/"cafe"), and the substring check
    then routed it specifically to nail_spa, producing real generated
    prose telling a Spanish restaurant's visitors about "sterilized
    instruments" and "the same technician." The sibling documented
    collision, "Corvette Repair" ("vet" inside "Corvette" routes to
    dental_medical before "repair" is ever checked), has the identical
    failure mode for prose (a car-repair shop talking about "patients" and
    "clinical evaluation"). Both are real for prose even though they're
    harmless for color/layout. Fixed with word-boundary regex throughout
    (closing off the SAME collision class in this function's own checks,
    not just the two already-known cases) plus two narrow, explicitly-
    scoped overrides for the two collisions this codebase's own tests
    already document -- not a general reimplementation of the coarse
    classifier, which would reintroduce the two-independently-maintained-
    lists drift risk this function's design deliberately avoids.
    """
    from .site_design import palettes
    # 2026-08-21, Opus review round 4: the word-boundary safety net added
    # below regressed real, common schema-type keys -- "MedicalClinic",
    # "HairSalon", "AutoRepair", "VeterinaryCare", "RealEstateAgent",
    # "GeneralContractor" and others are PascalCase compounds with no
    # internal spaces, so a strict \bmedical\b never matches inside
    # "medicalclinic" (no boundary between "medical" and "clinic" once
    # lowercased) even though this is the single most common real path
    # subtype strings take (site_engine.py's own _HUMAN dict keys). Split
    # PascalCase into real words first (the same technique _human() uses
    # for its own fallback, refined to treat a run of capitals as one
    # acronym unit so "HVACBusiness" splits to "HVAC Business", not
    # "H V A C Business") -- free-text subtypes with real spaces already
    # pass through unchanged.
    _camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", subtype or "")
    s = _camel_split.lower()
    coarse = palettes.industry_family_for(subtype)

    # 2026-08-21, Opus review round 3: plain \b...\b word-boundary regex
    # requires a NON-word character immediately after the keyword, so it
    # doesn't match a trailing "s" -- "Estates Agency", "Nails Salon", "Day
    # Spas", "Spanish Restaurants", "Corvette Repairs" all silently fell
    # through every guard below (round 2's own fix, and this one, alike),
    # reproducing the exact false-claim bugs both rounds were fixing, just
    # one letter away. Every keyword below now allows an optional trailing
    # "s" (`s?`) rather than requiring an exact match.

    # Known, documented substring collisions (see docstring) that identify
    # a MORE SPECIFIC correct family -- checked first, since a positive
    # redirect is better than a safe-but-generic fallback when we actually
    # know the right answer.
    if (coarse == palettes.INDUSTRY_FAMILY_BEAUTY_SALON
            and re.search(r"\brestaurants?\b|\bcafes?\b", s)
            and not re.search(r"\bsalons?\b|\bspas?\b|\bnails?\b|\bbeauty\b", s)):
        coarse = palettes.INDUSTRY_FAMILY_FOOD_RESTAURANT
    if (coarse == palettes.INDUSTRY_FAMILY_DENTAL_MEDICAL
            and re.search(r"\brepairs?\b", s)
            and "veterinary" not in s
            and not re.search(r"\bdent|\bphysicians?\b|\bmedical\b", s)):
        coarse = palettes.INDUSTRY_FAMILY_HOME_SERVICES

    # 2026-08-21, Opus review round 4: the two overrides above only catch
    # the two specific collisions this session happened to test ("spa" in
    # "Spanish", "vet" in "Corvette") -- confirmed via real generated
    # output that the SAME defect class is still open for any other word
    # that happens to contain one of industry_family_for()'s substrings
    # without being a genuine match: "Spanish Tapas Bar" (no literal
    # "restaurant"/"cafe" word, so the override above never fires) still
    # got beauty-salon prose about hair and stylists; "Corvette
    # Restoration" (no literal "repair") still got dental prose about
    # patients and clinical evaluation. Enumerating every possible
    # restaurant/repair synonym is an unbounded, losing list. Instead: if
    # coarse's own family has NO real, whole-word support anywhere in the
    # subtype string -- meaning the coarse classifier's own verdict came
    # from nothing but an accidental substring, with no positive evidence
    # either way -- don't guess a specific family at all. Fall back to
    # "general" (still real, industry-neutral, non-generic prose; never a
    # false, specific professional claim). This is a safety net under the
    # two specific overrides above, not a replacement for them: a genuine
    # positive match (like "restaurant") still routes to the better,
    # more-specific family instead of settling for "general".
    _REAL_WORD_MARKERS = {
        palettes.INDUSTRY_FAMILY_DENTAL_MEDICAL: r"\bdent|\bphysicians?\b|\bmedical\b|\bvets?\b|\bveterinary\b",
        palettes.INDUSTRY_FAMILY_HOME_SERVICES: r"\bplumb|\bhvac\b|\belectric|\brepairs?\b|\bcontractors?\b",
        palettes.INDUSTRY_FAMILY_LEGAL_FINANCE: r"\blaws?\b|\battorneys?\b|\bfinanc|\bestates?\b",
        palettes.INDUSTRY_FAMILY_BEAUTY_SALON: r"\bsalons?\b|\bbeauty\b|\bspas?\b|\bnails?\b",
        palettes.INDUSTRY_FAMILY_FOOD_RESTAURANT: r"\bfoods?\b|\brestaurants?\b|\bcafes?\b",
    }
    marker = _REAL_WORD_MARKERS.get(coarse)
    if marker and not re.search(marker, s):
        coarse = palettes.INDUSTRY_FAMILY_GENERAL

    if (coarse == palettes.INDUSTRY_FAMILY_LEGAL_FINANCE
            and re.search(r"\bestates?\b", s)
            and not re.search(r"\blaw\b|\battorneys?\b", s)):
        return "real_estate"
    if coarse == palettes.INDUSTRY_FAMILY_BEAUTY_SALON and re.search(r"\bnails?\b|\bspas?\b", s):
        return "nail_spa"
    return coarse


def prose_for(subtype, seed, business_name, human, loc, areas, svc_phrase, creds):
    family_key = _prose_family_for(subtype)
    variants = _FAMILIES.get(family_key, _FAMILIES["general"])
    variant_fn = variants[_variant_index(seed, len(variants))]
    return variant_fn(business_name, human, loc, areas, svc_phrase, creds)
