# FTC v. Workado, LLC (f/k/a Content At Scale AI) — Complaint, Docket No. C-4822

- **Jurisdiction:** Federal
- **Domain:** AI-visibility / AI-generated content honesty — a real FTC enforcement matter, not
  guidance. **Correction (caught by the 2026-08-15 adversarial review, not caught when this file
  was first written):** this is a Complaint resolved by consent order, not an adjudicated finding.
  Per the companion Decision and Order (file 18), Workado "neither admits nor denies any of the
  allegations in the Complaint." Everything below is what the FTC *alleged*, not a court or
  Commission finding of fact — still a materially stronger source than the FTC blog post previously
  staged as file 10 (which produced zero atomic notes from paraphrased, non-verbatim content), but
  read it as allegation, not adjudication.
- **Source:** https://www.ftc.gov/system/files/ftc_gov/pdf/ContentatScaleAI-Complaint.pdf
  (FTC File No. 232-3092, Docket No. C-4822, Complaint issued August 21, 2025; case landing page:
  https://www.ftc.gov/legal-library/browse/cases-proceedings/2323092-content-scale-ai)
- **Retrieved:** 2026-08-15
- **Retrieval method:** Operator-supplied, real document, verbatim
- **Verification status:** Not yet lawyer-reviewed
- **Directly relevant to GEO Suite itself, not just client audits:** this is an FTC enforcement
  action against an AI-detection company for an unsubstantiated accuracy claim — GEO Suite's own
  Nova UI makes accuracy/measurement claims ("AI-Search Readiness," "measured live, never
  fabricated"). Worth the lawyer's attention for GEO Suite's own marketing posture, not only as a
  citation for client audits.

## What Workado (f/k/a Content At Scale AI) is and what it claimed

> "Respondent advertises, offers for sale, and sells products and services to consumers for creating
> marketing content, including the 'AI Content Detector'... The AI Content Detector uses artificial
> intelligence ('AI') technology to determine whether written content, including marketing content,
> is AI-generated."

> "Respondent claims that its AI Content Detector will predict with 98.3% accuracy whether text was
> generated using AI technology such as ChatGPT, GPT4, Claude, Bard, or another generative AI
> technology."

## The actual, real gap between the claim and the evidence

> "the AI model Respondent uses for its AI Content Detector was trained on abstracts of scholarly
> articles. Respondent did not create, train, or fine tune the AI model used in its AI Content
> Detector, nor has it tested whether the AI Content Detector would achieve the same accuracy rate
> for marketing and other plain language text that Respondent's users typically submit."

> "those test results show that when evaluating a mix of human-created and AI-generated content, the
> AI model correctly distinguished AI content from human content at a substantially lower rate than
> 98.3%."

> "the developers' best result for the AI Model's accuracy when evaluating a mix of human-created and
> AI-generated non-academic content was 74.5%. The developers' testing data also showed that the AI
> Model struggled to identify AI-generated content as AI-generated when evaluating non-academic
> content, correctly detecting AI-generated text merely 53.2% of the time."

> "even if a user relied on the AI Content Detector only to evaluate whether their AI-generated
> marketing content and copywriting would be detected as AI-generated, the AI Content Detector would
> do barely better than a coin toss."

## The charge

> "The acts and practices of Respondent as alleged in this complaint constitute unfair or deceptive
> acts or practices, in or affecting commerce in violation of Section 5(a) of the Federal Trade
> Commission Act."

## Real advertised claims the FTC cited as deceptive (Complaint Exhibit A, verbatim)

> "Use our AI Detector (now with 98% accuracy) to see if your text is human or AI generated from
> ChatGPT, GPT 4, Claude, & Bard. Our AI checker is one of the most trusted and goes deeper than a
> generic AI content detector."

> "Trained on blog posts, Wikipedia, essays, and more." (Contradicted by the complaint's own finding,
> paragraph 11: the model was trained only on academic-abstract text, not blog posts or Wikipedia.)

## Why this is here

A real, adjudicated, named example of exactly the failure mode this platform's own honesty
discipline is built to avoid: a specific numeric accuracy claim (98%) that didn't match the real,
tested performance (53-74%), and a claim about training data (blog posts, Wikipedia) that
contradicted the actual training data (academic abstracts only). Directly on point for auditing any
client's AI-related marketing claims, and worth a self-check against GEO Suite's own.
