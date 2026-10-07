# Guidelines for AI Coding Agents (AGENTS.md)

This document establishes the principles, development workflow, and quality standards for any AI Coding Agent contributing to the `auto-sub-video` project.

---

## 1. Core Principles

1. **Adhere to Project Context (`PROJECT.md`)**:
   * Always read and follow architectural decisions in [`PROJECT.md`](file:///d:/www/auto-sub-video/PROJECT.md).
   * Prioritize **100% free and open-source solutions**. Do not introduce paid cloud services (e.g., ElevenLabs, paid Whisper APIs) unless explicitly requested.
2. **Go Global & Language Standards**:
   * All user-facing documentation, UI labels, button tooltips, and public messages must be in **English**.
   * Internal code comments should be concise, explanatory (focusing on "why", not just "what"), and easy to maintain.
3. **Modularity & Independence**:
   * Each module within `core/` must adhere to the Single Responsibility Principle.
   * Data exchange between modules must use well-defined schemas (dataclasses or standardized dictionaries).
   * Avoid circular imports between submodules in `core/`.
4. **Resource Optimization**:
   * Default to lightweight CPU execution (faster-whisper with INT8 compute, native FFmpeg processing).
   * Automatically clean up intermediate temporary files in `temp/` to prevent excessive disk consumption.

---

## 2. Development Workflow

1. **Read Before Writing**: Inspect existing code with viewing tools before performing modifications.
2. **Step-by-Step Changes**: Plan complex modifications and execute sequentially with verification at each step.
3. **Evidence-Based Verification**:
   * Execute unit tests (`python tests/run_all_tests.py`) after making code changes.
   * Never report a task as complete without verifying runtime execution and syntax correctness.
4. **Clean Git Practices**:
   * Write concise, imperative commit messages under 72 characters.
   * Maintain repository integrity and keep dependencies up to date.
