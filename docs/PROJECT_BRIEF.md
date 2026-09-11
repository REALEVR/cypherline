# Cypherline — Project Brief (v1)

One AI-generated beat. Many voices, recorded separately, each taking a verse. Cypherline aligns every take to the rhythm and compiles them into one continuous 3–4 minute track — a crowdsourced cypher built on a shared instrumental.

Rendered version with better formatting: https://claude.ai/code/artifact/11f86593-bf8c-4769-891a-6a727361db0e

## Two things to settle before writing product code

**Suno's terms.** The shared beat comes from Suno AI. What you can legally do with a Suno-generated instrumental — redistribute it, let others record over it, compile it into a product other people use — depends on Suno's terms of service and which plan generated it. This needs a real read of Suno's current ToS, not an assumption, before any beat is used as the backbone of a product.

**Whose voice, whose song.** Every contributor is submitting a recording of their own voice into a compiled work other people will listen to, remix context, and the platform will host. You need each contributor's explicit consent to that use, and a clear answer to "who owns the compiled track" before the first real submission, not after.

## The core idea

Take one Suno-generated beat. Open it up for verses: anyone can record a take over it, for a specific slot in the song's structure (verse 1, verse 2, hook, bridge). Cypherline analyzes each submission against the beat's rhythm — tempo, downbeats, phrase length — and only surfaces takes that actually land in the pocket. The best-fitting take per slot gets compiled into one continuous song, capped at 3–4 minutes, credited to everyone who's on it.

**The core loop:** Beat published → Verses submitted per slot → Rhythm-fit scored → Best takes selected → Compiled track (3–4 min)

## The rhythm-matching problem — the real technical core

This is the part that makes Cypherline a product and not just a file-upload box. A home recording won't naturally line up with the beat's grid. The pipeline needs to:

1. **Detect the beat's grid.** BPM, downbeats, and phrase/bar boundaries from the Suno track (standard MIR techniques — onset detection, tempo estimation; libraries like `librosa` or `essentia` handle this well).
2. **Detect the vocal take's timing.** Where the contributor actually started relative to the beat, and where their phrasing drifts.
3. **Score the fit.** How well syllable/phrase onsets in the take align to the beat grid — this produces the "does this actually flow" score, not just "is this on beat."
4. **Time-align without pitch distortion.** Small timing drift gets corrected with time-stretching (not pitch-shifting) so a decent take that's slightly early or late still locks in.
5. **Reject, don't force.** A take that's rhythmically incompatible with the beat should be rejected or flagged for the contributor to retry — never algorithmically mangled into fitting.

## Data model (sketch)

| Entity | Key fields |
|---|---|
| **Beat** | `id`, `sunoTrackRef`, `bpm`, `beatGrid`, `structure[]` (ordered slots: verse/hook/bridge), `status` |
| **Submission** | `id`, `beatId`, `slotId`, `contributorUserId`, `audioUrl`, `rhythmFitScore`, `status` (pending / accepted / rejected) |
| **CompiledTrack** | `id`, `beatId`, `selectedSubmissionIds[]`, `durationSec` (180–240 target), `publishedAt` |

## Go-to-market angle

- **Challenge format, not upload box.** "Add your verse to this beat" is a native fit for TikTok/Reels duet-chain culture — the growth mechanic is the product, same shape as a duet challenge.
- **Scarcity per slot.** A beat with a limited number of open slots (say, 4 verse slots) creates urgency and a clear finish line — "the cypher is complete" is a shareable moment in itself.
- **Comparable products worth profiling.** Smule (collaborative singing), BandLab (collaborative production), Splice (sample/stem collaboration), TikTok duet chains. None of them do beat-locked multi-contributor compilation quite this way — that gap is the pitch, and Research should confirm it holds up.

## What happens next

Legal reads Suno's current terms of service specifically for this use case (redistribution, commercial compilation, plan-tier restrictions) and drafts the contributor consent/licensing terms before any real submission is accepted. Research profiles Smule, BandLab, and TikTok's duet-chain mechanics for what's genuinely different here. Engineering scaffolds the beat-grid detection and rhythm-fit scoring first — that's the part that has to actually work for the rest of the product to mean anything.
