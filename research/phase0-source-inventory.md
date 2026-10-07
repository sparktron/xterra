# Xterra Wiki Research: Phase 0 Source Inventory

Scope: second-gen Nissan Xterra (N50), mechanical/electrical troubleshooting and off-road modification.
Model years: 2005-2015 commonly cited [Unverified]; project notes say 2006-2016. Resolve in Phase 0 recon.
Status of this file: seed list compiled from general knowledge. No source below has been fetched or checked yet.

## Conventions

- **Trust tier**: T1 factory/primary data, T2 community knowledge, T3 third-party reference, T4 video, T5 vendor tech notes, T6 archive/fallback
- **Access**: open / login / paywall / unknown
- **Scrape feasibility**: unknown until recon; values to assign: easy / hard / blocked / manual-only
- **Priority**: P1 (recon first), P2, P3
- **Status**: `todo` -> `recon` -> `extracted` -> `qa`
- Every claim in the wiki should carry a provenance tag: `FSM/TSB`, `forum-consensus`, or `single-anecdote`.
- Mark Frontier/Pathfinder/Titan/Equator-derived facts as `cross-model` until confirmed on an Xterra.

## Source table

| ID | Source | URL | Tier | Content | Access | Scrape | Priority | Status | Notes |
|----|--------|-----|------|---------|--------|--------|----------|--------|-------|
| S01 | Nissan N50 Xterra factory service manual | TBD (Nissan TechInfo or forum-hosted PDFs) | T1 | Wiring diagrams, torque specs, DTC tables, diagnostic trees | unknown | unknown | P1 | todo | Licensing/copyright: summarize and link, do not republish verbatim. Verify legal access route. |
| S02 | NHTSA | nhtsa.gov | T1 | TSBs, recalls, owner complaints by model year | open | unknown | P1 | todo | Complaint counts can rank failure patterns. |
| S03 | Nissan TSBs (non-NHTSA mirrors) | TBD | T1 | Service bulletins | unknown | unknown | P2 | todo | Find mirrors during recon. |
| S04 | OEM parts catalogs (online Nissan dealer sites) | TBD | T1 | Exploded diagrams, part numbers by VIN/option | open | unknown | P1 | todo | Pick one or two catalogs; compare diagram coverage. |
| S05 | thenewx.org | thenewx.org | T2 | Pinned/how-to threads, DIY, build threads, parts diagrams | unknown | unknown | P1 | todo | Stated favorite. Mine pinned + how-to first. |
| S06 | Nissan Frontier forums (D40) | TBD | T2 | VQ40DE, RE5R05A, transfer case, axles, electrical | unknown | unknown | P1 | todo | Drivetrain treated as near-identical to Frontier 2005-2021 (stated); tag `cross-model`. |
| S07 | Pathfinder (R51) / Titan forums | TBD | T2 | Shared VQ40DE and 5-speed automatic | unknown | unknown | P3 | todo | `cross-model` only. |
| S08 | Reddit r/Xterra | reddit.com/r/Xterra | T2 | Recent Q&A, pointers to better threads | open | unknown | P3 | todo | Shallow; use as index. |
| S09 | Facebook Xterra groups | n/a | T2 | Tribal knowledge | login | blocked | P3 | todo | Poorly searchable; likely manual-only. |
| S10 | Expedition Portal | expeditionportal.com | T2 | Build logs, suspension/gearing decisions | unknown | unknown | P2 | todo | |
| S11 | Pirate4x4 | pirate4x4.com | T2 | Build logs, off-road mods | unknown | unknown | P2 | todo | |
| S12 | Haynes/Chilton Frontier & Xterra 2005-2015 manual | n/a | T3 | Procedures and specs | paywall | manual-only | P3 | todo | Verify exact title and year coverage [Unverified]. |
| S13 | ALLDATA / Mitchell1 ProDemand / Identifix | n/a | T3 | Verified procedures, TSB summaries | paywall | blocked | P3 | todo | Likely reference-only. |
| S14 | YouTube (symptom + model searches) | youtube.com | T4 | Visual repair procedures | open | unknown | P2 | todo | Candidate transcript mining. Search terms: "Xterra N50 <symptom>", "VQ40DE timing chain guide rail". Channels not vetted. |
| S15 | Suspension/armor vendors (ARB/OME, Bilstein, Total Chaos, Camburg, similar) | TBD | T5 | Fitment guides, load ratings, lift charts | open | unknown | P2 | todo | Vendor claims: tag as vendor-sourced. |
| S16 | Gear/axle/locker vendors | TBD | T5 | Ratios, locker compatibility per axle | open | unknown | P3 | todo | |
| S17 | Internet Archive Wayback Machine | web.archive.org | T6 | Snapshots of dead forum threads and vendor pages | open | unknown | P1 | todo | Primary route for preserving forum content. |

## Cross-model reference platforms (for tagging only)

- Nissan Frontier D40 (2005-2021), Pathfinder R51, Titan, Suzuki Equator (Frontier twin)
- Shared components to confirm: VQ40DE engine, RE5R05A automatic, transfer case, axles [Inference]

## Phase 0 recon checklist (per source)

- [ ] Confirm URL is live and which sections matter
- [ ] Record access method (open / login / paywall) and ToS or robots.txt notes
- [ ] Test scrape feasibility on 3 sample pages (rendering, pagination, rate limits)
- [ ] Estimate volume (threads, pages, documents)
- [ ] Identify pinned/high-value index pages
- [ ] Check Wayback coverage for the same pages
- [ ] Assign trust tier and provenance tag
- [ ] Note licensing/copyright constraints on republishing
- [ ] Update Status and Scrape columns in the table above

## Known failure topics to seed search (from general knowledge) [Unverified]

- Transmission cooler leaking into radiator (coolant/ATF cross-contamination)
- VQ40DE timing chain guide/tensioner wear
- Use these as recon search terms, not as confirmed facts.

## Open questions

- Final model-year range for the wiki (2005-2015 vs 2006-2016)
- Legal access route for the FSM
- Which parts catalog to standardize on
- Whether to treat YouTube transcripts as a source type in later phases
