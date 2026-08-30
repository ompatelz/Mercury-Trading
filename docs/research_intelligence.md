# Research intelligence

`ResearchIntelligenceService` is the deterministic gate between a proposed structured hypothesis and a campaign's durable research queue. It checks required data against the campaign's declared available data, detects exact/near duplicate claims with token-set similarity, retrieves failure-aware lessons for the same strategy family, and calculates an explainable priority from novelty, feasibility, evidence, historical failure similarity, and expected cost.

Rejected proposals are retained with their reasons; accepted proposals are sorted into `ResearchCampaign.research_queue`. This is triage only: it cannot generate executable code, run a campaign, promote a strategy, or bypass the existing validation workflow.
