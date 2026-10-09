# TikTok Short-Form Video Readiness Plan

## Goal

Make AutoDub Studio reliably turn short social clips into portrait-ready translated/dubbed videos while preserving source content, keeping captions readable around platform controls, and validating the exported media before publishing it.

This plan covers processing and export. It does not include automatic story editing, hook generation, or automatic selection of the best source moments.

## Current Baseline

- TikTok/Douyin URLs and local video files are accepted by the existing pipeline.
- The renderer preserves the input frame size and aspect ratio; it does not currently create a true TikTok portrait export from a landscape source.
- The subtitle preview can display portrait and landscape layouts, but that preview choice does not transform the rendered video.
- The ASS subtitle script currently assumes a 720x1280 play resolution.
- SRT input can bypass Whisper. Short clip render/latency benchmarks and profile-specific output checks are not yet recorded.
- The app supports subtitle placement controls, but has no TikTok UI-safe-area guide.

## Phases

### Phase 1 — Portrait Export Profiles

**Scope:** Add an opt-in `TikTok 9:16` export profile while keeping `Original` as the backward-compatible default. Support explicit crop-to-fill and contain-with-padding behavior, scale subtitles against the output profile, and preserve audio/video duration.

**Acceptance:**

- Profile values are validated; invalid sizes and fit modes fail before FFmpeg starts.
- TikTok output is portrait 9:16 at the selected target size (default 1080x1920); landscape inputs can be cropped or contained without stretching.
- Original profile retains the source geometry.
- Subtitles render with the correct profile dimensions.
- The pipeline warns when the selected portrait profile must upscale; it does not imply added source detail.
- Offline tests assert output dimensions and no geometric stretch for portrait and landscape fixture inputs.

### Phase 2 — UI Export Controls and Safe-Area Preview

**Scope:** Add export profile and fit-mode controls to the GUI. Show the chosen profile in the subtitle preview and add an optional configurable safe-area overlay; keep guides out of the rendered output.

**Acceptance:**

- Users can select Original or TikTok 9:16, and Crop or Contain.
- Preview reflects the target crop and safe-area guide, including subtitle placement.
- UI settings reach the worker and pipeline for every queued job.

### Phase 3 — Short-Clip Timeline and Audio Cases

**Scope:** Exercise short durations and edge conditions, including clips under 5 seconds, no-audio clips with SRT, sparse speech, a final cue near video end, and TTS extending beyond the final cue.

**Acceptance:**

- A short video never loses its last frames due to audio duration or `-shortest` behavior.
- Invalid/empty speech is reported clearly; SRT-only processing remains available for clips without audio.
- Subtitle and dubbing timestamps stay inside the output duration or emit an explicit warning.
- Short fixtures finish with validated audio/video streams.

### Phase 4 — TikTok Export Validation

**Scope:** Validate portrait geometry, codecs, frame rate, duration, audio presence, safe-area placement, and full decode before atomic output publication.

**Acceptance:**

- Portrait profile output is 9:16 at target dimensions and encoded in broadly compatible H.264/AAC MP4.
- Render validation checks expected dimensions/profile in addition to stream presence and duration.
- Failed render/profile validation never publishes a completed output.
- Tests cover profile validation failures and CPU fallback.

### Phase 5 — Short-Form Performance and Release QA

**Scope:** Add representative 10–15s and 30–60s benchmark inputs with per-stage timings, translated cue count, render time, file size, and peak RSS. Verify the frozen Windows build.

**Acceptance:**

- Benchmark runs are repeatable and distinguish local processing from external LLM/TTS wait.
- One local/SRT-only path and one live provider path are recorded separately.
- GUI, packaged runtime, and output preview work with portrait clips and landscape-to-portrait exports.

## Risks and Decisions

- Cropping landscape footage can remove important subjects; users must preview crop or choose contain mode.
- Upscaling low-resolution sources does not restore detail. Warn or preserve source resolution when the source is below the selected profile threshold.
- TikTok overlay dimensions can vary by device, caption length, and app UI. Safe-area guides are visual aids, not a guarantee against every platform overlay.
- TikTok download availability can depend on current `yt-dlp` support, login/cookies, region, and source restrictions; maintain local-file and SRT workflows as fallbacks.
- Keep Original as the default to avoid changing existing output behavior without user selection.

## Progress

| Phase | Status | Evidence / Remaining work |
|---|---|---|
| 1. Portrait export profiles | Complete | Added validated 9:16 profile, crop/contain transforms, profile-aware ASS dimensions, geometry/codec checks, full stream decode before publish, and landscape fixture renders. Original remains the default. |
| 2. UI controls and preview guides | Complete | Added profile/fit controls and subtitle preview safe-area overlay. GUI tests cover settings and guide state; frozen runtime profile check is included in Phase 5. |
| 3. Short-clip timeline | Complete | Rendered a 1.2s no-audio SRT clip to portrait; existing late-dub fixture now exports portrait while preserving 1.2s duration and the final dubbed audio. |
| 4. Export validation | Complete | Profile render verifies exact dimensions, H.264/AAC, stream presence, duration, and full PyAV decode before atomic publication. Crop/contain outputs decode in tests. |
| 5. Performance and release QA | Complete | Added a no-network 10s/30s SRT export benchmark with two repeats; recorded separate live-provider measurements from the earlier full video; built the Windows bundle and passed frozen portrait-profile, codec, subtitle, full-decode, FFmpeg, PyAV, and writable-directory checks. |

### Short-form benchmark — 2026-10-09

`python tools/benchmark_shortform_export.py --durations 10 30 --repeats 2` generated landscape fixtures with 5 and 14 SRT cues, used deterministic fake translations, disabled TTS, and rendered 1080x1920 H.264/AAC outputs. All eight measurements include full-stream decode validation. These are repeatable local-render results on this Windows host; network providers are deliberately excluded.

| Duration / mode | Wall time by repeat | Mean | Output size | Peak RSS |
|---|---:|---:|---:|---:|
| 10s crop | 7.91s / 6.08s | 7.00s | 2.05 MB | 65.9–124.1 MiB* |
| 10s contain | 4.43s / 4.45s | 4.44s | 2.18 MB | 66.0–66.2 MiB |
| 30s crop | 16.68s / 19.98s | 18.33s | 6.29 MB | 67.2–67.6 MiB |
| 30s contain | 12.74s / 12.53s | 12.64s | 6.51 MB | 68.2–68.6 MiB |

*The first crop run recorded a 124.1 MiB peak, while its repeat recorded 65.9 MiB; retain this cold-start spike in capacity planning rather than treating the warm run as the peak.

The independent 1.2s SRT-only landscape fixture rendered to 360x640 in about 0.2s with no source audio. A separate 1.2s dubbed fixture preserved late audio through the last cue. The app now warns when the target requires pixel upscaling so users know the larger frame does not add detail. The prior 176s live-provider run is recorded in `reliability_improvement_plan.md`; its external LLM/TTS latency is not comparable to this local short-export benchmark.

The frozen Windows self-check passed on the landscape fixture and also rendered the new 360x640 TikTok profile with burned subtitles. It verified H.264/AAC, full stream decode, bundled FFmpeg 7.1, PyAV probing, and writable temp/output directories. The self-check report is generated under the ignored `output/benchmarks/` directory.
