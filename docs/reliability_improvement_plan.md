# Video Pipeline Reliability and Completion Plan

## Purpose

This plan turns the code review findings into a phased implementation roadmap. Its goal is to make each job produce a complete, validated video, report degraded results honestly, and clean up safely after success, failure, or cancellation.

## Progress Update — 2026-10-09

| Phase | Status | Notes |
| :--- | :--- | :--- |
| 0. Credentials | Implemented; owner action pending | The embedded provider key was removed and setup guidance added. Rotate/revoke the previously exposed key with its provider. |
| 1–7. Pipeline reliability and GUI | Implemented, with external credential rotation pending | Preflight, per-job cleanup, timeline padding, typed job outcomes, visible fallback warnings, validated output publishing, cancellation across pipeline stages, and SRT paths are in place. |
| 8. Verification and packaging | Source suite, isolated GUI smoke, and frozen-runtime checks passed; release checks remain | Latest `python tests/run_all_tests.py`: 7/7 test modules passed, including same-basename download isolation and cancellation checks for download, Whisper iteration, LLM, TTS, FFmpeg/mix/render. The frozen Windows build passed a runtime self-check for `.env`, PyAV, bundled FFmpeg, subtitle rendering, and writable app directories. A 176-second local-video E2E run translated and voiced all 75 dialogue segments and passed stream/duration/decode checks. A later E2E retry stalled in external LLM translation and was stopped; it produced no new result. Optional live provider tests remain separate. |
| 9. Performance | Core implementation and long-video measurement done; acceptance follow-ups remain | Hardware detection, TTS loop reuse and bounded concurrency, stage/substage timings, PyAV-first duration probing, configurable Whisper tuning, and adaptive LLM batch recovery are implemented. The synthetic 180s/300-cue mixer improved from 14.23s / 197.9 MiB to 3.02s / 65.9 MiB. Two local MP3 probe runs measured PyAV at 2.0–3.4 ms/probe vs FFmpeg at 170–362 ms/probe (83–107x). A 176-second long-video benchmark completed in 752.81s with 75/75 translated, 0 fallback, 362 MiB peak working set, and validated H.264/AAC output. Same-transcript TTS after silence trimming reduced >0.10s subtitle overruns from 67/75 to 10/75 and actual next-cue voice overlaps from 28/75 to 3/75; 0 TTS/sync failures. Short-video, repeated live-provider, manual language/timing, and credential-owner checks remain open. |

### Local full-pipeline baseline — 2026-10-09

The supplied `output/video_test.mp4` was processed with the configured CPU/INT8 Whisper model, default beam size 5, word timestamps enabled, the configured LLM, Edge TTS, subtitles, and the default render path. The source file was preserved; the result was written to `output/video_test_e2e_test/video_test_vi.mp4` (59,038,340 bytes).

| Stage | Elapsed |
| :--- | ---: |
| Media preflight | 0.84s |
| Audio extraction | 2.17s |
| Whisper transcription (75 dialogue segments) | 81.24s |
| LLM translation (19 batches; all 75 segments returned) | 570.20s |
| TTS and tempo sync (75 segments) | 275.71s |
| Audio mix | 5.04s |
| Subtitle generation | <0.01s |
| Video render | 53.58s |
| **Total measured stage time** | **988.78s (16m 29s)** |

The output contains H.264 video and AAC audio. Independent PyAV inspection measured the source at 176.033s and output video at 176.000s; output audio is 176.033s. The video-duration difference is one 30-fps frame, within the render tolerance. A sampled output frame showed the Vietnamese subtitle burned into the image.

The run exposed two optimization targets. LLM translation took 9m 30s across 19 sequential batches (about 30s per batch); a lightweight connectivity ping returned immediately, so provider generation/request latency—not a general connection outage—dominated this run. TTS took 4m 36s, including 247.24s in requests/retries, 0.85s across 150 PyAV duration probes, and 9.09s in `atempo` encoding. Many dubbed lines still exceeded their target interval after the current bounded tempo adjustment; the largest observed warning was 1.29s. The render completed, but possible speech overlap remains a synchronization-quality issue to address.

A separate one-run Whisper comparison on the same 176-second extracted audio measured `base` CPU/INT8 as follows: beam 1 with word timestamps 41.03s; beam 1 without them 51.97s; beam 5 with them 91.14s; beam 5 without them 138.98s. The order and single-repeat sample are too noisy to infer that disabling timestamps makes transcription slower or faster. Keep the Whisper defaults until repeated measurements and a subtitle-quality review support a change.

### Follow-up validation and optimization experiments — 2026-10-09

The batch-size-8 result above was only an isolated translation pass, not a complete pipeline comparison. Follow-up full-video runs changed the decision: keep the configured default at batch size 4. The batch-8 full run took 660.74s for translation, timed out on two requests, and left 16 segments in source-language fallback. That process predated adaptive timeout splitting. The final batch-4 run, with timeout splitting enabled, completed all 75 translations without source-fallback warnings.

| Run | LLM result | TTS result | Render/result |
| :--- | :--- | :--- | :--- |
| Isolated batch 8 translation | 504.96s; 75/75 translated; no fallback in one run | Not run | Directional only; not an end-to-end result |
| Full batch 8 experiment | 660.74s; two timeouts; 16 source-language fallbacks | 109.46s | Render completed; not recommended as the default configuration |
| Final full batch 4 run | 566.53s; 75 dialogues ready, with timeout splitting available | 144.60s for all 75 segments | 49.80s render; output 59,014,158 bytes; total measured stage time 793.20s (13m 13s) |
| Same saved 75-segment transcript, batch 4 | 525.95s; 19 requests; zero fallbacks | Not run | Exact transcript held constant |
| Same saved 75-segment transcript, batch 8 | 924.23s; 16 requests including adaptive splits; zero fallbacks | Not run | 398.28s (75.7%) slower than batch 4 in this paired one-run comparison |

Independent PyAV inspection of the final output at `output/video_test_e2e_final/video_test_vi.mp4` found H.264 video, AAC audio, 576x1024 at 30 fps, 176.000s video, and 176.033s audio. The input is 176.033s, so video duration differs by one frame. A sampled frame at 17s showed both the original embedded Chinese caption and the burned Vietnamese subtitle. A full FFmpeg decode pass to a null sink exited successfully with no decode errors. The source video was preserved.

The final batch-4 run used TTS concurrency 2 and 0.2s request-start pacing. Its TTS stage was 144.60s versus 275.71s in the earlier sequential baseline; because provider latency and regenerated speech vary, treat this one-pair comparison as directional. The 75-segment run recorded 266.41s cumulative request/retry time, 133.81s request wall time, 0.89s across 150 PyAV probes, and 9.70s in `atempo` encoding. A separate live 8-phrase smoke completed 8/8 in 42.93s sequentially and 10.99s with concurrency 2 (one run each). Unit coverage checks bounded concurrency and stable source ordering. Repeat live checks for rate limits and cancellation before considering a higher concurrency.

The fixed-transcript translation comparison returned all 75 segments with no fallback for either batch size, but the output text differed on 39 segments. Several inspected short lines favored batch 4 for concise dubbing and context (including the sampled seafood exchange); provider variation and chunk context can change wording. Batch 8 is slower here despite fewer requests, so retain batch 4. A complete human language review remains open.

The final run still warned that several dubbed lines exceeded their target interval; the largest excess was 1.34s. The renderer completed correctly, but possible speech overlap remains a synchronization-quality issue. Do not truncate dialogue silently; review the audio and choose a product policy before changing this behavior.

### Silence trimming follow-up — 2026-10-09

The TTS synchronizer now measures the active audio window with PyAV before applying tempo adjustment, trimming leading/trailing MP3 silence while preserving small speech padding. The interval target can use the actual short cue duration and is capped at the next cue start. On the same saved 75-line translation, one live Edge TTS run completed all 75 segments with no synthesis or sync failures in 70.58s. Using a 0.10s reporting threshold, subtitle overruns fell from 67 to 10 and measured voice overlap with the next cue fell from 28 to 3; the largest remaining next-cue overlap was 0.227s. This is a directional single-run result because Edge TTS output varies. Full E2E with this latest trimming change remains unverified: the retry stalled during external LLM translation before reaching TTS/render. Preserve full speech and keep residual overruns visible; do not claim zero overlap.

The checklist below records implemented items individually. Remaining unchecked items are follow-up work or require an external action. The test suite does not establish that every provider, codec, GPU, and packaged Windows path works on every machine.

## Outcomes

- The exported video keeps the source video's full duration, including when its audio stream ends early.
- Failed translation or TTS segments are visible and follow an explicit recovery policy instead of silently becoming missing dialogue.
- Failed or cancelled renders never appear as completed output files.
- Jobs do not overwrite one another's temporary files or final outputs.
- GUI controls describe behavior that is actually connected to the pipeline.
- Long-running network, FFmpeg, and audio operations have bounded waits and respond to cancellation.
- Automated tests cover the failure cases below without requiring live external services by default.

## Recommended Order

```mermaid
flowchart LR
    P0["Phase 0: Credential cleanup"] --> P1["Phase 1: Regression fixtures and media preflight"]
    P1 --> P2["Phase 2: Isolated job workspaces"]
    P2 --> P3["Phase 3: Timeline and audio duration"]
    P3 --> P4["Phase 4: Translation and TTS reliability"]
    P4 --> P5["Phase 5: Validated atomic rendering"]
    P5 --> P6["Phase 6: Cancellation and timeouts"]
    P6 --> P7["Phase 7: GUI and SRT integration"]
    P7 --> P8["Phase 8: End-to-end QA and packaging"]
    P8 --> P9["Phase 9: Measure and optimize performance"]
```

Phases 0 and 1 can start immediately. Later phases depend on the media/job contracts established earlier. Keep each phase in a reviewable change set and complete its acceptance criteria before moving on.

---

## Phase 0 — Remove Embedded Credentials

**Why:** `ui/main_window.py` contains a provider preset with a credential embedded in source. A credential committed to code should be considered exposed.

**Likely files:** `ui/main_window.py`, `config.py`, `.env.example`, possibly `README.md`.

### Tasks

- [x] Remove the literal credential from the provider preset. Load a user-provided key from `Config` or leave the field empty.
- [x] Ensure presets never save a credential into tracked source files.
- [x] Add a short setup hint explaining that provider credentials belong in `.env` or the settings UI.
- [ ] Ask the credential owner to revoke/rotate the exposed key outside the repository, then verify the replacement is not committed.

### Definition of done

- No provider credential is present in tracked source or documentation.
- The provider can still be configured through the supported settings flow.
- A repository search for common credential patterns finds no live secrets; known test placeholders are documented as placeholders.

---

## Phase 1 — Establish Regression Fixtures and Preflight Metadata

**Why:** Duration, stream, and codec decisions must use facts about the input rather than assumptions. This phase also creates repeatable tests before changing media behavior.

**Likely files:** `core/audio_extractor.py` or a focused media-probe module, `pipeline.py`, `tests/`.

### Tasks

- [x] Define a small typed media metadata result containing duration, video/audio stream presence, dimensions, frame rate, and codec/container information.
- [x] Probe metadata with the existing PyAV dependency where possible; use FFprobe only if it is reliably available in source and packaged builds.
- [x] Validate the source before expensive work starts. Report clear errors for unreadable files, missing video, missing audio when STT is required, and zero-duration media. Explicit codec allowlisting remains open.
- [x] Define a typed per-job result/status shape for completed, completed-with-warnings, failed, and cancelled jobs; use it at the GUI worker boundary while retaining the exception-based CLI API.
- [x] Add deterministic FFmpeg fixtures for audio shorter than video and video with no audio. Non-MP4 input and same-basename source fixtures remain open.
- [x] Keep network tests separate from the default test path; mock LLM and Edge TTS for deterministic unit tests.

### Definition of done

- Preflight reports actionable errors before transcription/rendering begins.
- Metadata can be read for the supported local formats and packaged runtime.
- The new fixture set reproduces the known audio-tail and filename-collision scenarios.

---

## Phase 2 — Isolate Job Files and Define Cleanup Ownership

**Why:** Current intermediate names are based on source stems or segment indexes in shared directories. Repeated or concurrent jobs can reuse files, and intermediate files accumulate.

**Likely files:** `config.py`, `pipeline.py`, `core/downloader.py`, `core/tts_engine.py`, `.gitignore`.

### Tasks

- [x] Create a unique working directory for every pipeline job, with collision-resistant naming.
- [x] Route downloaded video, extracted audio, mixed audio, ASS files, and dubbed segments through that job directory.
- [x] Keep the Whisper model cache in a separate persistent cache directory; never remove it during ordinary job cleanup.
- [x] Keep user inputs and completed output outside the job workspace, so job cleanup cannot remove them.
- [x] Add a `finally` cleanup policy for successful, failed, and cancelled jobs. Retain intermediates only when `KEEP_INTERMEDIATES` is enabled.
- [x] Ensure cleanup errors are logged as warnings and do not hide the primary pipeline error.

### Definition of done

- Two jobs with the same source filename use separate intermediate paths.
- A job cannot delete files owned by another job or user-provided inputs.
- Normal completion removes disposable intermediates while preserving the model cache and final output.
- Cancellation and exceptions also run cleanup.

---

## Phase 3 — Make the Audio Timeline Match the Video

**Why:** `create_mixed_audio_track` currently sizes the mix from the extracted audio. The pipeline does not pass the optional video duration, and render paths use `-shortest`; a shorter source audio stream can clip both late dubbing and the end of the picture.

**Likely files:** `pipeline.py`, `core/audio_mixer.py`, media metadata code, `tests/`.

### Tasks

- [x] Pass the probed video duration into the zero-based mixer timeline.
- [x] Build background and speech timelines to video duration, padding early-ending audio with silence and trimming content beyond the video end.
- [x] Reject invalid segment ranges and clip/drop segments outside the video duration with a visible warning.
- [x] Place dubbed segments by their source timestamp without clipping them when original audio ends early.
- [x] Use explicit FFmpeg stream mapping and only use `-shortest` after mixed audio is normalized to the intended video duration.
- [x] Assess Pydub's in-memory mixing cost on longer inputs. Replace full-timeline repeated overlays with 10-second bounded mix chunks while preserving timeline, source-audio fallback, delay, and ducking semantics.
- [x] Preserve correct behavior for videos with no source audio when an attached SRT is used; use silence as the mix background when dubbing.

### Definition of done

- An input whose audio ends before its video exports with the full video duration.
- A dubbed segment near the end of the video is present in the output audio.
- Short clips, silence gaps, overlapping segments, and audio longer than video have defined and tested behavior.
- Tests compare output duration with input duration using a documented frame/timestamp tolerance.

---

## Phase 4 — Make Translation and TTS Results Explicit

**Why:** Translation output is not fully validated, and TTS or speed-adjustment exceptions can be converted to silence while the job continues as if successful.

**Likely files:** `core/translator.py`, `core/tts_engine.py`, pipeline result/status schema, `tests/`.

### Tasks

- [x] Validate translation responses against the expected schema: list shape, known unique indexes, non-empty translated text, and complete coverage of requested segments.
- [x] Record per-segment outcomes for translation, TTS, and synchronization.
- [x] Add finite request timeouts and bounded retries/backoff for LLM and Edge TTS calls. Remove stale output before each TTS attempt.
- [x] Replace broad silent fallbacks around speed adjustment with specific error handling and a visible warning containing the segment index.
- [x] Apply a best-effort policy: preserve source speech when available after translation/TTS/sync failures; use silence when source speech is unavailable; report warnings.
- [x] Verify generated audio has positive duration before mixing and warn when it exceeds its target interval.
- [x] Report speech that remains longer than the target interval after bounded tempo adjustment so possible overlap is visible.
- [x] Reuse one event loop for a TTS batch and run synthesis with bounded concurrency (default 2, configurable up to 4), request pacing, retries, timeouts, cancellation, and source-order result handling.

### Definition of done

- Malformed or incomplete LLM responses cannot silently masquerade as fully translated output.
- Every missing/failed voice segment appears in job warnings and the GUI log.
- A job is marked “completed” only according to the selected strict/best-effort policy.
- No zero-byte, stale, or undecodable segment audio reaches the mixer.

---

## Phase 5 — Render to a Temporary File, Validate, Then Publish

**Why:** The renderer currently writes directly to the final path with overwrite enabled and primarily checks that a non-empty file exists. A failed or cancelled render can leave a misleading partial result, and same-name outputs can overwrite earlier work.

**Likely files:** `core/audio_mixer.py`, `pipeline.py`, `core/audio_extractor.py`, `tests/`, `build_exe.py`.

### Tasks

- [x] Select a collision-safe final filename. Existing files are preserved and numbered names are used for subsequent renders.
- [x] Render to a unique temporary MP4 in the output directory (retaining the `.mp4` suffix).
- [x] On NVENC failure, remove the failed temporary file before CPU fallback and report the fallback's real error if it also fails.
- [x] Make stream maps explicit for all render paths. Do not map unsupported subtitle/data/attachment streams.
- [x] When passthrough copy is incompatible with rendering, fall back to a supported encoder.
- [x] Validate the temporary output with PyAV: require video, require audio when expected, and compare duration with the source.
- [x] Sanitize ASS event and watermark text and escape Windows subtitle filter paths.
- [x] Publish only after validation using an atomic rename on the same filesystem. Remove temporary output on failure or cancellation.

### Definition of done

- A non-empty but invalid/truncated MP4 is never reported as successful.
- Failed and cancelled renders leave no file with the final output name.
- Valid output keeps the expected video/audio streams and duration.
- Passthrough, CPU encode, GPU encode, subtitle burn-in, logo overlay, and fallback paths have coverage.

---

## Phase 6 — Make Cancellation and Timeouts Consistent

**Why:** Cancellation is currently cooperative between pipeline steps and during final rendering, but downloads, extraction, speed adjustment, and active network calls can continue after the user presses Stop.

**Likely files:** `pipeline.py`, `ui/worker.py`, `core/downloader.py`, `core/audio_extractor.py`, `core/translator.py`, `core/tts_engine.py`, `core/audio_mixer.py`.

### Tasks

- [x] Replace the worker's plain boolean with a thread-safe cancellation event and pass it through long-running stages.
- [x] For FFmpeg subprocesses, poll for cancellation, terminate gracefully, wait for a short grace period, then kill if needed; always reap the child process.
- [x] Add bounded timeouts to network and FFmpeg subprocess operations. PyAV metadata probing is in-process and currently has no separate timeout.
- [x] Make the yt-dlp progress hook stop cleanly while preserving `InterruptedError` instead of converting cancellation into a normal download failure.
- [x] Make LLM/TTS requests finite and check cancellation while waiting or immediately after a request returns.
- [x] Ensure cancellation exceptions are not swallowed by encoder fallback or generic error handlers.
- [x] Mark active and queued items stopped/cancelled accurately; do not emit 100% batch progress after cancellation.
- [x] Coordinate cancellation with per-job cleanup and temporary render cleanup.

### Definition of done

- Stop eventually returns control for every stage within its documented maximum wait.
- No child FFmpeg process remains after cancellation.
- A cancellation is never displayed as an ordinary failure or successful completion.
- The final output is absent unless the render was fully validated and published.

---

## Phase 7 — Connect GUI Controls to Real Pipeline Paths

**Why:** The UI exposes SRT attachment and mode/settings controls that are not currently included in the worker task/options sent to the pipeline.

**Likely files:** `ui/main_window.py`, `ui/worker.py`, `pipeline.py`, a subtitle parser module, `tests/test_phase7.py`.

### Tasks

- [x] Snapshot each queued row's source and attached SRT into the worker task, and lock queue edits while processing to prevent row-index changes.
- [x] Connect “Attach .srt” to selected queue rows and validate existence, encoding, timestamps, and chronological ordering before processing.
- [x] Implement the attached-SRT path: preserve SRT timestamps, skip Whisper, optionally synthesize dubbing, and extract source audio only when required.
- [x] Define truthful source-mode semantics using “Prefer attached SRT; otherwise run Whisper.”
- [x] Apply dubbing delay to translated audio and subtitles together; leave preserved source-audio fallbacks at their original timing.
- [x] Disable controls that have no supported behavior, including original-subtitle blur and voice cloning through Edge TTS.
- [x] Prevent queue edits that could invalidate active row references by locking the queue during processing.
- [x] Surface per-video and per-segment warnings separately from fatal job errors.

### Definition of done

- Attached SRT is used for the selected row and cannot be confused with another queue item.
- SRT-only translation runs without Whisper and preserves the subtitle timing.
- Every visible processing control either changes the pipeline as described or is clearly unavailable/deferred.
- Batch statuses remain correct after retries, cancellation, and row sorting/removal.

---

## Phase 8 — Offline Regression, End-to-End Verification, and Packaging

**Why:** The current suite includes useful module checks, but the key failure cases need deterministic coverage and the packaged Windows runtime must be checked separately from source execution.

**Likely files:** `tests/`, `tests/run_all_tests.py`, `build_exe.py`, `AutoDubStudio.spec`, `README.md`, `PROJECT.md`.

### Tasks

- [x] Add focused offline tests for core acceptance cases: shorter-than-video audio, no-audio SRT input, failed TTS, incomplete translation JSON, output collisions, same-basename downloads in isolated workspaces, segment timing, typed outcomes, and cancellation across download, Whisper segment iteration, LLM, TTS, FFmpeg/audio mix, and render. Live provider and broader codec/GPU combinations remain environment-dependent.
- [x] Make the default suite offline and deterministic by mocking network providers. Live Edge TTS remains opt-in.
- [x] Add an FFmpeg end-to-end fixture that renders a short video with early-ending source audio, verifies streams and duration, and checks a late dubbed segment survives.
- [x] Run `python tests/run_all_tests.py`: 7/7 test modules passed on 2026-10-09. The yt-dlp availability check and optional live Edge TTS suite test were skipped; a separate live 8-phrase Edge TTS smoke passed, and the supplied video completed a full E2E run.
- [x] Build and launch an isolated PyInstaller onedir application; verify the GUI starts, bundled FFmpeg runs, and app temp/output folders are writable. Host-provided ICU DLLs are filtered because they conflict with Qt's Windows ICU ABI.
- [x] Verify PyAV metadata probing, subtitle font rendering, `.env` loading, bundled FFmpeg, and writable temp/output paths through a rebuilt frozen application using a harmless sentinel model value.
- [x] Update README to describe actual SRT, failure, cancellation, and output naming behavior. Release notes remain to be updated.

### Definition of done

- The offline suite passes without network access or pre-downloaded models.
- The optional integration suite clearly reports skipped/unavailable external services.
- Source and packaged runs produce equivalent validated output for the supported workflows.
- Documentation matches the implemented controls and known limitations.

---

---

## Phase 9 — Measure and Optimize Performance

**Why:** Reliability fixes do not establish that the application is fast or memory-efficient. Optimize only after measuring representative workloads so speed changes preserve subtitle timing, audio recovery, and render quality.

**Likely files:** `config.py`, `core/transcriber.py`, `core/tts_engine.py`, `core/audio_mixer.py`, `pipeline.py`, `tests/`, and a benchmark utility under `tools/` or `scripts/`.

### Tasks

- [ ] Add repeatable benchmark workloads for short and long videos, recording per-stage elapsed time, segment count, output duration, and peak process memory. The long 176-second sample is recorded; add a short-video workload. Keep live provider calls optional and distinguish network wait from local CPU time.
- [x] Add a repeatable synthetic audio-mixer benchmark for duration, cue count, elapsed time, peak Python allocations, and output-duration validation. Peak Python allocations are a proxy, not total process RSS.
- [x] Report successful job stage timings in the final pipeline log so real runs can identify dominant stages without adding telemetry services.
- [x] Cache CUDA/NVENC capability detection for the process lifetime; provide an explicit refresh option for diagnostics. Return copies so callers cannot mutate cached state.
- [x] Reuse a single asyncio event loop per TTS batch and add bounded Edge TTS concurrency (default 2, max 4) with request pacing, bounded retries/timeouts, cancellation, and stable result ordering.
- [x] Read generated audio duration through PyAV first to avoid one FFmpeg process per probe; preserve the FFmpeg fallback for unsupported/corrupt formats and cancellation checks.
- [x] Add a repeatable MP3 duration-probe benchmark that compares PyAV with the FFmpeg fallback and reports container-duration differences. Two local runs showed an 83–107x median speedup per probe; PyAV reported 1.00s vs FFmpeg's 1.06s for the synthetic 1-second MP3, so retain this encoder-delay/padding difference in output interpretation.
- [x] Record cumulative TTS request/retry time separately from PyAV probes, FFmpeg probe fallbacks, and `atempo` encoding within each batch.
- [x] Benchmark Pydub mixing on long videos and high segment counts, including peak Python allocations; implement a bounded chunk mixer and verify exact duration, cross-chunk placement, source fallback, and silence gaps.
- [x] Record the local synthetic 180-second / 300-cue result: before 14.23s and 197.9 MiB peak Python allocations; after 3.02s and 65.9 MiB. One post-change run was measured, so use this as directional evidence rather than a machine-independent guarantee.
- [ ] Measure Whisper CPU/GPU behavior across supported model sizes and beam settings. Keep word timestamps enabled where required by the product; do not reduce quality defaults without a recorded quality/performance comparison.
- [x] Make Whisper beam size and word timestamps configurable while preserving current defaults (`beam_size=5`, word timestamps enabled); add a local benchmark entry point for user-provided audio and selected models.
- [x] Run a one-repeat Whisper timing comparison on representative Chinese speech from the supplied video using CPU/INT8, beam 1/5, and word timestamps on/off; record that the result is directional only.
- [x] Run the full pipeline on the supplied local video and independently verify output streams, duration, and a burned-subtitle frame.
- [ ] Review Whisper subtitle accuracy and dubbing overlap manually; automated same-transcript measurement after silence trimming still found 3/75 next-cue overlaps above 0.10s (maximum 0.227s). A human listening/transcript review is still needed.
- [x] Add configurable LLM batch size (1–32), retain the stable default of 4, and split malformed, oversized, or timed-out batches before source fallback.
- [x] Compare batch sizes on a saved identical 75-segment transcript: batch 4 took 525.95s / 19 requests, batch 8 took 924.23s / 16 requests including adaptive splits; both returned all segments without fallback. Keep batch 4 as default.
- [ ] Complete a human language review of the 39 differing translations and subtitle/audio timing before changing translation defaults.
- [x] Add a bounded TTS concurrency implementation and verify it with a live 8-phrase smoke and a 75-segment full pipeline run; the 8-phrase one-run comparison measured 42.93s sequentially vs 10.99s at concurrency 2.
- [ ] Repeat the TTS concurrency benchmark with rate-limit handling and cancellation under live provider conditions. Unit tests cover bounded 429 retry and cancellation; repeated live-provider error-rate and output checks remain open. Do not increase the default concurrency until these pass.
- [x] Define and test the overlong-speech policy: preserve the complete generated audio, report subtitle-interval overrun and actual overlap with the next cue, and classify the job as completed-with-warnings. Do not silently truncate speech.
- [ ] Record before/after timing and memory results for each optimization. Mixer, probe, and long-video pipeline metrics are recorded; add short-video and repeated-run results. Avoid claiming a performance improvement when no representative measurement exists.

### Definition of done

- A repeatable local benchmark identifies which pipeline stages dominate time and memory for representative workloads.
- Performance changes include correctness checks for duration, audio/subtitle timing, and failure/cancellation paths.
- The app remains usable on CPU-only Windows systems, and optional GPU paths retain a CPU fallback.
- Reported speed or memory gains are supported by recorded measurements on the same workload and hardware.

---

## Cross-Phase Review Checklist

- [x] User-provided inputs are never deleted or overwritten by job cleanup.
- [x] No error path reports success merely because an output file exists.
- [x] Warnings identify the affected segment or video and describe the recovery without logging credentials.
- [x] Pipeline temp paths are per-job; persistent model/cache data is separate.
- [x] UTF-8 without BOM is used for new documentation and text files.
- [x] Tests are deterministic by default; live network checks are opt-in.
- [ ] Each phase is reviewed and committed separately with a concise imperative message.
