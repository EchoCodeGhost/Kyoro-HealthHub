# manage_registry.py — Geräte- und App-Registry verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_registry.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages the registry of devices and apps in a local JSON file. Enables tracking of device types, serial numbers, purchase dates, and deactivation dates for traceability. NOTE: device_id values are pseudonyms (e.g. 'DEV-8abb425f'), not semantic device names. Mapping to real device names is handled by identity_resolver.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/registry.json (local only, not in repo). Supports separate management for devices and apps with different attributes.

## Data flow

- **Reads:** `~/.config/kyoro/registry.json`
- **Writes:** `~/.config/kyoro/registry.json`

## Limitations

Local file only. No automatic validation.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_registry.py device list
python3 scripts/utils/manage/personal/manage_registry.py device add
python3 scripts/utils/manage/personal/manage_registry.py device edit 3
python3 scripts/utils/manage/personal/manage_registry.py device delete 3
python3 scripts/utils/manage/personal/manage_registry.py device export
python3 scripts/utils/manage/personal/manage_registry.py app list
python3 scripts/utils/manage/personal/manage_registry.py app add
python3 scripts/utils/manage/personal/manage_registry.py app edit 2
python3 scripts/utils/manage/personal/manage_registry.py app delete 2
python3 scripts/utils/manage/personal/manage_registry.py app export
```
