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


def _prose_seed(seed: int) -> int:
    return int(hashlib.sha256(f"prose:{seed}".encode()).hexdigest()[:16], 16)


def _variant_index(seed: int, n: int) -> int:
    return _prose_seed(seed) % n


# Each entry below is a function (business_name, human, loc, areas, svc_phrase, creds) -> 8-tuple:
#   (open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b)
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
        f'You can also read more <a href="about.html">about {business_name} and our approach to care</a> '
        f"before your visit."
    )
    p2_a = (
        f"Every treatment plan at {business_name} starts with a full clinical "
        f"evaluation, not a guess, so patients understand exactly what is "
        f"recommended and what the options are before agreeing to anything. "
    )
    em_clause = "getting the diagnosis right the first time is what everything else depends on"
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
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f"out. "
        f'You can also read more <a href="about.html">about {business_name} and how the practice is run</a> '
        f"before scheduling."
    )
    p2_a = (
        f"{business_name} reviews each case individually before recommending "
        f"anything, weighing the real options against a patient's actual "
        f"situation rather than defaulting to the same plan for everyone. "
    )
    em_clause = "a treatment plan that is explained clearly is one a patient can actually agree to with confidence"
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
        f"on the bill afterward."
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
        f"cost once insurance is factored in."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f'You can also read more <a href="about.html">about {business_name} and how we work</a> '
        f"before you call."
    )
    p2_a = (
        f"Every job at {business_name} starts with a real inspection and a "
        f"written estimate, so you understand the recommendation and the price "
        f"before agreeing to anything. "
    )
    em_clause = "doing the job right the first time is the foundation of everything here"
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
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f"show up. "
        f'You can also read more <a href="about.html">about {business_name} and what we guarantee</a> '
        f"before you call."
    )
    p2_a = (
        f"When something breaks, {business_name} treats speed and quality as "
        f"the same goal, not a trade-off — a rushed repair that fails again in "
        f"a month costs everyone more than doing it right the first time. "
    )
    em_clause = "a fast response only matters if the fix actually holds"
    p2_b = (
        f", which is why every technician is trained to diagnose the real "
        f"problem before starting work, not just treat the symptom that got the "
        f"call placed. The team covers {areas} and keeps trucks stocked so most "
        f"repairs are finished in one visit. If a job turns out to be bigger "
        f"than expected, you hear about it before the work continues, never "
        f"after. The warranty on labor and materials is explained up front, in "
        f"writing, so there is nothing to dispute later, and it applies "
        f"whether the fix was simple or took the whole crew a full day."
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
        f"invoice arrives."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f"the cracks between meetings. "
        f'You can also read more <a href="about.html">about {business_name} and how matters are handled</a> '
        f"before you reach out."
    )
    p2_a = (
        f"Every matter at {business_name} starts with a full review of the "
        f"facts and a candid assessment of the realistic outcomes, not a sales "
        f"pitch about guaranteed results no one can actually promise. "
    )
    em_clause = "an honest assessment early is worth more than false confidence later"
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
        f"at the last possible moment."
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
        f"with no pressure to decide on the spot."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _legal_finance_1(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" serving clients across {areas}. Practice areas include "
        f"{svc_phrase}, and every engagement follows the same process: a real "
        f"review of the situation, a written explanation of the options, and "
        f"an agreed fee structure before any work begins. "
    )
    if creds:
        p1_rest += f"{business_name} is {creds}, and that experience is applied to your specific situation, not a generic template. "
    p1_rest += (
        f"Clients are updated as their matter progresses rather than left to "
        f"wonder, and calls are returned within a reasonable window, not weeks "
        f"later. New clients receive the same responsiveness as clients who "
        f"have worked with the firm for years, from the very first call. "
        f'You can also read more <a href="about.html">about {business_name} and our approach</a> '
        f"before scheduling a consultation."
    )
    p2_a = (
        f"{business_name} treats a clear fee structure as part of good "
        f"representation, not a separate conversation to have later — clients "
        f"should never be surprised by a bill for work they did not know was "
        f"happening. "
    )
    em_clause = "clients who understand the plan and the cost make better decisions than clients who are just told to trust the process"
    p2_b = (
        f", which is why every matter starts with both laid out in writing. "
        f"The firm serves {areas} and structures communication so clients "
        f"always know the current status of their case without having to ask. "
        f"Complex matters get the same transparency as simple ones: what is "
        f"being done, why it is being done, and what it costs, explained before "
        f"it happens rather than justified after the invoice arrives. Any "
        f"change in strategy is discussed with the client first, not decided "
        f"unilaterally."
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
        f"and with a straight answer about what happens next."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


def _beauty_salon_0(business_name, human, loc, areas, svc_phrase, creds):
    open_clause = f"{business_name} is a {human} in {loc}"
    p1_rest = (
        f" welcoming clients from {areas}. The studio offers {svc_phrase}, and "
        f"every appointment starts with a real consultation, not a rushed "
        f"guess, so you leave with something you actually asked for. "
        f"Clients choose {business_name} because the same stylist sees you "
        f"appointment after appointment, product recommendations are honest "
        f"rather than upsold, and pricing is clear before anything begins. "
    )
    if creds:
        p1_rest += f"The team is {creds}, trained on current techniques rather than whatever was standard years ago. "
    p1_rest += (
        f"New clients get the same unhurried consultation as regulars, with "
        f"time to talk through what you actually want before any work starts, "
        f"including a real conversation about what your hair or skin can "
        f"actually support. "
        f'You can also read more <a href="about.html">about {business_name} and our approach</a> '
        f"before you book."
    )
    p2_a = (
        f"Every appointment at {business_name} starts with a real "
        f"conversation about what you want, not an assumption based on what is "
        f"trending, so the result actually matches what you asked for. "
    )
    em_clause = "a service that starts with real listening is the difference between a client who comes back and one who does not"
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
        f"the result actually holds up once you get home."
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
        f"arrive."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f"decorated to look that way in photos. "
        f'You can also read more <a href="about.html">about {business_name} and the experience</a> '
        f"before you book."
    )
    p2_a = (
        f"{business_name} treats the actual experience of an appointment as "
        f"part of the service, not just the technical result — how relaxed you "
        f"feel matters as much as how it looks when you leave. "
    )
    em_clause = "a great result delivered in a rushed, stressful appointment is not actually a great experience"
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
        f"pressure to add anything once you are already in the chair."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f"adjusted quietly depending on how busy the kitchen is. "
        f'You can also read more <a href="about.html">about {business_name} and our kitchen</a> '
        f"before you visit."
    )
    p2_a = (
        f"Every dish at {business_name} starts with ingredients chosen the "
        f"same day, not a freezer pulled from on a slow night, because the "
        f"difference is obvious the moment it hits the table. "
    )
    em_clause = "consistency is what actually keeps people coming back, not one great meal followed by three forgettable ones"
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
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f'You can also read more <a href="about.html">about {business_name} and the space</a> '
        f"before you book a table."
    )
    p2_a = (
        f"{business_name} treats the atmosphere of a meal as seriously as "
        f"what is on the plate — a great dish served in a rushed, loud, "
        f"stressful room is a different experience than the same dish enjoyed "
        f"slowly. "
    )
    em_clause = "the room and the pace of service matter as much as the food itself"
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
        f"actually ready."
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
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f'You can also read more <a href="about.html">about {business_name} and how we work</a> '
        f"before you reach out."
    )
    p2_a = (
        f"Every request at {business_name} starts with a real assessment of "
        f"the situation and a clear explanation of the options, not a "
        f"one-size-fits-all answer applied to everyone who calls. "
    )
    em_clause = "understanding the actual situation before recommending anything is what everything else depends on"
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
        f"take before you commit to anything."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


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
        f'You can also read more <a href="about.html">about {business_name} and our approach</a> '
        f"before reaching out."
    )
    p2_a = (
        f"{business_name} treats clear communication as part of the work "
        f"itself, not a separate courtesy — clients should never be surprised "
        f"by cost, timeline, or scope partway through, and none of that should "
        f"have to be pried out of anyone. "
    )
    em_clause = "clients who understand the plan make better decisions than clients who are just asked to trust the process"
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
        f" matter more than any single project. Every client gets direct "
        f"communication with the people actually doing the work, not a "
        f"go-between, and requests are documented so there is a clear record "
        f"of what was agreed at every stage. Getting started is simple, and "
        f"you will understand the real plan, the timeline, and the cost before "
        f"you commit to anything — no vague estimate that turns into a "
        f"different number once the work is already underway."
    )
    return open_clause, p1_rest, p2_a, em_clause, p2_b, about_a, about_em, about_b


_FAMILIES = {
    "dental_medical": [_dental_medical_0, _dental_medical_1],
    "home_services": [_home_services_0, _home_services_1],
    "legal_finance": [_legal_finance_0, _legal_finance_1],
    "beauty_salon": [_beauty_salon_0, _beauty_salon_1],
    "food_restaurant": [_food_restaurant_0, _food_restaurant_1],
    "general": [_general_0, _general_1],
}


def prose_for(subtype, seed, business_name, human, loc, areas, svc_phrase, creds):
    from .site_design import palettes
    family_key = palettes.industry_family_for(subtype)
    variants = _FAMILIES.get(family_key, _FAMILIES["general"])
    variant_fn = variants[_variant_index(seed, len(variants))]
    return variant_fn(business_name, human, loc, areas, svc_phrase, creds)
